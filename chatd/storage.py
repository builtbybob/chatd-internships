"""
Data storage for the chatd-internships bot.

This module handles persistent storage of data using various backends (file, DB, Redis).
"""

import json
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Type

from chatd.logging_utils import get_logger

# Get logger
logger = get_logger()


class Storage(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    def save_data(self, data: List[Dict[str, Any]]) -> bool:
        """
        Save data to storage.
        
        Args:
            data: Data to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def load_data(self) -> List[Dict[str, Any]]:
        """
        Load data from storage.
        
        Returns:
            List[Dict[str, Any]]: The loaded data
        """
        pass
    
    @abstractmethod
    def save_message_info(self, message_id: str, channel_id: str, role_key: str) -> bool:
        """
        Save information about a sent message.
        
        Args:
            message_id: Discord message ID
            channel_id: Discord channel ID
            role_key: Normalized role key
            
        Returns:
            bool: True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_messages_for_role(self, role_key: str) -> List[Dict[str, str]]:
        """
        Get all messages sent for a role.
        
        Args:
            role_key: Normalized role key
            
        Returns:
            List[Dict[str, str]]: List of message info dictionaries
        """
        pass


class FileStorage(Storage):
    """File-based storage backend."""
    
    def __init__(self, data_file: str = 'previous_data.json', messages_file: str = 'messages.json'):
        self.data_file = data_file
        self.messages_file = messages_file
        self._message_cache = self._load_messages()
    
    def save_data(self, data: List[Dict[str, Any]]) -> bool:
        """
        Save data to a JSON file.
        
        Args:
            data: Data to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(self.data_file, 'w') as file:
                json.dump(data, file)
            logger.debug(f"Saved {len(data)} items to {self.data_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving data to {self.data_file}: {e}")
            return False
    
    def load_data(self) -> List[Dict[str, Any]]:
        """
        Load data from a JSON file.
        
        Returns:
            List[Dict[str, Any]]: The loaded data
        """
        if not os.path.exists(self.data_file):
            logger.debug(f"Data file {self.data_file} does not exist, returning empty list")
            return []
            
        try:
            with open(self.data_file, 'r') as file:
                data = json.load(file)
            logger.debug(f"Loaded {len(data)} items from {self.data_file}")
            return data
        except Exception as e:
            logger.error(f"Error loading data from {self.data_file}: {e}")
            return []
    
    def _load_messages(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Load message information from a JSON file.
        
        Returns:
            Dict[str, List[Dict[str, str]]]: The loaded message info
        """
        if not os.path.exists(self.messages_file):
            return {}
            
        try:
            with open(self.messages_file, 'r') as file:
                data = json.load(file)
            return data
        except Exception as e:
            logger.error(f"Error loading message info from {self.messages_file}: {e}")
            return {}
    
    def _save_messages(self) -> bool:
        """
        Save message information to a JSON file.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(self.messages_file, 'w') as file:
                json.dump(self._message_cache, file)
            return True
        except Exception as e:
            logger.error(f"Error saving message info to {self.messages_file}: {e}")
            return False
    
    def save_message_info(self, message_id: str, channel_id: str, role_key: str) -> bool:
        """
        Save information about a sent message.
        
        Args:
            message_id: Discord message ID
            channel_id: Discord channel ID
            role_key: Normalized role key
            
        Returns:
            bool: True if successful, False otherwise
        """
        if role_key not in self._message_cache:
            self._message_cache[role_key] = []
            
        self._message_cache[role_key].append({
            'message_id': message_id,
            'channel_id': channel_id,
        })
        
        return self._save_messages()
    
    def get_messages_for_role(self, role_key: str) -> List[Dict[str, str]]:
        """
        Get all messages sent for a role.
        
        Args:
            role_key: Normalized role key
            
        Returns:
            List[Dict[str, str]]: List of message info dictionaries
        """
        return self._message_cache.get(role_key, [])


# Factory for creating storage instances
class StorageFactory:
    """Factory for creating storage instances."""
    
    @staticmethod
    def create_storage(storage_type: str = 'file', **kwargs) -> Storage:
        """
        Create a storage instance.
        
        Args:
            storage_type: Type of storage to create (file, redis, db)
            **kwargs: Additional arguments for the storage instance
            
        Returns:
            Storage: The created storage instance
        """
        if storage_type == 'file':
            return FileStorage(**kwargs)
        else:
            logger.warning(f"Unsupported storage type: {storage_type}, using file storage")
            return FileStorage(**kwargs)


# Singleton storage instance
_storage_instance: Optional[Storage] = None


def get_storage(storage_type: str = 'file', **kwargs) -> Storage:
    """
    Get the storage instance.
    
    Args:
        storage_type: Type of storage to create (file, redis, db)
        **kwargs: Additional arguments for the storage instance
        
    Returns:
        Storage: The storage instance
    """
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = StorageFactory.create_storage(storage_type, **kwargs)
    return _storage_instance
