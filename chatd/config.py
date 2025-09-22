"""
Configuration management for the chatd-internships bot.

This module handles loading, validating, and providing access to 
configuration values from environment variables or other sources.
"""

import os
import s    def _validate_file_permissions(self):
        """Validate that all required file paths exist and are writable."""
        logger.info("✅ Starting file permissions validation...")
        
        # List of file paths to validate
        file_paths = [
            ('DATA_FILE', self.data_file),
            ('MESSAGES_FILE', self.messages_file),
            ('CURRENT_HEAD_FILE', self.current_head_file),
            ('LOG_FILE', self.log_file),
            ('LOCAL_REPO_PATH', self.local_repo_path),
        ]
        
        # Debug: Print all paths
        logger.info("🔍 Debug - File paths being validated:")
        for config_name, file_path in file_paths:
            logger.info(f"   {config_name}: '{file_path}' (type: {type(file_path)})")subprocess
import tempfile
from pathlib import Path
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
    'MAX_POST_AGE_DAYS': '5',
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
        
        # Set default values, but don't let empty environment variables override defaults
        for key, default_value in DEFAULT_CONFIG.items():
            env_value = os.getenv(key)
            # Use environment value only if it's not None and not empty
            if env_value is not None and env_value.strip() != '':
                setattr(self, key.lower(), env_value)
            else:
                setattr(self, key.lower(), default_value)
        
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
        self.max_post_age_days = int(self.max_post_age_days)
        
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
        logger.info("🔍 Starting configuration validation...")
        
        # Check for required variables
        missing_vars = []
        for var in REQUIRED_CONFIG:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            logger.error(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
            logger.error("   Please check your .env file or set these environment variables.")
            return False
        
        # Validate Discord token format (basic check)
        if not self._validate_discord_token():
            return False
        
        # Validate channel IDs format
        if not self._validate_channel_ids():
            return False
        
        # Validate numeric configuration values
        if not self._validate_numeric_config():
            return False
        
        # Validate file system permissions
        if not self._validate_file_permissions():
            return False
        
        # Validate git repository accessibility
        if not self._validate_repository():
            return False
        
        # Validate Discord connection (basic token test)
        if not self._validate_discord_connection():
            return False
        
        logger.info("✅ Configuration validation passed.")
        return True

    def _validate_discord_token(self) -> bool:
        """Validate Discord token format."""
        token = self.discord_token
        if not token:
            logger.error("❌ DISCORD_TOKEN is required but not set")
            return False
        
        # Basic Discord token format check (should start with a specific pattern)
        if len(token) < 50:
            logger.error("❌ DISCORD_TOKEN appears to be too short (expected 50+ characters)")
            logger.error("   Please verify you have the correct bot token from Discord Developer Portal")
            return False
        
        # Discord bot tokens typically contain dots
        if '.' not in token:
            logger.error("❌ DISCORD_TOKEN format appears invalid (missing expected structure)")
            logger.error("   Please verify you have the correct bot token from Discord Developer Portal")
            return False
        
        logger.info("✅ Discord token format validation passed")
        return True

    def _validate_channel_ids(self) -> bool:
        """Validate channel IDs format and accessibility."""
        if not self.channel_ids:
            logger.error("❌ CHANNEL_IDS is required but not set")
            logger.error("   Please provide comma-separated Discord channel IDs")
            return False
        
        try:
            for channel_id in self.channel_ids:
                channel_int = int(channel_id)
                # Discord snowflake IDs are typically 17-19 digits
                if not (16 <= len(str(channel_int)) <= 20):
                    logger.error(f"❌ Channel ID {channel_id} appears invalid (Discord IDs are typically 17-19 digits)")
                    return False
            logger.info(f"✅ Channel IDs validation passed ({len(self.channel_ids)} channels configured)")
        except (ValueError, AttributeError):
            logger.error("❌ CHANNEL_IDS must be comma-separated integers")
            logger.error("   Example: CHANNEL_IDS=123456789012345678,987654321098765432")
            return False
        
        return True

    def _validate_numeric_config(self) -> bool:
        """Validate numeric configuration values."""
        # Validate max_post_age_days
        if not (1 <= self.max_post_age_days <= 30):
            logger.error(f"❌ MAX_POST_AGE_DAYS must be between 1 and 30 days. Got: {self.max_post_age_days}")
            logger.error("   This controls how old job postings can be before being filtered out")
            return False
        
        # Validate check interval
        if not (1 <= self.check_interval_minutes <= 60):
            logger.error(f"❌ CHECK_INTERVAL_MINUTES must be between 1 and 60 minutes. Got: {self.check_interval_minutes}")
            logger.error("   This controls how often the bot checks for new job postings")
            return False
        
        # Validate max retries
        if not (1 <= self.max_retries <= 10):
            logger.error(f"❌ MAX_RETRIES must be between 1 and 10. Got: {self.max_retries}")
            logger.error("   This controls how many times to retry failed operations")
            return False
        
        logger.info("✅ Numeric configuration validation passed")
        return True

    def _validate_file_permissions(self) -> bool:
        """Validate file system permissions for required directories."""
        # Create list of file paths and their names for validation
        file_paths = [
            ('DATA_FILE', self.data_file),
            ('MESSAGES_FILE', self.messages_file),
            ('CURRENT_HEAD_FILE', self.current_head_file),
            ('LOG_FILE', self.log_file),
            ('LOCAL_REPO_PATH', self.local_repo_path),
        ]
        
        # Check for empty paths first
        for config_name, file_path in file_paths:
            if not file_path or file_path.strip() == '':
                logger.error(f"❌ {config_name} is empty or not set")
                logger.error(f"   Please check your environment variables or .env file")
                logger.error(f"   Default value should be: {DEFAULT_CONFIG.get(config_name, 'N/A')}")
                return False
        
        # Create list of directories that need to be writable
        required_dirs = [
            os.path.dirname(self.data_file),
            os.path.dirname(self.messages_file),
            os.path.dirname(self.current_head_file),
            os.path.dirname(self.log_file),
            self.local_repo_path,  # This is already a directory path, not a file path
        ]
        
        # Debug logging to identify empty paths
        file_paths = [
            ("data_file", self.data_file),
            ("messages_file", self.messages_file), 
            ("current_head_file", self.current_head_file),
            ("log_file", self.log_file),
            ("local_repo_path", self.local_repo_path)
        ]
        
        for name, path in file_paths:
            logger.info(f"🔍 {name}: '{path}'")
        
        for i, dir_path in enumerate(required_dirs):
            logger.info(f"🔍 Required dir {i}: '{dir_path}'")
            # Skip empty paths
            if not dir_path or dir_path.strip() == '':
                logger.error(f"❌ Empty directory path found in configuration (index {i})")
                logger.error("   Please check your environment variables for empty values")
                return False
                
            if not self._check_directory_writable(dir_path):
                logger.error(f"❌ Directory not writable: {dir_path}")
                logger.error("   The bot needs write access to store data and logs")
                return False
        
        logger.info("✅ File permissions validation passed")
        return True

    def _check_directory_writable(self, dir_path: str) -> bool:
        """Check if a directory is writable, creating it if necessary."""
        try:
            # Create directory if it doesn't exist
            os.makedirs(dir_path, exist_ok=True)
            
            # Test write access
            test_file = os.path.join(dir_path, '.write_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return True
        except (OSError, PermissionError) as e:
            logger.error(f"   Cannot write to {dir_path}: {e}")
            return False

    def _validate_repository(self) -> bool:
        """Validate git repository URL accessibility."""
        try:
            # Test if git is available
            result = subprocess.run(['git', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                logger.error("❌ Git command not available")
                logger.error("   Please install git: apt update && apt install -y git")
                return False
            
            # Test repository URL accessibility (without cloning)
            logger.info(f"🔍 Testing repository access: {self.repo_url}")
            result = subprocess.run([
                'git', 'ls-remote', '--heads', self.repo_url
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                logger.error(f"❌ Cannot access repository: {self.repo_url}")
                logger.error("   Error output:", result.stderr.strip())
                logger.error("   Please check the repository URL and network connectivity")
                return False
            
            logger.info("✅ Repository accessibility validation passed")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("❌ Repository access test timed out")
            logger.error("   Please check network connectivity")
            return False
        except FileNotFoundError:
            logger.error("❌ Git command not found")
            logger.error("   Please install git: apt update && apt install -y git")
            return False
        except Exception as e:
            logger.error(f"❌ Repository validation failed: {e}")
            return False

    def _validate_discord_connection(self) -> bool:
        """Test Discord token validity without starting the full bot."""
        try:
            import asyncio
            import discord
            
            async def test_connection():
                """Test Discord connection with a minimal client."""
                client = discord.Client(intents=discord.Intents.default())
                
                @client.event
                async def on_ready():
                    """Connection successful callback."""
                    logger.info(f"✅ Discord connection successful (logged in as {client.user})")
                    
                    # Test channel access if we can
                    accessible_channels = 0
                    for channel_id_str in self.channel_ids:
                        try:
                            channel_id = int(channel_id_str)
                            channel = client.get_channel(channel_id)
                            if channel is None:
                                # Try fetching the channel
                                channel = await client.fetch_channel(channel_id)
                            
                            if channel:
                                # Test if we can send messages to this channel
                                permissions = channel.permissions_for(channel.guild.me)
                                if permissions.send_messages:
                                    accessible_channels += 1
                                else:
                                    logger.warning(f"⚠️  No send permission for channel {channel_id} ({channel.name})")
                            else:
                                logger.warning(f"⚠️  Cannot access channel {channel_id} (not found or no permission)")
                        except Exception as e:
                            logger.warning(f"⚠️  Cannot validate channel {channel_id_str}: {e}")
                    
                    if accessible_channels > 0:
                        logger.info(f"✅ Can access {accessible_channels}/{len(self.channel_ids)} configured channels")
                    else:
                        logger.warning("⚠️  No accessible channels found - bot may not function properly")
                    
                    await client.close()
                
                try:
                    # Connect with a timeout
                    await asyncio.wait_for(client.start(self.discord_token), timeout=15.0)
                except asyncio.TimeoutError:
                    logger.error("❌ Discord connection test timed out")
                    return False
                except discord.LoginFailure:
                    logger.error("❌ Discord login failed - invalid token")
                    logger.error("   Please check your DISCORD_TOKEN in the .env file")
                    return False
                except discord.HTTPException as e:
                    if "401" in str(e):
                        logger.error("❌ Discord authentication failed - invalid token")
                        logger.error("   Please check your DISCORD_TOKEN in the .env file")
                    else:
                        logger.error(f"❌ Discord HTTP error: {e}")
                    return False
                except Exception as e:
                    logger.error(f"❌ Discord connection test failed: {e}")
                    return False
                
                return True
            
            # Run the connection test
            logger.info("🔍 Testing Discord connection...")
            return asyncio.run(test_connection())
            
        except ImportError:
            logger.error("❌ Discord.py not installed")
            logger.error("   Please install discord.py: pip install discord.py")
            return False
        except Exception as e:
            logger.error(f"❌ Discord connection validation failed: {e}")
            return False


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
