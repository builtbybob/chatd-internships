"""
Tests for Section 5.13: Configurable reaction set for job posting messages.

Tests configuration validation and parsing for MESSAGE_REACTIONS.
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from chatd.config import Config


class TestConfigurableReactions:
    """Test suite for configurable MESSAGE_REACTIONS."""

    @pytest.fixture(autouse=True)
    def reset_config_instance(self):
        """Patch Config._instance to None before each test."""
        with patch.object(Config, "_instance", None):
            yield

    # =============================================================================
    # Configuration Parsing and Validation Tests
    # =============================================================================

    @patch.dict(os.environ, {'MESSAGE_REACTIONS': '❓,✅'}, clear=False)
    def test_default_message_reactions_parsing(self):
        """Test parsing of default MESSAGE_REACTIONS configuration."""
        config = Config()
        
        assert config.message_reactions == ['❓', '✅']
        assert len(config.message_reactions) == 2

    @patch.dict(os.environ, {'MESSAGE_REACTIONS': '❓,✅,💼,🔗,👍'}, clear=False)
    def test_multiple_reactions_parsing(self):
        """Test parsing multiple reactions."""
        config = Config()
        
        expected_reactions = ['❓', '✅', '💼', '🔗', '👍']
        assert config.message_reactions == expected_reactions
        assert len(config.message_reactions) == 5

    @patch.dict(os.environ, {'MESSAGE_REACTIONS': '❓ , ✅ , 💼 '}, clear=False)
    def test_reactions_with_whitespace(self):
        """Test that whitespace around reactions is stripped."""
        config = Config()
        
        assert config.message_reactions == ['❓', '✅', '💼']

    @patch.dict(os.environ, {'MESSAGE_REACTIONS': '❓,,✅,,'}, clear=False)
    def test_empty_reactions_filtered(self):
        """Test that empty strings from double commas are filtered out."""
        config = Config()
        
        assert config.message_reactions == ['❓', '✅']

    @patch.dict(os.environ, {'MESSAGE_REACTIONS': '<:custom_emoji:123456789>'}, clear=False)
    def test_custom_emoji_support(self):
        """Test support for custom Discord emoji format."""
        config = Config()
        
        assert config.message_reactions == ['<:custom_emoji:123456789>']

    @patch.dict(os.environ, {'MESSAGE_REACTIONS': ' , , '}, clear=False)
    @patch('chatd.config.logger')
    def test_empty_reactions_validation_fails(self, mock_logger):
        """Test that MESSAGE_REACTIONS with only whitespace/commas fails validation."""
        config = Config()
        
        result = config._validate_message_reactions()
        
        assert result is False
        mock_logger.error.assert_called()
        error_calls = [call[0][0] for call in mock_logger.error.call_args_list]
        assert any("MESSAGE_REACTIONS cannot be empty" in call for call in error_calls)

    @patch.dict(os.environ, {'MESSAGE_REACTIONS': ','.join(['❓'] * 15)}, clear=False)
    @patch('chatd.config.logger')
    def test_too_many_reactions_validation_fails(self, mock_logger):
        """Test that too many reactions fails validation."""
        config = Config()
        
        result = config._validate_message_reactions()
        
        assert result is False
        mock_logger.error.assert_called()
        error_calls = [call[0][0] for call in mock_logger.error.call_args_list]
        assert any("Too many reactions configured" in call for call in error_calls)

    @patch.dict(os.environ, {'MESSAGE_REACTIONS': '❓,❓,✅'}, clear=False)
    @patch('chatd.config.logger')
    def test_duplicate_reactions_validation_fails(self, mock_logger):
        """Test that duplicate reactions fail validation."""
        config = Config()
        
        result = config._validate_message_reactions()
        
        assert result is False
        mock_logger.error.assert_called()
        error_calls = [call[0][0] for call in mock_logger.error.call_args_list]
        assert any("Duplicate reaction emoji found" in call for call in error_calls)

    @patch.dict(os.environ, {'MESSAGE_REACTIONS': 'a' * 60}, clear=False)
    @patch('chatd.config.logger')
    def test_overly_long_reaction_validation_fails(self, mock_logger):
        """Test that overly long reaction strings fail validation."""
        config = Config()
        
        result = config._validate_message_reactions()
        
        assert result is False
        mock_logger.error.assert_called()
        error_calls = [call[0][0] for call in mock_logger.error.call_args_list]
        assert any("Reaction emoji too long" in call for call in error_calls)

    @patch.dict(os.environ, {'MESSAGE_REACTIONS': '❓,✅,💼'}, clear=False)
    @patch('chatd.config.logger')
    def test_valid_reactions_validation_passes(self, mock_logger):
        """Test that valid reactions pass validation."""
        config = Config()
        
        result = config._validate_message_reactions()
        
        assert result is True
        mock_logger.info.assert_called()
        info_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        assert any("MESSAGE_REACTIONS validation passed" in call for call in info_calls)

    @patch.dict(os.environ, {
        'MESSAGE_REACTIONS': '❓,✅,💼',
        'DISCORD_TOKEN': 'test.token.12345678901234567890123456789012345678901234567890',
        'CHANNEL_IDS': '123456789012345678,987654321098765432'
    }, clear=False)
    @patch('chatd.config.Config._validate_discord_connection')
    @patch('chatd.config.Config._validate_repository')
    @patch('chatd.config.Config._validate_file_permissions')
    def test_message_reactions_included_in_full_validation(self, mock_file_perms, mock_repo, mock_discord):
        """Test that MESSAGE_REACTIONS validation is included in full config validation."""
        # Mock all external validation methods to return True
        mock_file_perms.return_value = True
        mock_repo.return_value = True
        mock_discord.return_value = True
        
        config = Config()
        result = config.validate()
        
        # Should pass since all validations return True
        assert result is True