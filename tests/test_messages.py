"""
Tests for the messages module.
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from chatd.messages import format_epoch, format_message, compare_roles, get_reaction_tips


class TestMessages(unittest.TestCase):
    """Test cases for the messages module."""
    
    def test_format_epoch(self):
        """Test epoch time formatting with timezone conversion."""
        # Mock the config to use America/New_York timezone for consistent testing
        with patch('chatd.config.config') as mock_config:
            mock_config.timezone = 'America/New_York'
            
            # Create a specific UTC timestamp (2023-09-15 19:13:00 UTC)
            # This should convert to 3:13 PM EDT in Eastern time (September is in EDT, so UTC-4)
            utc_dt = datetime(2023, 9, 15, 19, 13, 0, tzinfo=timezone.utc)
            timestamp = utc_dt.timestamp()
            formatted = format_epoch(timestamp)
            
            # September 15, 2023 is in EDT (UTC-4), so 19:13 UTC = 15:13 EDT (3:13 PM)
            # The function should now output without leading zeros and use the correct timezone name
            
            # Check that it contains the expected time (without leading zero) and timezone suffix
            self.assertIn('September, 15 @ 3:13 PM', formatted)
            self.assertTrue(formatted.endswith('EST') or formatted.endswith('EDT'))
    
    def test_format_message(self):
        """Test message formatting."""
        # Create a test role
        role = {
            'title': 'Software Engineer Intern',
            'company_name': 'Example Corp',
            'url': 'https://example.com/jobs/123',
            'locations': ['San Francisco, CA', 'Remote'],
            'terms': ['Summer 2026'],
            'sponsorship': 'Available',
            'date_posted': datetime.now().timestamp(),
        }
        
        formatted = format_message(role)
        
        # Check for key components in the formatted message
        self.assertIn('## Example Corp', formatted)
        self.assertIn('## [Software Engineer Intern]', formatted)
        self.assertIn('San Francisco, CA | Remote', formatted)
        self.assertIn('### Sponsorship: `Available`', formatted)
    
    def test_format_message_with_missing_fields(self):
        """Test message formatting with missing fields."""
        # Create a role with minimal fields
        role = {
            'title': 'Software Engineer Intern',
            'company_name': 'Example Corp',
            'date_posted': datetime.now().timestamp(),
        }
        
        formatted = format_message(role)
        
        # Check for key components in the formatted message
        self.assertIn('## Example Corp', formatted)
        self.assertIn('## [Software Engineer Intern]', formatted)
        self.assertIn('Not specified', formatted)  # For missing locations
    
    def test_compare_roles(self):
        """Test role comparison."""
        old_role = {
            'title': 'Software Engineer Intern',
            'company_name': 'Example Corp',
            'locations': ['San Francisco, CA'],
        }
        
        new_role = {
            'title': 'Software Engineer Intern',
            'company_name': 'Example Corp',
            'locations': ['San Francisco, CA', 'Remote'],
        }
        
        changes = compare_roles(old_role, new_role)
        self.assertEqual(len(changes), 1)
        self.assertIn("locations changed from ['San Francisco, CA'] to ['San Francisco, CA', 'Remote']", changes)
    
    def test_get_reaction_tips_disabled(self):
        """Test reaction tips when reactions are disabled."""
        mock_config = MagicMock()
        mock_config.enable_reactions = False
        mock_config.message_reactions = ['❓', '📝']
        
        with patch('chatd.config.config', mock_config):
            result = get_reaction_tips()
            self.assertEqual(result, "")
    
    def test_get_reaction_tips_no_reactions_configured(self):
        """Test reaction tips when no reactions are configured."""
        mock_config = MagicMock()
        mock_config.enable_reactions = True
        mock_config.message_reactions = []
        
        with patch('chatd.config.config', mock_config):
            result = get_reaction_tips()
            self.assertEqual(result, "")
    
    def test_get_reaction_tips_default_emojis(self):
        """Test reaction tips with default emojis."""
        mock_config = MagicMock()
        mock_config.enable_reactions = True
        mock_config.message_reactions = ['❓', '📝']
        
        with patch('chatd.config.config', mock_config):
            result = get_reaction_tips()
            self.assertEqual(result, "❓: More info • 📝: Mark applied")
    
    def test_get_reaction_tips_custom_emojis(self):
        """Test reaction tips with custom emojis (custom emojis are ignored in tips)."""
        mock_config = MagicMock()
        mock_config.enable_reactions = True
        mock_config.message_reactions = ['❓', '💼', '👍']
        
        with patch('chatd.config.config', mock_config):
            result = get_reaction_tips()
            self.assertEqual(result, "❓: More info")
    
    def test_get_reaction_tips_mixed_emojis(self):
        """Test reaction tips with mix of known and custom emojis (only known emojis get tips)."""
        mock_config = MagicMock()
        mock_config.enable_reactions = True
        mock_config.message_reactions = ['📝', '💯', '❓']
        
        with patch('chatd.config.config', mock_config):
            result = get_reaction_tips()
            self.assertEqual(result, "📝: Mark applied • ❓: More info")
    
    def test_get_reaction_tips_only_custom_emojis(self):
        """Test reaction tips with only custom emojis (should return empty string)."""
        mock_config = MagicMock()
        mock_config.enable_reactions = True
        mock_config.message_reactions = ['💼', '👍', '⭐']
        
        with patch('chatd.config.config', mock_config):
            result = get_reaction_tips()
            self.assertEqual(result, "")
    
    def test_format_message_with_reactions_enabled(self):
        """Test message formatting includes reaction tips when reactions are enabled."""
        mock_config = MagicMock()
        mock_config.enable_reactions = True
        mock_config.message_reactions = ['❓', '📝']
        mock_config.timezone = 'America/New_York'  # Add proper timezone
        
        role = {
            'title': 'Software Engineer Intern',
            'company_name': 'Example Corp',
            'url': 'https://example.com/jobs/123',
            'locations': ['San Francisco, CA'],
            'terms': ['Summer 2026'],
            'date_posted': datetime.now().timestamp(),
        }
        
        with patch('chatd.config.config', mock_config):
            formatted = format_message(role)
            self.assertIn('❓: More info • 📝: Mark applied', formatted)
    
    def test_format_message_with_reactions_disabled(self):
        """Test message formatting excludes reaction tips when reactions are disabled."""
        mock_config = MagicMock()
        mock_config.enable_reactions = False
        mock_config.message_reactions = ['❓', '📝']
        mock_config.timezone = 'America/New_York'  # Add proper timezone
        
        role = {
            'title': 'Software Engineer Intern',
            'company_name': 'Example Corp',
            'url': 'https://example.com/jobs/123',
            'locations': ['San Francisco, CA'],
            'terms': ['Summer 2026'],
            'date_posted': datetime.now().timestamp(),
        }
        
        with patch('chatd.config.config', mock_config):
            formatted = format_message(role)
            self.assertNotIn('❓: More info', formatted)
            self.assertNotIn('📝: Mark applied', formatted)


if __name__ == '__main__':
    unittest.main()
