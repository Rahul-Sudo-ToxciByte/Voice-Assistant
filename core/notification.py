# -*- coding: utf-8 -*-

"""
Notification System

This module provides the notification system for Jarvis.
"""

import time
from typing import Dict, Any, Optional
from modules.voice_commands_new import VoiceCommandSystem

class Notification:
    """
    Notification class for Jarvis.
    
    This class represents a notification that can be displayed to the user
    or processed by the system.
    """
    
    def __init__(self, title: str, message: str, source: str, 
                 notification_type: str = "info", data: Optional[Dict[str, Any]] = None):
        """
        Initialize a notification.
        
        Args:
            title: The notification title
            message: The notification message
            source: The source of the notification (e.g., plugin name)
            notification_type: The type of notification (info, warning, error, etc.)
            data: Additional data associated with the notification
        """
        self.title = title
        self.message = message
        self.source = source
        self.notification_type = notification_type
        self.data = data or {}
        self.timestamp = time.time()
        self.read = False
        self.id = f"{self.source}_{self.timestamp}_{id(self)}"
    
    def mark_as_read(self):
        """
        Mark the notification as read.
        """
        self.read = True
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the notification to a dictionary.
        
        Returns:
            Dictionary representation of the notification
        """
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "source": self.source,
            "type": self.notification_type,
            "data": self.data,
            "timestamp": self.timestamp,
            "read": self.read
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Notification':
        """
        Create a notification from a dictionary.
        
        Args:
            data: Dictionary containing notification data
            
        Returns:
            Notification object
        """
        notification = cls(
            title=data.get("title", ""),
            message=data.get("message", ""),
            source=data.get("source", ""),
            notification_type=data.get("type", "info"),
            data=data.get("data", {})
        )
        notification.timestamp = data.get("timestamp", time.time())
        notification.read = data.get("read", False)
        notification.id = data.get("id", notification.id)
        return notification