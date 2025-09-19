"""
Message formatting for the chatd-internships bot.

This module handles formatting and comparing role data for Discord messages.
"""

from datetime import datetime
from typing import Dict, List, Any, Optional

from chatd.logging_utils import get_logger

# Get logger
logger = get_logger()


def format_epoch(val: float) -> str:
    """
    Format Unix timestamp (seconds) as a human-readable date string.
    
    Args:
        val: Unix timestamp in seconds
        
    Returns:
        str: Formatted date string (e.g., 'September, 15 @ 07:13 PM')
    """
    return datetime.fromtimestamp(val).strftime('%B, %d @ %I:%M %p')


def format_message(role: Dict[str, Any]) -> str:
    """
    Format a role for Discord message.
    
    Args:
        role: Role data dictionary
        
    Returns:
        str: Formatted message string for Discord
    """
    # Build safe values
    title = role.get('title', '').strip()
    company = role.get('company_name', '').strip()
    url = role.get('url', '').strip() if role.get('url') else ''
    locations = role.get('locations') or []
    location_str = ' | '.join(locations) if locations else 'Not specified'
    terms = role.get('terms') or []
    term_str = ' | '.join(terms) if terms else 'Not specified'
    sponsorship = role.get('sponsorship')

    # Format the posting date
    posted_on = format_epoch(role.get('date_posted'))

    # Header link uses angle-bracketed URL per example
    header_link = f"(<{url}>)" if url else ""

    parts = []
    parts.append(f">>> ## {company}")
    parts.append(f"## [{title}]{header_link}")

    # Add locations
    parts.append("### Locations: ")
    parts.append(location_str)

    # Add terms
    if len(terms) > 0 and term_str != 'Summer 2026':
        parts.append(f"### Terms: `{term_str}`")

    # Conditionally include Sponsorship
    if sponsorship and str(sponsorship).strip().lower() != 'other':
        parts.append(f"### Sponsorship: `{sponsorship}`")

    parts.append(f"Posted on: {posted_on}")

    return "\n".join(parts)


def compare_roles(old_role: Dict[str, Any], new_role: Dict[str, Any]) -> List[str]:
    """
    Compare two roles and return a list of changes.
    
    Args:
        old_role: Original role data
        new_role: Updated role data
        
    Returns:
        List[str]: List of changes between the roles
    """
    changes = []
    for key in new_role:
        if old_role.get(key) != new_role.get(key):
            changes.append(f"{key} changed from {old_role.get(key)} to {new_role.get(key)}")
    return changes
