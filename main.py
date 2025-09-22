#!/usr/bin/env python3
"""
Entry point for the chatd-internships bot.

This script initializes the bot and runs it.
"""

import sys
import signal

from chatd.config import config, validate_config
from chatd.logging_utils import get_logger, setup_signal_handlers
from chatd.bot import run_bot

# Initialize logger
logger = get_logger()


def signal_handler(sig, frame):
    """Handle graceful shutdown."""
    logger.info("Shutting down gracefully...")
    sys.exit(0)


def main():
    """Main entry point."""
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Set up signal handlers for log level changes
    setup_signal_handlers()
    
    logger.info("🚀 Starting ChatD Internships Bot...")
    
    # Validate configuration
    try:
        logger.info("🔧 Validating configuration...")
        if not validate_config():
            logger.error("💥 Configuration validation failed. Cannot start bot.")
            logger.error("   Please fix the configuration issues above and try again.")
            sys.exit(1)
        logger.info("✅ Configuration validation completed successfully")
    except Exception as e:
        logger.error(f"💥 Configuration validation encountered an error: {e}")
        logger.error("   Please check your configuration and try again.")
        sys.exit(1)
    
    try:
        logger.info("🤖 Starting Discord bot...")
        # Run the bot
        run_bot()
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Error running bot: {e}")
        logger.error("   Check the logs above for more details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
