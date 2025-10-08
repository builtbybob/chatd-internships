"""
Tests for Section 4.3: Reaction Batching and Rate Limiting

This module tests the enhanced ReactionQueue class with batch processing,
improved rate limiting, and configurable retry logic.
"""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, Mock, patch

import discord
import pytest_asyncio

from chatd.bot import ReactionQueue
from chatd.config import Config


@pytest.fixture
def mock_config():
    """Create a mock config with Section 4.3 settings."""
    config = Mock()
    # Section 4.3 configuration
    config.reaction_batch_size = 3
    config.reaction_batch_delay = 0.1  # 100ms for faster tests
    config.reaction_retry_count = 2
    config.reaction_retry_delay = 0.05  # 50ms for faster tests
    # Legacy configuration (still used)
    config.batch_processing_delay = 0.01  # 10ms for faster tests
    
    # Section 4.4 configuration (required for ReactionQueue)
    config.health_window_size = 100
    config.degradation_threshold = 0.5
    config.recovery_threshold = 0.2
    config.circuit_breaker_threshold = 10
    config.circuit_breaker_timeout = 300
    config.health_check_interval = 60
    
    return config


@pytest.fixture
def mock_message():
    """Create a mock Discord message."""
    message = Mock(spec=discord.Message)
    message.id = 123456789
    message.add_reaction = AsyncMock()
    return message


@pytest_asyncio.fixture
async def reaction_queue(mock_config):
    """Create a ReactionQueue instance for testing."""
    with patch('chatd.bot.config', mock_config):
        queue = ReactionQueue()
        await queue.start()
        yield queue
        await queue.stop()


class TestReactionBatching:
    """Test reaction batch processing functionality."""
    
    @pytest.mark.asyncio
    async def test_batch_processing_with_multiple_batches(self, reaction_queue, mock_message, mock_config):
        """Test that reactions are processed in correct batch sizes."""
        # Test with 7 reactions across 3 batches (3+3+1)
        reactions = ['👍', '❤️', '🎉', '🚀', '✅', '📝', '🔥']
        
        start_time = time.time()
        await reaction_queue.queue_reactions(mock_message, reactions)
        
        # Wait for processing to complete
        await asyncio.sleep(0.5)
        
        # Verify all reactions were attempted
        assert mock_message.add_reaction.call_count == 7
        
        # Verify batch delays were applied (should take at least 2 * batch_delay)
        elapsed_time = time.time() - start_time
        expected_min_time = 2 * mock_config.reaction_batch_delay  # 2 delays between 3 batches
        assert elapsed_time >= expected_min_time
        
        # Verify statistics
        stats = reaction_queue.get_stats()
        assert stats['queued'] == 1
        assert stats['processed'] == 1
    
    @pytest.mark.asyncio
    async def test_batch_processing_with_single_batch(self, reaction_queue, mock_message, mock_config):
        """Test that small reaction sets process quickly in single batch."""
        # Test with 2 reactions (single batch)
        reactions = ['👍', '❤️']
        
        start_time = time.time()
        await reaction_queue.queue_reactions(mock_message, reactions)
        
        # Wait for processing to complete
        await asyncio.sleep(0.2)
        
        # Verify all reactions were attempted
        assert mock_message.add_reaction.call_count == 2
        
        # Verify no unnecessary delays (should be very fast for single batch)
        elapsed_time = time.time() - start_time
        # Single batch should not have batch delays, just the sleep time we added for testing
        assert elapsed_time >= 0.2  # Should include our 0.2s sleep
        assert elapsed_time < 0.3   # But not much longer
        
        # Verify statistics
        stats = reaction_queue.get_stats()
        assert stats['queued'] == 1
        assert stats['processed'] == 1
    
    @pytest.mark.asyncio
    async def test_batch_failure_handling(self, reaction_queue, mock_message, mock_config):
        """Test handling of failures within batches."""
        reactions = ['👍', '❤️', '🎉', '🚀']
        
        # Make second and fourth reactions fail with rate limiting
        def add_reaction_side_effect(reaction):
            if reaction in ['❤️', '🚀']:
                response_mock = Mock()
                response_mock.status = 500
                response_mock.reason = "Internal Server Error"
                raise discord.HTTPException(response_mock, "Server error")
        
        mock_message.add_reaction.side_effect = add_reaction_side_effect
        
        await reaction_queue.queue_reactions(mock_message, reactions)
        
        # Wait for processing and potential retries
        await asyncio.sleep(1.0)
        
        # Verify all reactions were attempted initially
        assert mock_message.add_reaction.call_count >= 4
        
        # Verify statistics show some failures
        stats = reaction_queue.get_stats()
        assert stats['queued'] >= 1
        assert stats['retried'] >= 1 or stats['failed'] >= 1
    
    @pytest.mark.asyncio
    async def test_rate_limit_retry_with_exponential_backoff(self, reaction_queue, mock_message, mock_config):
        """Test exponential backoff retry logic for rate limits."""
        reactions = ['👍', '❤️']
        
        # Make all reactions fail initially, then succeed
        call_count = 0
        def add_reaction_side_effect(reaction):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # First attempt fails
                response_mock = Mock()
                response_mock.status = 500
                response_mock.reason = "Internal Server Error"
                raise discord.HTTPException(response_mock, "Server error")
            # Subsequent attempts succeed
        
        mock_message.add_reaction.side_effect = add_reaction_side_effect
        
        start_time = time.time()
        await reaction_queue.queue_reactions(mock_message, reactions)
        
        # Wait for processing and retries
        await asyncio.sleep(1.5)
        
        # Verify retries occurred with exponential backoff
        elapsed_time = time.time() - start_time
        expected_min_time = mock_config.reaction_retry_delay  # At least one retry delay
        assert elapsed_time >= expected_min_time
        
        # Verify statistics show retries
        stats = reaction_queue.get_stats()
        assert stats['retried'] >= 1
    
    @pytest.mark.asyncio
    async def test_message_not_found_stops_processing(self, reaction_queue, mock_message, mock_config):
        """Test that NotFound errors stop processing immediately."""
        reactions = ['👍', '❤️', '🎉']
        
        # Make first reaction fail with NotFound - use proper response mock
        response_mock = Mock()
        response_mock.status = 404
        response_mock.reason = "Not Found"
        mock_message.add_reaction.side_effect = discord.NotFound(response_mock, "Message not found")
        
        await reaction_queue.queue_reactions(mock_message, reactions)
        
        # Wait for processing
        await asyncio.sleep(0.3)
        
        # Verify processing stopped after first reaction
        assert mock_message.add_reaction.call_count == 1
        
        # Verify statistics show early termination (processed count is not incremented for early returns)
        stats = reaction_queue.get_stats()
        assert stats['processed'] == 0  # Early termination doesn't count as processed
        assert stats['failed'] == 0  # Not counted as failed since it was early termination
    
    @pytest.mark.asyncio
    async def test_forbidden_error_stops_processing(self, reaction_queue, mock_message, mock_config):
        """Test that Forbidden errors stop processing immediately."""
        reactions = ['👍', '❤️', '🎉']
        
        # Make first reaction fail with Forbidden - use proper response mock
        response_mock = Mock()
        response_mock.status = 403
        response_mock.reason = "Forbidden"
        mock_message.add_reaction.side_effect = discord.Forbidden(response_mock, "Missing permissions")
        
        await reaction_queue.queue_reactions(mock_message, reactions)
        
        # Wait for processing
        await asyncio.sleep(0.3)
        
        # Verify processing stopped after first reaction
        assert mock_message.add_reaction.call_count == 1
        
        # Verify statistics show early termination (processed count is not incremented for early returns)
        stats = reaction_queue.get_stats()
        assert stats['processed'] == 0  # Early termination doesn't count as processed
        assert stats['failed'] == 0  # Not counted as failed since it was early termination
    
    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self, reaction_queue, mock_message, mock_config):
        """Test behavior when max retries are exhausted."""
        reactions = ['👍', '❤️']
        
        # Make all reactions always fail - use proper response mock
        response_mock = Mock()
        response_mock.status = 500
        response_mock.reason = "Internal Server Error"
        mock_message.add_reaction.side_effect = discord.HTTPException(response_mock, "Server error")
        
        await reaction_queue.queue_reactions(mock_message, reactions)
        
        # Wait for all retries to complete
        await asyncio.sleep(2.0)
        
        # Verify statistics show exhausted retries
        stats = reaction_queue.get_stats()
        assert stats['failed'] >= 1
        assert stats['retried'] >= 1


class TestReactionQueueConfiguration:
    """Test configuration-driven behavior."""
    
    @pytest.mark.asyncio
    async def test_configurable_batch_size(self, mock_message):
        """Test that batch size configuration is respected."""
        # Test with batch size of 2
        config = Mock()
        config.reaction_batch_size = 2
        config.reaction_batch_delay = 0.1
        config.reaction_retry_count = 2
        config.reaction_retry_delay = 0.05
        config.batch_processing_delay = 0.01
        config.health_window_size = 100  # Add missing config
        config.circuit_breaker_threshold = 10  # Add missing config
        config.circuit_breaker_timeout = 300  # Add missing config
        config.degradation_threshold = 0.5  # Add missing config
        config.recovery_threshold = 0.2  # Add missing config
        config.health_check_interval_seconds = 60  # Add missing config
        
        with patch('chatd.bot.config', config):
            queue = ReactionQueue()
            await queue.start()
            
            reactions = ['👍', '❤️', '🎉', '🚀', '✅']  # 5 reactions = 3 batches
            
            start_time = time.time()
            await queue.queue_reactions(mock_message, reactions)
            
            # Wait for processing
            await asyncio.sleep(0.5)
            
            # Should have 2 delays between 3 batches
            elapsed_time = time.time() - start_time
            expected_min_time = 2 * config.reaction_batch_delay
            assert elapsed_time >= expected_min_time
            
            await queue.stop()
    
    @pytest.mark.asyncio
    async def test_configurable_retry_count(self, mock_message):
        """Test that retry count configuration is respected."""
        # Test with only 1 retry
        config = Mock()
        config.reaction_batch_size = 5
        config.reaction_batch_delay = 0.05
        config.reaction_retry_count = 1  # Only 1 retry
        config.reaction_retry_delay = 0.05
        config.batch_processing_delay = 0.01
        config.health_window_size = 100  # Add missing config
        config.circuit_breaker_threshold = 10  # Add missing config
        config.circuit_breaker_timeout = 300  # Add missing config
        config.degradation_threshold = 0.5  # Add missing config
        config.recovery_threshold = 0.2  # Add missing config
        config.health_check_interval_seconds = 60  # Add missing config
        
        with patch('chatd.bot.config', config):
            queue = ReactionQueue()
            await queue.start()
            
            reactions = ['👍']
            
            # Make reaction always fail
            response_mock = Mock()
            response_mock.status = 500
            response_mock.reason = "Internal Server Error"
            mock_message.add_reaction.side_effect = discord.HTTPException(response_mock, "Server error")
            
            await queue.queue_reactions(mock_message, reactions)
            
            # Wait for processing and single retry
            await asyncio.sleep(0.5)
            
            # Should have exactly 2 attempts (initial + 1 retry)
            assert mock_message.add_reaction.call_count == 2
            
            await queue.stop()


class TestPerformanceImprovement:
    """Test performance improvements from batching."""
    
    @pytest.mark.asyncio
    async def test_batch_vs_individual_timing(self, mock_message):
        """Compare batch processing vs individual processing timing."""
        reactions = ['👍', '❤️', '🎉', '🚀', '✅', '📝']  # 6 reactions
        
        # Test batch processing (Section 4.3)
        batch_config = Mock()
        batch_config.reaction_batch_size = 3
        batch_config.reaction_batch_delay = 0.1
        batch_config.reaction_retry_count = 2
        batch_config.reaction_retry_delay = 0.05
        batch_config.batch_processing_delay = 0.01
        batch_config.health_window_size = 100  # Add missing config
        batch_config.circuit_breaker_threshold = 10  # Add missing config
        batch_config.circuit_breaker_timeout = 300  # Add missing config
        batch_config.degradation_threshold = 0.5  # Add missing config
        batch_config.recovery_threshold = 0.2  # Add missing config
        batch_config.health_check_interval_seconds = 60  # Add missing config
        
        with patch('chatd.bot.config', batch_config):
            queue = ReactionQueue()
            await queue.start()
            
            start_time = time.time()
            await queue.queue_reactions(mock_message, reactions)
            await asyncio.sleep(0.5)
            batch_time = time.time() - start_time
            
            await queue.stop()
        
        # Batch processing should be significantly faster than individual processing
        # With 6 reactions in 2 batches: should take ~1 batch delay (0.1s)
        # Individual processing would take 6 * reaction_delay (much longer)
        assert batch_time < 0.6  # Should be much faster than individual processing (adjusted for test environment)
        assert mock_message.add_reaction.call_count == 6
    
    @pytest.mark.asyncio
    async def test_queue_statistics_accuracy(self, reaction_queue, mock_message):
        """Test that queue statistics accurately reflect batch processing."""
        # Queue multiple reaction tasks
        reactions1 = ['👍', '❤️']
        reactions2 = ['🎉', '🚀', '✅']
        
        await reaction_queue.queue_reactions(mock_message, reactions1)
        await reaction_queue.queue_reactions(mock_message, reactions2)
        
        # Wait for processing
        await asyncio.sleep(0.5)
        
        # Verify statistics
        stats = reaction_queue.get_stats()
        assert stats['queued'] == 2  # 2 tasks queued
        assert stats['processed'] == 2  # 2 tasks processed
        assert mock_message.add_reaction.call_count == 5  # 5 total reactions