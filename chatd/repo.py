"""
Repository management for the chatd-internships bot.

This module handles cloning, updating, and reading data from the GitHub repository.
"""

import json
import os
from typing import Dict, List, Any

import git

from chatd.config import config
from chatd.logging_utils import get_logger

# Get logger
logger = get_logger()


def clone_or_update_repo() -> bool:
    """
    Clones a repository if it doesn't exist locally or updates it if it already exists.
    
    Returns:
        bool: True if the repo was cloned fresh or if the file was updated during pull.
              False if pull resulted in no changes to the target file.
    """
    logger.debug("Cloning or updating repository...")
    
    if os.path.exists(config.local_repo_path):
        try:
            repo = git.Repo(config.local_repo_path)
            # Store the current commit hash of the file
            old_hash = repo.git.rev_parse('HEAD:' + os.path.relpath(config.json_file_path, config.local_repo_path))
            
            # Pull the latest changes with timeout
            logger.debug("Pulling latest changes from repository...")
            repo.remotes.origin.pull(kill_after_timeout=30)  # 30 second timeout
            
            try:
                # Get new commit hash of the file
                new_hash = repo.git.rev_parse('HEAD:' + os.path.relpath(config.json_file_path, config.local_repo_path))
                # Compare hashes to see if file changed
                was_updated = old_hash != new_hash
                if was_updated:
                    logger.info("Repository pulled and listings file was updated.")
                else:
                    logger.debug("Repository pulled but listings file unchanged.")
                return was_updated
            except git.exc.GitCommandError:
                # If we can't get the new hash, assume file changed to be safe
                logger.warning("Could not determine if file changed, assuming updated")
                return True
                
        except git.exc.InvalidGitRepositoryError:
            logger.warning("Invalid git repository detected, re-cloning...")
            import shutil
            shutil.rmtree(config.local_repo_path)  # Remove entire directory tree
            repo = git.Repo.clone_from(config.repo_url, config.local_repo_path, kill_after_timeout=60)
            logger.info("Repository cloned fresh.")
            return True
        except Exception as e:
            logger.error(f"Error updating repository: {e}")
            raise
    else:
        logger.info("Repository not found locally, cloning...")
        repo = git.Repo.clone_from(config.repo_url, config.local_repo_path, kill_after_timeout=60)
        logger.info("Repository cloned fresh.")
        return True


def read_json() -> List[Dict[str, Any]]:
    """
    Read the JSON file from the repository.
    
    Returns:
        List[Dict[str, Any]]: The parsed JSON data
    """
    logger.debug(f"Reading JSON file from {config.json_file_path}...")
    
    with open(config.json_file_path, 'r') as file:
        data = json.load(file)
    
    logger.debug(f"JSON file read successfully, {len(data)} items loaded.")
    return data
