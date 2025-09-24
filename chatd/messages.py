"""
Message formatting for the chatd-internships bot.

This module handles formatting and comparing role data for Discord messages.
"""

from datetime import datetime
from typing import Dict, List, Any, Optional

# Import timezone support
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    try:
        from backports.zoneinfo import ZoneInfo  # Fallback for older Python
    except ImportError:
        # If no timezone support available, we'll use a simple offset
        ZoneInfo = None

from chatd.logging_utils import get_logger

# Get logger
logger = get_logger()


def format_epoch(val: float) -> str:
    """
    Format Unix timestamp (seconds) as a human-readable date string in the configured timezone.
    
    Args:
        val: Unix timestamp in seconds
        
    Returns:
        str: Formatted date string without leading zeros (e.g., 'September, 15 @ 7:13 PM EDT')
    """
    from chatd.config import config
    
    if ZoneInfo is not None:
        # Use proper timezone conversion
        utc_dt = datetime.fromtimestamp(val, tz=ZoneInfo('UTC'))
        
        # Determine target timezone
        if config.timezone:
            # Use configured timezone
            target_tz = ZoneInfo(config.timezone)
        else:
            # Use system default timezone
            import time
            system_tz_name = time.tzname[time.daylight] if time.daylight else time.tzname[0]
            try:
                # Try to get the system timezone using common methods
                import os
                if os.path.exists('/etc/timezone'):
                    with open('/etc/timezone', 'r') as f:
                        system_tz_name = f.read().strip()
                elif 'TZ' in os.environ:
                    system_tz_name = os.environ['TZ']
                else:
                    # Fallback to America/New_York if we can't determine system timezone
                    system_tz_name = 'America/New_York'
                
                target_tz = ZoneInfo(system_tz_name)
            except:
                # Final fallback to America/New_York
                target_tz = ZoneInfo('America/New_York')
        
        # Convert to target timezone
        local_dt = utc_dt.astimezone(target_tz)
        
        # Format with actual timezone name and without leading zeros
        # Use %-I on Unix systems to remove leading zero from hour
        try:
            formatted_time = local_dt.strftime('%B, %d @ %-I:%M %p')
        except ValueError:
            # Windows doesn't support %-I, so use %I and strip leading zero manually
            formatted_time = local_dt.strftime('%B, %d @ %I:%M %p')
            # Remove leading zero from hour manually
            parts = formatted_time.split(' @ ')
            if len(parts) == 2:
                time_part = parts[1]
                if time_part.startswith('0'):
                    time_part = time_part[1:]
                formatted_time = f"{parts[0]} @ {time_part}"
        
        # Get the actual timezone abbreviation (EST/EDT)
        tz_name = local_dt.tzname()
        return f"{formatted_time} {tz_name}"
    else:
        # Fallback: ZoneInfo not available (very rare on modern systems), display in UTC
        utc_dt = datetime.fromtimestamp(val)
        
        # Format without leading zero
        try:
            formatted_time = utc_dt.strftime('%B, %d @ %-I:%M %p')
        except ValueError:
            # Windows doesn't support %-I, so use %I and strip leading zero manually
            formatted_time = utc_dt.strftime('%B, %d @ %I:%M %p')
            parts = formatted_time.split(' @ ')
            if len(parts) == 2:
                time_part = parts[1]
                if time_part.startswith('0'):
                    time_part = time_part[1:]
                formatted_time = f"{parts[0]} @ {time_part}"
            
        return f"{formatted_time} UTC"


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
