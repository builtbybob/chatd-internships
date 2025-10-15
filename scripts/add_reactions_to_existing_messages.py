#!/usr/bin/env python3
"""
One-time migration script to add reactions to existing Discord messages.

This script reads the message_tracking table to find all Discord messages that were
posted before the reaction framework was implemented, then adds the configured
reactions (❓,📝) to each message.

Usage:
    python scripts/add_reactions_to_existing_messages.py [--dry-run] [--batch-size=50] [--delay=0.5]

The script includes:
- Dry run mode for testing
- Configurable batch processing to avoid Discord rate limits
- Optimized delay logic (brief delays between messages, not individual reactions)
- Proper error handling and logging
- Progress tracking and statistics
- Resume capability if interrupted
"""

import os
import sys
import argparse
import asyncio
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add the project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import discord
from discord.ext import commands

from chatd.config import Config
from chatd.database import DatabaseManager, MessageTracking, create_database_manager
from chatd.logging_utils import setup_logging


class ReactionMigration:
    """Handles adding reactions to existing Discord messages."""
    
    def __init__(self, config: Config, dry_run: bool = False, batch_size: int = 50, delay: float = 0.5):
        """
        Initialize the reaction migration handler.
        
        Args:
            config: Configuration object
            dry_run: If True, only simulate adding reactions without actually doing it
            batch_size: Number of messages to process in each batch
            delay: Delay in seconds between messages (not individual reactions)
        """
        self.config = config
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.delay = delay
        
        # Initialize database connection
        self.db_manager = create_database_manager(config)
        
        # Initialize Discord bot
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True  # Enable reaction intents for adding reactions
        self.bot = commands.Bot(command_prefix='!', intents=intents)
        
        # Statistics tracking
        self.stats = {
            'total_messages': 0,
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }
        
        # Get configured reactions
        self.reactions = config.message_reactions
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
    async def get_messages_to_process(self) -> List[Dict[str, Any]]:
        """
        Get all message tracking entries that need reactions added.
        
        Returns:
            List of message tracking data with job info
        """
        self.logger.info("🔍 Fetching messages from database...")
        
        try:
            with self.db_manager.session_scope() as session:
                # Query all message tracking entries with job posting info
                # Filter out any null message_id or channel_id entries for safety
                query = session.query(MessageTracking).filter(
                    MessageTracking.message_id.isnot(None),
                    MessageTracking.channel_id.isnot(None)
                ).all()
                
                messages = []
                for entry in query:
                    messages.append({
                        'job_id': str(entry.id),
                        'message_id': entry.message_id,
                        'channel_id': entry.channel_id,
                        'posted_at': entry.posted_at
                    })
                
                self.stats['total_messages'] = len(messages)
                self.logger.info(f"📊 Found {len(messages)} messages to process")
                return messages
                
        except Exception as e:
            self.logger.error(f"❌ Failed to fetch messages from database: {e}")
            raise
    
    async def process_message(self, message_data: Dict[str, Any]) -> bool:
        """
        Process a single message by adding reactions.
        
        Args:
            message_data: Message tracking data
            
        Returns:
            bool: True if successful, False otherwise
        """
        message_id = message_data['message_id']
        channel_id = message_data['channel_id']
        job_id = message_data['job_id']
        
        try:
            # Get the Discord channel
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                self.logger.warning(f"⚠️  Channel {channel_id} not found (message {message_id})")
                return False
            
            # Get the Discord message
            try:
                message = await channel.fetch_message(int(message_id))
            except discord.NotFound:
                self.logger.warning(f"⚠️  Message {message_id} not found in channel {channel_id}")
                return False
            except discord.Forbidden:
                self.logger.warning(f"⚠️  No permission to access message {message_id} in channel {channel_id}")
                return False
            
            if self.dry_run:
                self.logger.info(f"✅ DRY RUN: Would add reactions {self.reactions} to message {message_id} (job {job_id[:8]}...)")
                return True
            
            # Check if reactions already exist
            existing_reactions = [str(reaction.emoji) for reaction in message.reactions]
            reactions_to_add = [emoji for emoji in self.reactions if emoji not in existing_reactions]
            
            if not reactions_to_add:
                self.logger.info(f"⏭️  Message {message_id} already has all configured reactions, skipping")
                self.stats['skipped'] += 1
                return True
            
            # Add each reaction with minimal delay to respect rate limits
            for i, reaction in enumerate(reactions_to_add):
                try:
                    await message.add_reaction(reaction)
                    self.logger.debug(f"✅ Added reaction {reaction} to message {message_id}")
                    
                    # Only add a small delay between reactions (not the full delay)
                    if i < len(reactions_to_add) - 1:  # Don't delay after the last reaction
                        await asyncio.sleep(0.2)  # Small 200ms delay between reactions
                        
                except discord.HTTPException as e:
                    if e.status == 429:  # Rate limited
                        self.logger.warning(f"⏱️  Rate limited adding reaction {reaction} to message {message_id}, waiting...")
                        # Wait for the retry-after time if provided
                        retry_after = getattr(e, 'retry_after', self.delay * 2)
                        await asyncio.sleep(retry_after)
                        # Try once more
                        try:
                            await message.add_reaction(reaction)
                            self.logger.debug(f"✅ Added reaction {reaction} to message {message_id} (after rate limit)")
                        except discord.HTTPException:
                            self.logger.warning(f"⚠️  Failed to add reaction {reaction} to message {message_id} even after rate limit retry")
                    else:
                        self.logger.warning(f"⚠️  Failed to add reaction {reaction} to message {message_id}: {e}")
                    # Continue with other reactions even if one fails
            
            self.logger.info(f"✅ Successfully processed message {message_id} (job {job_id[:8]}...) - added {len(reactions_to_add)} reactions")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to process message {message_id}: {e}")
            self.stats['errors'].append(f"Message {message_id}: {str(e)}")
            return False
    
    async def run_migration(self) -> bool:
        """
        Run the complete reaction migration process.
        
        Returns:
            bool: True if migration completed successfully
        """
        start_time = time.time()
        
        try:
            self.logger.info("🚀 Starting reaction migration for existing messages...")
            
            if self.dry_run:
                self.logger.info("🧪 DRY RUN MODE - No actual changes will be made")
            
            self.logger.info(f"⚙️  Configuration: batch_size={self.batch_size}, delay={self.delay}s, reactions={self.reactions}")
            
            # Get all messages to process
            messages = await self.get_messages_to_process()
            
            if not messages:
                self.logger.info("✅ No messages found to process")
                return True
            
            # Process messages in batches
            for i in range(0, len(messages), self.batch_size):
                batch = messages[i:i + self.batch_size]
                batch_num = (i // self.batch_size) + 1
                total_batches = (len(messages) + self.batch_size - 1) // self.batch_size
                
                self.logger.info(f"📦 Processing batch {batch_num}/{total_batches} ({len(batch)} messages)")
                
                # Process each message in the batch
                for j, message_data in enumerate(batch):
                    self.stats['processed'] += 1
                    
                    success = await self.process_message(message_data)
                    if success:
                        self.stats['successful'] += 1
                    else:
                        self.stats['failed'] += 1
                    
                    # Small delay between messages to avoid overwhelming Discord API
                    if j < len(batch) - 1:  # Don't delay after the last message in batch
                        await asyncio.sleep(self.delay)
                    
                    # Progress update every 25 messages
                    if self.stats['processed'] % 25 == 0:
                        progress = (self.stats['processed'] / len(messages)) * 100
                        self.logger.info(f"📈 Progress: {self.stats['processed']}/{len(messages)} ({progress:.1f}%) - "
                                       f"Success: {self.stats['successful']}, Failed: {self.stats['failed']}, Skipped: {self.stats['skipped']}")
                
                # Add delay between batches to be gentle on Discord API
                if i + self.batch_size < len(messages):
                    await asyncio.sleep(self.delay)  # Brief pause between batches
            
            # Final statistics
            elapsed_time = time.time() - start_time
            self.logger.info("🎉 Migration completed!")
            self.logger.info(f"📊 Final Statistics:")
            self.logger.info(f"   Total messages: {self.stats['total_messages']}")
            self.logger.info(f"   Processed: {self.stats['processed']}")
            self.logger.info(f"   Successful: {self.stats['successful']}")
            self.logger.info(f"   Failed: {self.stats['failed']}")
            self.logger.info(f"   Skipped: {self.stats['skipped']}")
            self.logger.info(f"   Time elapsed: {elapsed_time:.1f} seconds")
            
            if self.stats['errors']:
                self.logger.warning(f"⚠️  {len(self.stats['errors'])} errors occurred:")
                for error in self.stats['errors'][:10]:  # Show first 10 errors
                    self.logger.warning(f"   {error}")
                if len(self.stats['errors']) > 10:
                    self.logger.warning(f"   ... and {len(self.stats['errors']) - 10} more errors")
            
            # Consider migration successful if most messages were processed
            success_rate = (self.stats['successful'] + self.stats['skipped']) / max(self.stats['total_messages'], 1)
            if success_rate >= 0.9:  # 90% success rate threshold
                self.logger.info("✅ Migration completed successfully")
                return True
            else:
                self.logger.error(f"❌ Migration had too many failures (success rate: {success_rate:.1%})")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Migration failed with error: {e}")
            return False
    
    async def start_bot_and_migrate(self):
        """Start the Discord bot and run the migration."""
        @self.bot.event
        async def on_ready():
            self.logger.info(f"🤖 Bot connected as {self.bot.user}")
            
            # Run the migration
            try:
                success = await self.run_migration()
                exit_code = 0 if success else 1
            except Exception as e:
                self.logger.error(f"❌ Migration failed: {e}")
                exit_code = 1
            
            # Close the bot and exit
            await self.bot.close()
            sys.exit(exit_code)
        
        # Start the bot
        await self.bot.start(self.config.discord_token)


def main():
    """Main entry point for the migration script."""
    parser = argparse.ArgumentParser(description="Add reactions to existing Discord messages")
    parser.add_argument('--dry-run', action='store_true', 
                       help='Simulate the migration without making changes')
    parser.add_argument('--batch-size', type=int, default=50,
                       help='Number of messages to process in each batch (default: 50)')
    parser.add_argument('--delay', type=float, default=0.5,
                       help='Delay in seconds between messages (default: 0.5)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose debug logging')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = 'DEBUG' if args.verbose else 'INFO'
    setup_logging(log_level=log_level)
    logger = logging.getLogger(__name__)
    
    # Load configuration
    try:
        config = Config()
        logger.info("✅ Configuration loaded successfully")
    except Exception as e:
        logger.error(f"❌ Failed to load configuration: {e}")
        return 1
    
    # Validate that we have the required tokens and settings
    if not config.discord_token:
        logger.error("❌ DISCORD_TOKEN not configured")
        return 1
    
    if not config.message_reactions:
        logger.error("❌ MESSAGE_REACTIONS not configured")
        return 1
    
    # Validate that MESSAGE_REACTIONS is properly configured
    if not isinstance(config.message_reactions, list) or len(config.message_reactions) == 0:
        logger.error("❌ MESSAGE_REACTIONS must be a non-empty list of emoji")
        return 1
    
    logger.info(f"🎯 Will add reactions: {config.message_reactions}")
    logger.info(f"🔧 Batch size: {args.batch_size}, Delay: {args.delay}s, Dry run: {args.dry_run}")
    
    # Create and run the migration
    migration = ReactionMigration(
        config=config,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        delay=args.delay
    )
    
    try:
        asyncio.run(migration.start_bot_and_migrate())
    except KeyboardInterrupt:
        logger.info("⏹️  Migration interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())