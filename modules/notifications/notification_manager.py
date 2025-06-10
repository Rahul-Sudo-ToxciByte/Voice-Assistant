#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Notification Manager for Jarvis Assistant

This module handles notifications, alerts, and reminders for the Jarvis assistant.
It supports multiple notification channels including voice, GUI, email, and desktop notifications.
"""

import os
import json
import logging
import time
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta
import threading
import queue

# For desktop notifications
try:
    import plyer.notification
    DESKTOP_NOTIFICATIONS_AVAILABLE = True
except ImportError:
    DESKTOP_NOTIFICATIONS_AVAILABLE = False

# For email notifications
try:
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False


class Notification:
    """Notification class to represent a single notification"""
    
    def __init__(self, title: str, message: str, level: str = "info", 
                 channel: str = "all", timestamp: Optional[datetime] = None,
                 expiry: Optional[datetime] = None, data: Optional[Dict[str, Any]] = None,
                 actions: Optional[List[Dict[str, Any]]] = None, id: Optional[str] = None):
        """Initialize a notification
        
        Args:
            title: Notification title
            message: Notification message
            level: Notification level (info, warning, error, critical)
            channel: Notification channel (voice, gui, email, desktop, all)
            timestamp: Notification timestamp (default: now)
            expiry: Notification expiry time (default: None)
            data: Additional data for the notification
            actions: List of actions that can be taken on the notification
            id: Unique identifier for the notification (default: auto-generated)
        """
        self.title = title
        self.message = message
        self.level = level.lower()
        self.channel = channel.lower()
        self.timestamp = timestamp or datetime.now()
        self.expiry = expiry
        self.data = data or {}
        self.actions = actions or []
        self.id = id or f"{int(time.time())}_{hash(title + message) % 10000}"
        self.read = False
        self.dismissed = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert notification to dictionary
        
        Returns:
            Dictionary representation of the notification
        """
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "level": self.level,
            "channel": self.channel,
            "timestamp": self.timestamp.isoformat(),
            "expiry": self.expiry.isoformat() if self.expiry else None,
            "data": self.data,
            "actions": self.actions,
            "read": self.read,
            "dismissed": self.dismissed
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Notification':
        """Create notification from dictionary
        
        Args:
            data: Dictionary representation of the notification
            
        Returns:
            Notification object
        """
        # Convert timestamp and expiry from ISO format to datetime
        timestamp = datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None
        expiry = datetime.fromisoformat(data["expiry"]) if data.get("expiry") else None
        
        # Create notification
        notification = cls(
            title=data["title"],
            message=data["message"],
            level=data.get("level", "info"),
            channel=data.get("channel", "all"),
            timestamp=timestamp,
            expiry=expiry,
            data=data.get("data", {}),
            actions=data.get("actions", []),
            id=data.get("id")
        )
        
        # Set read and dismissed status
        notification.read = data.get("read", False)
        notification.dismissed = data.get("dismissed", False)
        
        return notification
    
    def is_expired(self) -> bool:
        """Check if the notification is expired
        
        Returns:
            True if expired, False otherwise
        """
        if not self.expiry:
            return False
        
        return datetime.now() > self.expiry
    
    def mark_as_read(self):
        """Mark the notification as read"""
        self.read = True
    
    def dismiss(self):
        """Dismiss the notification"""
        self.dismissed = True


class Reminder(Notification):
    """Reminder class for scheduled notifications"""
    
    def __init__(self, title: str, message: str, scheduled_time: datetime,
                 repeat: Optional[str] = None, repeat_interval: Optional[int] = None,
                 repeat_until: Optional[datetime] = None, **kwargs):
        """Initialize a reminder
        
        Args:
            title: Reminder title
            message: Reminder message
            scheduled_time: Time when the reminder should be triggered
            repeat: Repeat pattern (none, daily, weekly, monthly, custom)
            repeat_interval: Interval for custom repeat (in minutes)
            repeat_until: End time for repeating reminders
            **kwargs: Additional arguments for Notification
        """
        super().__init__(title, message, **kwargs)
        self.scheduled_time = scheduled_time
        self.repeat = repeat
        self.repeat_interval = repeat_interval
        self.repeat_until = repeat_until
        self.triggered = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert reminder to dictionary
        
        Returns:
            Dictionary representation of the reminder
        """
        data = super().to_dict()
        data.update({
            "scheduled_time": self.scheduled_time.isoformat(),
            "repeat": self.repeat,
            "repeat_interval": self.repeat_interval,
            "repeat_until": self.repeat_until.isoformat() if self.repeat_until else None,
            "triggered": self.triggered
        })
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Reminder':
        """Create reminder from dictionary
        
        Args:
            data: Dictionary representation of the reminder
            
        Returns:
            Reminder object
        """
        # Extract reminder-specific fields
        scheduled_time = datetime.fromisoformat(data["scheduled_time"]) if data.get("scheduled_time") else None
        repeat = data.get("repeat")
        repeat_interval = data.get("repeat_interval")
        repeat_until = datetime.fromisoformat(data["repeat_until"]) if data.get("repeat_until") else None
        
        # Create base notification data
        notification_data = data.copy()
        for key in ["scheduled_time", "repeat", "repeat_interval", "repeat_until", "triggered"]:
            if key in notification_data:
                del notification_data[key]
        
        # Create notification
        notification = Notification.from_dict(notification_data)
        
        # Create reminder
        reminder = cls(
            title=notification.title,
            message=notification.message,
            scheduled_time=scheduled_time,
            repeat=repeat,
            repeat_interval=repeat_interval,
            repeat_until=repeat_until,
            level=notification.level,
            channel=notification.channel,
            timestamp=notification.timestamp,
            expiry=notification.expiry,
            data=notification.data,
            actions=notification.actions,
            id=notification.id
        )
        
        # Set read and dismissed status
        reminder.read = notification.read
        reminder.dismissed = notification.dismissed
        reminder.triggered = data.get("triggered", False)
        
        return reminder
    
    def is_due(self) -> bool:
        """Check if the reminder is due
        
        Returns:
            True if due, False otherwise
        """
        return datetime.now() >= self.scheduled_time
    
    def get_next_occurrence(self) -> Optional[datetime]:
        """Get the next occurrence of the reminder
        
        Returns:
            Next occurrence time, or None if no more occurrences
        """
        if not self.repeat or self.repeat == "none":
            return None
        
        if self.repeat_until and datetime.now() > self.repeat_until:
            return None
        
        now = datetime.now()
        
        if self.repeat == "daily":
            next_time = datetime(now.year, now.month, now.day, 
                               self.scheduled_time.hour, self.scheduled_time.minute, self.scheduled_time.second)
            if next_time <= now:
                next_time += timedelta(days=1)
            return next_time
        
        elif self.repeat == "weekly":
            days_ahead = self.scheduled_time.weekday() - now.weekday()
            if days_ahead <= 0:  # Target day already happened this week
                days_ahead += 7
            next_time = datetime(now.year, now.month, now.day, 
                               self.scheduled_time.hour, self.scheduled_time.minute, self.scheduled_time.second) + timedelta(days=days_ahead)
            return next_time
        
        elif self.repeat == "monthly":
            # Try to set the same day of the month
            try:
                next_time = datetime(now.year, now.month, self.scheduled_time.day,
                                   self.scheduled_time.hour, self.scheduled_time.minute, self.scheduled_time.second)
                if next_time <= now:
                    if now.month == 12:
                        next_time = datetime(now.year + 1, 1, self.scheduled_time.day,
                                           self.scheduled_time.hour, self.scheduled_time.minute, self.scheduled_time.second)
                    else:
                        next_time = datetime(now.year, now.month + 1, self.scheduled_time.day,
                                           self.scheduled_time.hour, self.scheduled_time.minute, self.scheduled_time.second)
                return next_time
            except ValueError:
                # Handle case where the day doesn't exist in the next month (e.g., 31st)
                if now.month == 12:
                    next_month = 1
                    next_year = now.year + 1
                else:
                    next_month = now.month + 1
                    next_year = now.year
                
                # Get the last day of the next month
                if next_month in [4, 6, 9, 11]:
                    last_day = 30
                elif next_month == 2:
                    if (next_year % 4 == 0 and next_year % 100 != 0) or (next_year % 400 == 0):
                        last_day = 29
                    else:
                        last_day = 28
                else:
                    last_day = 31
                
                return datetime(next_year, next_month, min(self.scheduled_time.day, last_day),
                               self.scheduled_time.hour, self.scheduled_time.minute, self.scheduled_time.second)
        
        elif self.repeat == "custom" and self.repeat_interval:
            # Add repeat_interval minutes to the last scheduled time
            next_time = self.scheduled_time + timedelta(minutes=self.repeat_interval)
            while next_time <= now:
                next_time += timedelta(minutes=self.repeat_interval)
            return next_time
        
        return None
    
    def trigger(self) -> 'Reminder':
        """Trigger the reminder and create the next occurrence if needed
        
        Returns:
            Next reminder occurrence, or None if no more occurrences
        """
        self.triggered = True
        
        # Check if we need to create a new reminder for the next occurrence
        next_time = self.get_next_occurrence()
        if not next_time:
            return None
        
        # Create a new reminder for the next occurrence
        next_reminder = Reminder(
            title=self.title,
            message=self.message,
            scheduled_time=next_time,
            repeat=self.repeat,
            repeat_interval=self.repeat_interval,
            repeat_until=self.repeat_until,
            level=self.level,
            channel=self.channel,
            data=self.data.copy(),
            actions=self.actions.copy()
        )
        
        return next_reminder


class NotificationManager:
    """Notification Manager for Jarvis Assistant"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the notification manager
        
        Args:
            config: Configuration dictionary for notification settings
        """
        self.logger = logging.getLogger("jarvis.notifications")
        self.config = config
        
        # Set up notification configuration
        self.enabled = config.get("enable_notifications", True)
        self.channels = config.get("notification_channels", ["voice", "gui"])
        self.max_history = config.get("max_notification_history", 100)
        self.reminder_check_interval = config.get("reminder_check_interval", 60)  # seconds
        
        # Set up data paths
        self.data_dir = os.path.join("data", "notifications")
        self.notifications_file = os.path.join(self.data_dir, "notifications.json")
        self.reminders_file = os.path.join(self.data_dir, "reminders.json")
        
        # Create data directory
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Initialize notification lists
        self.notifications: List[Notification] = []
        self.reminders: List[Reminder] = []
        
        # Load notifications and reminders
        self._load_notifications()
        self._load_reminders()
        
        # Set up notification queue and thread
        self.notification_queue = queue.Queue()
        self.running = False
        self.notification_thread = None
        
        # Callbacks
        self.voice_callback = None
        self.gui_callback = None
        self.on_notification = None
        
        # Email configuration
        self.email_config = config.get("email", {})
        
        self.logger.info(f"Notification manager initialized (enabled: {self.enabled})")
    
    def _load_notifications(self):
        """Load notifications from file"""
        if not os.path.exists(self.notifications_file):
            self.notifications = []
            return
        
        try:
            with open(self.notifications_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.notifications = [Notification.from_dict(item) for item in data]
            
            # Remove expired notifications
            self.notifications = [n for n in self.notifications if not n.is_expired()]
            
            # Limit to max history
            if len(self.notifications) > self.max_history:
                self.notifications = self.notifications[-self.max_history:]
            
            self.logger.info(f"Loaded {len(self.notifications)} notifications")
        
        except Exception as e:
            self.logger.error(f"Error loading notifications: {e}")
            self.notifications = []
    
    def _save_notifications(self):
        """Save notifications to file"""
        try:
            data = [n.to_dict() for n in self.notifications]
            
            with open(self.notifications_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        
        except Exception as e:
            self.logger.error(f"Error saving notifications: {e}")
    
    def _load_reminders(self):
        """Load reminders from file"""
        if not os.path.exists(self.reminders_file):
            self.reminders = []
            return
        
        try:
            with open(self.reminders_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.reminders = [Reminder.from_dict(item) for item in data]
            
            # Remove expired reminders
            current_time = datetime.now()
            self.reminders = [
                r for r in self.reminders 
                if not (r.triggered and (not r.repeat or r.repeat == "none")) and
                   not (r.repeat_until and current_time > r.repeat_until)
            ]
            
            self.logger.info(f"Loaded {len(self.reminders)} reminders")
        
        except Exception as e:
            self.logger.error(f"Error loading reminders: {e}")
            self.reminders = []
    
    def _save_reminders(self):
        """Save reminders to file"""
        try:
            data = [r.to_dict() for r in self.reminders]
            
            with open(self.reminders_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        
        except Exception as e:
            self.logger.error(f"Error saving reminders: {e}")
    
    def start(self):
        """Start the notification manager"""
        if not self.enabled:
            return
        
        if self.running:
            return
        
        self.running = True
        self.notification_thread = threading.Thread(target=self._notification_worker, daemon=True)
        self.notification_thread.start()
        
        self.logger.info("Notification manager started")
    
    def stop(self):
        """Stop the notification manager"""
        if not self.running:
            return
        
        self.running = False
        if self.notification_thread:
            self.notification_thread.join(timeout=2.0)
            self.notification_thread = None
        
        # Save notifications and reminders
        self._save_notifications()
        self._save_reminders()
        
        self.logger.info("Notification manager stopped")
    
    def _notification_worker(self):
        """Worker thread for processing notifications and checking reminders"""
        last_reminder_check = time.time()
        
        while self.running:
            try:
                # Check for new notifications in the queue
                try:
                    notification = self.notification_queue.get(timeout=1.0)
                    self._process_notification(notification)
                    self.notification_queue.task_done()
                except queue.Empty:
                    pass
                
                # Check for due reminders
                current_time = time.time()
                if current_time - last_reminder_check >= self.reminder_check_interval:
                    self._check_reminders()
                    last_reminder_check = current_time
            
            except Exception as e:
                self.logger.error(f"Error in notification worker: {e}")
                time.sleep(5)  # Sleep to avoid tight loop in case of persistent errors
    
    def _process_notification(self, notification: Notification):
        """Process a notification
        
        Args:
            notification: Notification to process
        """
        # Add to history
        self.notifications.append(notification)
        
        # Limit history size
        if len(self.notifications) > self.max_history:
            self.notifications = self.notifications[-self.max_history:]
        
        # Save notifications
        self._save_notifications()
        
        # Send to appropriate channels
        if notification.channel == "all":
            channels = self.channels
        else:
            channels = [notification.channel]
        
        for channel in channels:
            self._send_to_channel(notification, channel)
        
        # Call notification callback
        if self.on_notification:
            try:
                self.on_notification(notification)
            except Exception as e:
                self.logger.error(f"Error in notification callback: {e}")
    
    def _send_to_channel(self, notification: Notification, channel: str):
        """Send notification to a specific channel
        
        Args:
            notification: Notification to send
            channel: Channel to send to
        """
        try:
            if channel == "voice" and self.voice_callback:
                self.voice_callback(notification.title, notification.message, notification.level)
            
            elif channel == "gui" and self.gui_callback:
                self.gui_callback(notification)
            
            elif channel == "desktop" and DESKTOP_NOTIFICATIONS_AVAILABLE:
                plyer.notification.notify(
                    title=notification.title,
                    message=notification.message,
                    app_name="Jarvis",
                    timeout=10
                )
            
            elif channel == "email" and EMAIL_AVAILABLE:
                self._send_email_notification(notification)
        
        except Exception as e:
            self.logger.error(f"Error sending notification to {channel}: {e}")
    
    def _send_email_notification(self, notification: Notification):
        """Send notification via email
        
        Args:
            notification: Notification to send
        """
        if not EMAIL_AVAILABLE or not self.email_config:
            return
        
        try:
            # Get email configuration
            smtp_server = self.email_config.get("smtp_server")
            smtp_port = self.email_config.get("smtp_port", 587)
            smtp_username = self.email_config.get("smtp_username")
            smtp_password = self.email_config.get("smtp_password")
            from_email = self.email_config.get("from_email")
            to_email = self.email_config.get("to_email")
            
            if not all([smtp_server, smtp_username, smtp_password, from_email, to_email]):
                self.logger.error("Incomplete email configuration")
                return
            
            # Create message
            msg = MIMEMultipart()
            msg["From"] = from_email
            msg["To"] = to_email
            msg["Subject"] = f"Jarvis Notification: {notification.title}"
            
            # Add notification level to body
            body = f"Level: {notification.level.upper()}\n\n{notification.message}"
            msg.attach(MIMEText(body, "plain"))
            
            # Connect to SMTP server and send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)
            
            self.logger.info(f"Sent email notification: {notification.title}")
        
        except Exception as e:
            self.logger.error(f"Error sending email notification: {e}")
    
    def _check_reminders(self):
        """Check for due reminders"""
        if not self.reminders:
            return
        
        current_time = datetime.now()
        new_reminders = []
        triggered_reminders = []
        
        for reminder in self.reminders:
            if not reminder.triggered and reminder.is_due():
                # Create notification from reminder
                notification = Notification(
                    title=reminder.title,
                    message=reminder.message,
                    level=reminder.level,
                    channel=reminder.channel,
                    data=reminder.data.copy(),
                    actions=reminder.actions.copy()
                )
                
                # Add to notification queue
                self.notification_queue.put(notification)
                
                # Trigger reminder and get next occurrence
                next_reminder = reminder.trigger()
                if next_reminder:
                    new_reminders.append(next_reminder)
                
                triggered_reminders.append(reminder)
        
        # Update reminders list
        if triggered_reminders:
            # Remove triggered one-time reminders
            self.reminders = [
                r for r in self.reminders 
                if not (r in triggered_reminders and (not r.repeat or r.repeat == "none"))
            ]
            
            # Add new reminders for next occurrences
            self.reminders.extend(new_reminders)
            
            # Save reminders
            self._save_reminders()
    
    def notify(self, title: str, message: str, level: str = "info", channel: str = "all",
               expiry: Optional[datetime] = None, data: Optional[Dict[str, Any]] = None,
               actions: Optional[List[Dict[str, Any]]] = None) -> str:
        """Send a notification
        
        Args:
            title: Notification title
            message: Notification message
            level: Notification level (info, warning, error, critical)
            channel: Notification channel (voice, gui, email, desktop, all)
            expiry: Notification expiry time
            data: Additional data for the notification
            actions: List of actions that can be taken on the notification
            
        Returns:
            Notification ID
        """
        if not self.enabled:
            return ""
        
        # Create notification
        notification = Notification(
            title=title,
            message=message,
            level=level,
            channel=channel,
            expiry=expiry,
            data=data,
            actions=actions
        )
        
        # Add to queue
        self.notification_queue.put(notification)
        
        return notification.id
    
    def add_reminder(self, title: str, message: str, scheduled_time: datetime,
                    repeat: Optional[str] = None, repeat_interval: Optional[int] = None,
                    repeat_until: Optional[datetime] = None, level: str = "info",
                    channel: str = "all", data: Optional[Dict[str, Any]] = None,
                    actions: Optional[List[Dict[str, Any]]] = None) -> str:
        """Add a reminder
        
        Args:
            title: Reminder title
            message: Reminder message
            scheduled_time: Time when the reminder should be triggered
            repeat: Repeat pattern (none, daily, weekly, monthly, custom)
            repeat_interval: Interval for custom repeat (in minutes)
            repeat_until: End time for repeating reminders
            level: Notification level (info, warning, error, critical)
            channel: Notification channel (voice, gui, email, desktop, all)
            data: Additional data for the notification
            actions: List of actions that can be taken on the notification
            
        Returns:
            Reminder ID
        """
        if not self.enabled:
            return ""
        
        # Create reminder
        reminder = Reminder(
            title=title,
            message=message,
            scheduled_time=scheduled_time,
            repeat=repeat,
            repeat_interval=repeat_interval,
            repeat_until=repeat_until,
            level=level,
            channel=channel,
            data=data,
            actions=actions
        )
        
        # Add to reminders list
        self.reminders.append(reminder)
        
        # Save reminders
        self._save_reminders()
        
        return reminder.id
    
    def remove_reminder(self, reminder_id: str) -> bool:
        """Remove a reminder
        
        Args:
            reminder_id: ID of the reminder to remove
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        # Find reminder
        for i, reminder in enumerate(self.reminders):
            if reminder.id == reminder_id:
                # Remove reminder
                del self.reminders[i]
                
                # Save reminders
                self._save_reminders()
                
                return True
        
        return False
    
    def get_notifications(self, count: int = 10, include_read: bool = False) -> List[Dict[str, Any]]:
        """Get recent notifications
        
        Args:
            count: Number of notifications to return
            include_read: Whether to include read notifications
            
        Returns:
            List of notification dictionaries
        """
        if not self.enabled:
            return []
        
        # Filter notifications
        filtered = [n for n in self.notifications if include_read or not n.read]
        
        # Sort by timestamp (newest first)
        sorted_notifications = sorted(filtered, key=lambda n: n.timestamp, reverse=True)
        
        # Limit to count
        limited = sorted_notifications[:count]
        
        # Convert to dictionaries
        return [n.to_dict() for n in limited]
    
    def get_reminders(self, include_triggered: bool = False) -> List[Dict[str, Any]]:
        """Get active reminders
        
        Args:
            include_triggered: Whether to include triggered reminders
            
        Returns:
            List of reminder dictionaries
        """
        if not self.enabled:
            return []
        
        # Filter reminders
        filtered = [r for r in self.reminders if include_triggered or not r.triggered]
        
        # Sort by scheduled time
        sorted_reminders = sorted(filtered, key=lambda r: r.scheduled_time)
        
        # Convert to dictionaries
        return [r.to_dict() for r in sorted_reminders]
    
    def mark_as_read(self, notification_id: str) -> bool:
        """Mark a notification as read
        
        Args:
            notification_id: ID of the notification to mark as read
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        # Find notification
        for notification in self.notifications:
            if notification.id == notification_id:
                # Mark as read
                notification.mark_as_read()
                
                # Save notifications
                self._save_notifications()
                
                return True
        
        return False
    
    def dismiss_notification(self, notification_id: str) -> bool:
        """Dismiss a notification
        
        Args:
            notification_id: ID of the notification to dismiss
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        # Find notification
        for notification in self.notifications:
            if notification.id == notification_id:
                # Dismiss notification
                notification.dismiss()
                
                # Save notifications
                self._save_notifications()
                
                return True
        
        return False
    
    def clear_notifications(self, older_than: Optional[datetime] = None) -> int:
        """Clear notifications
        
        Args:
            older_than: Clear notifications older than this time
            
        Returns:
            Number of notifications cleared
        """
        if not self.enabled:
            return 0
        
        original_count = len(self.notifications)
        
        if older_than:
            # Remove notifications older than the specified time
            self.notifications = [n for n in self.notifications if n.timestamp >= older_than]
        else:
            # Remove all notifications
            self.notifications = []
        
        # Save notifications
        self._save_notifications()
        
        return original_count - len(self.notifications)
    
    def register_callbacks(self, voice_callback: Optional[Callable[[str, str, str], None]] = None,
                          gui_callback: Optional[Callable[[Notification], None]] = None,
                          on_notification: Optional[Callable[[Notification], None]] = None):
        """Register callback functions
        
        Args:
            voice_callback: Callback for voice notifications
            gui_callback: Callback for GUI notifications
            on_notification: Callback for all notifications
        """
        self.voice_callback = voice_callback
        self.gui_callback = gui_callback
        self.on_notification = on_notification
    
    def shutdown(self):
        """Shutdown the notification manager"""
        self.stop()
        self.logger.info("Notification manager shut down")