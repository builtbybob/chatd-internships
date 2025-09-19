"""
Configuration management for the chatd-internships bot.

This module handles loading, validating, and providing access to 
configuration values from environment variables or other sources.
"""

import os
import sys
from typing import List, Optional

import logging
from dotenv import load_dotenv

# Initialize logger (will be properly configured after logging_utils is imported)
logger = logging.getLogger('chatd-internships')

# Default configuration values
DEFAULT_CONFIG = {
    'REPO_URL': 'https://github.com/SimplifyJobs/Summer2026-Internships.git',
    'LOCAL_REPO_PATH': '/app/Summer2026-Internships',
    'DATA_FILE': '/app/data/previous_data.json',
    'MESSAGES_FILE': '/app/data/message_tracking.json',
    'CURRENT_HEAD_FILE': '/app/data/current_head.txt',
    'LOG_FILE': '/app/logs/chatd.log',
    'LOG_LEVEL': 'INFO',
    'MAX_RETRIES': '3',
    'CHECK_INTERVAL_MINUTES': '1',
    'ENABLE_REACTIONS': 'false',
}

# Required configuration values that must be set
REQUIRED_CONFIG = [
    'DISCORD_TOKEN',
    'CHANNEL_IDS',
]

class Config:
    """Configuration singleton for the chatd-internships bot."""
    
    _instance = None
    
    def __new__(cls):
        """Ensure only one instance of Config exists."""
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the configuration, loading from environment variables."""
        if self._initialized:
            return
            
        # Load environment variables from .env file
        load_dotenv()
        
        # Set default values
        for key, value in DEFAULT_CONFIG.items():
            setattr(self, key.lower(), os.getenv(key, value))
        
        # Set up path to JSON file
        self.json_file_path = os.path.join(
            self.local_repo_path, 
            '.github', 
            'scripts', 
            'listings.json'
        )
        
        # Parse channel IDs as a list
        self.channel_ids = [
            id.strip() for id in os.getenv('CHANNEL_IDS', '').split(',')
        ] if os.getenv('CHANNEL_IDS') else []
        
        # Convert numeric values to integers
        self.max_retries = int(self.max_retries)
        self.check_interval_minutes = int(self.check_interval_minutes)
        
        # Convert boolean values
        self.enable_reactions = self.enable_reactions.lower() in ('true', '1', 'yes', 'on')
        
        # Set Discord token
        self.discord_token = os.getenv('DISCORD_TOKEN')
        
        # Make data file paths easily accessible
        self.data_file = self.data_file
        self.messages_file = self.messages_file  
        self.current_head_file = self.current_head_file
        self.log_file = self.log_file
        
        self._initialized = True

    def validate(self) -> bool:
        """
        Validate required configuration values.
        
        Returns:
            bool: True if validation passes, False otherwise
        """
        # Check for required variables
        missing_vars = []
        for var in REQUIRED_CONFIG:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
            logger.error("Please check your .env file or set these environment variables.")
            return False
        
        # Validate channel IDs format
        try:
            for channel_id in self.channel_ids:
                int(channel_id)
        except (ValueError, AttributeError):
            logger.error("CHANNEL_IDS must be comma-separated integers")
            return False
        
        logger.info("Configuration validation passed.")
        return True


# Create a singleton instance
config = Config()


def validate_config() -> bool:
    """
    Validate required configuration values on startup.
    
    Returns:
        bool: True if validation passes, exits the program otherwise
    """
    if not config.validate():
        sys.exit(1)
    return True
