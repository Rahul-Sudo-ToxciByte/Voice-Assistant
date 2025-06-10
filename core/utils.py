# -*- coding: utf-8 -*-

"""
Utility Functions

This module provides utility functions used throughout the Jarvis system.
"""

import re
import datetime
from typing import Dict, List, Any, Optional, Tuple, Union

def extract_entities(text: str) -> Dict[str, Any]:
    """
    Extract entities from text using simple pattern matching.
    
    Args:
        text: The text to extract entities from
        
    Returns:
        Dictionary of extracted entities
    """
    entities = {}
    
    # Extract person names (simple implementation)
    person_match = re.search(r"for (\w+)", text, re.IGNORECASE)
    if person_match:
        entities["person"] = person_match.group(1)
    
    # Extract locations (simple implementation)
    location_match = re.search(r"in (\w+)", text, re.IGNORECASE)
    if location_match:
        entities["location"] = location_match.group(1)
    
    # Extract dates (simple implementation)
    date_match = re.search(r"on (\w+ \d+)", text, re.IGNORECASE)
    if date_match:
        entities["date"] = date_match.group(1)
    
    # Extract times (simple implementation)
    time_match = re.search(r"at (\d+:\d+)", text, re.IGNORECASE)
    if time_match:
        entities["time"] = time_match.group(1)
    
    return entities

def extract_datetime(text: str) -> Optional[datetime.datetime]:
    """
    Extract datetime from text using simple pattern matching.
    
    Args:
        text: The text to extract datetime from
        
    Returns:
        Extracted datetime or None if not found
    """
    # This is a simplified implementation
    # In a real system, you would use a more sophisticated approach
    
    # Try to match common date/time patterns
    patterns = [
        # MM/DD/YYYY HH:MM
        r"(\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2})",
        # YYYY-MM-DD HH:MM
        r"(\d{4}-\d{1,2}-\d{1,2} \d{1,2}:\d{2})",
        # Month DD, YYYY HH:MM
        r"(\w+ \d{1,2}, \d{4} \d{1,2}:\d{2})"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                # Try different formats
                formats = [
                    "%m/%d/%Y %H:%M",
                    "%Y-%m-%d %H:%M",
                    "%B %d, %Y %H:%M"
                ]
                
                for fmt in formats:
                    try:
                        return datetime.datetime.strptime(match.group(1), fmt)
                    except ValueError:
                        continue
            except Exception:
                pass
    
    # Handle relative times like "tomorrow at 3pm"
    if "tomorrow" in text.lower():
        time_match = re.search(r"(\d{1,2})(am|pm)", text.lower())
        if time_match:
            hour = int(time_match.group(1))
            if time_match.group(2) == "pm" and hour < 12:
                hour += 12
            
            now = datetime.datetime.now()
            tomorrow = now + datetime.timedelta(days=1)
            return datetime.datetime(tomorrow.year, tomorrow.month, tomorrow.day, hour, 0)
    
    return None

def format_datetime(dt: datetime.datetime) -> str:
    """
    Format a datetime object as a human-readable string.
    
    Args:
        dt: The datetime to format
        
    Returns:
        Formatted datetime string
    """
    return dt.strftime("%A, %B %d, %Y at %I:%M %p")

def get_datetime_obj(date_str: str, time_str: Optional[str] = None) -> Optional[datetime.datetime]:
    """
    Convert date and time strings to a datetime object.
    
    Args:
        date_str: The date string
        time_str: The time string (optional)
        
    Returns:
        Datetime object or None if conversion fails
    """
    try:
        # Try different date formats
        date_formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%B %d, %Y",
            "%b %d, %Y"
        ]
        
        dt = None
        for fmt in date_formats:
            try:
                dt = datetime.datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue
        
        if dt is None:
            return None
        
        # If time is provided, update the datetime
        if time_str:
            time_formats = [
                "%H:%M",
                "%I:%M %p",
                "%I:%M%p"
            ]
            
            for fmt in time_formats:
                try:
                    time_obj = datetime.datetime.strptime(time_str, fmt)
                    dt = dt.replace(hour=time_obj.hour, minute=time_obj.minute)
                    break
                except ValueError:
                    continue
        
        return dt
    except Exception:
        return None