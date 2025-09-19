"""
Repository management for the chatd-internships bot.

This module handles cloning, updating, and reading data from the GitHub repository.
"""

import json
import os
from typing import Dict, List, Any, Union, Optional

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
            
            # Pull the latest changes
            repo.remotes.origin.pull()
            
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
            os.rmdir(config.local_repo_path)  # Remove invalid directory
            git.Repo.clone_from(config.repo_url, config.local_repo_path)
            logger.info("Repository cloned fresh.")
            return True
    else:
        git.Repo.clone_from(config.repo_url, config.local_repo_path)
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


def normalize_role_key(role: Union[Dict[str, Any], str]) -> str:
    """
    Create a stable normalized key for a role using company, title and URL (if available).
    This reduces mismatches caused by whitespace, capitalization or minor title changes.
    
    Args:
        role: Role data as a dictionary or string
        
    Returns:
        str: Normalized role key
    """
    def norm(s: Optional[str]) -> str:
        return (s or "").strip().lower()

    if isinstance(role, str):
        return role.strip().lower()

    url = role.get('url') if isinstance(role, dict) else None
    if url:
        return f"{norm(role.get('company_name'))}__{norm(role.get('title'))}__{url}"
    return f"{norm(role.get('company_name'))}__{norm(role.get('title'))}"
