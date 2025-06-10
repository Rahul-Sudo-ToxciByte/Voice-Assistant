#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Always-On Voice Activation Plugin for Jarvis Assistant

This plugin enables Jarvis to respond to voice commands even when the screen is off
or the system is in low-power mode. It monitors system state and adjusts the voice
engine accordingly to maintain wake word detection while minimizing resource usage.
"""

import os
import logging
import threading
import time
from typing import Dict, Any, Optional

# Import for system monitoring
import psutil

# Import for Windows-specific functionality
try:
    import win32api
    import win32con
    import win32gui
    import win32process
    import pywintypes
    from ctypes import windll
    WINDOWS_SUPPORT = True
except ImportError:
    WINDOWS_SUPPORT = False

# Import for keyboard and mouse monitoring
try:
    from pynput import mouse, keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

# Import Plugin base class
from core.plugin import Plugin


class AlwaysOnPlugin(Plugin):
    """Always-On Voice Activation Plugin for Jarvis Assistant"""
    
    def __init__(self, assistant):
        """Initialize the Always-On plugin
        
        Args:
            assistant: The Jarvis assistant instance
        """
        super().__init__(assistant)
        self.logger = logging.getLogger("jarvis.plugins.always_on")
        
        # Check if required libraries are available
        if not WINDOWS_SUPPORT and os.name == 'nt':
            self.logger.error("Windows support libraries not available. Please install with 'pip install pywin32'")
        
        if not PYNPUT_AVAILABLE:
            self.logger.error("Pynput library not available. Please install with 'pip install pynput'")
        
        # Get plugin configuration
        self.config = self.assistant.config.get("plugins", {}).get("always_on", {})
        self.enabled = self.config.get("enabled", True)
        self.low_power_mode = self.config.get("low_power_mode", True)
        self.wake_on_notification = self.config.get("wake_on_notification", True)
        self.screen_off_timeout = self.config.get("screen_off_timeout", 30)  # seconds
        self.power_save_threshold = self.config.get("power_save_threshold", 20)  # percentage
        
        # System state tracking
        self.screen_on = True
        self.last_activity_time = time.time()
        self.in_low_power_mode = False
        self.battery_level = 100
        self.on_ac_power = True
        
        # Thread control
        self.running = False
        self.monitor_thread = None
        
        # References to system components
        self.voice_engine = None
        self.system_monitor = None
        self.notification_manager = None
        
        # Listeners
        self.keyboard_listener = None
        self.mouse_listener = None
        
        self.logger.info("Always-On plugin initialized")
    
    def activate(self):
        """Activate the Always-On plugin"""
        # Get references to required system components
        self.voice_engine = self.assistant.get_module("voice_engine")
        self.system_monitor = self.assistant.get_module("system_monitor")
        self.notification_manager = self.assistant.get_module("notifications")
        
        if not self.voice_engine:
            self.logger.error("Voice engine not available, cannot activate Always-On plugin")
            return False
        
        # Start activity monitoring
        if PYNPUT_AVAILABLE:
            self._start_activity_monitoring()
        
        # Start system monitoring thread
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        # Register notification callback if notification manager is available
        if self.notification_manager and self.wake_on_notification:
            self.notification_manager.register_callback(self._notification_callback)
        
        # Register commands
        self._register_commands()
        
        # Register intents
        self._register_intents()
        
        self.logger.info("Always-On plugin activated")
        return True
    
    def _start_activity_monitoring(self):
        """Start monitoring keyboard and mouse activity"""
        try:
            # Set up keyboard listener
            self.keyboard_listener = keyboard.Listener(
                on_press=self._on_activity,
                on_release=self._on_activity
            )
            self.keyboard_listener.start()
            
            # Set up mouse listener
            self.mouse_listener = mouse.Listener(
                on_move=self._on_activity,
                on_click=self._on_activity,
                on_scroll=self._on_activity
            )
            self.mouse_listener.start()
            
            self.logger.info("Activity monitoring started")
        except Exception as e:
            self.logger.error(f"Failed to start activity monitoring: {e}")
    
    def _on_activity(self, *args, **kwargs):
        """Callback for keyboard and mouse activity"""
        self.last_activity_time = time.time()
        
        # If screen was off, turn it back on
        if not self.screen_on:
            self._wake_screen()
    
    def _monitor_loop(self):
        """Background thread to monitor system state and adjust voice engine"""
        while self.running:
            try:
                # Update system state
                self._update_system_state()
                
                # Check if screen should be turned off
                current_time = time.time()
                if self.screen_on and (current_time - self.last_activity_time) > self.screen_off_timeout:
                    self._screen_off()
                
                # Adjust voice engine based on system state
                self._adjust_voice_engine()
                
                # Sleep for a short time
                time.sleep(1.0)
            
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {e}")
                time.sleep(5.0)  # Wait before retrying on error
    
    def _update_system_state(self):
        """Update system state information"""
        # Update battery information
        if hasattr(psutil, 'sensors_battery'):
            battery = psutil.sensors_battery()
            if battery:
                self.battery_level = battery.percent
                self.on_ac_power = battery.power_plugged
        
        # Check screen state on Windows
        if os.name == 'nt' and WINDOWS_SUPPORT:
            try:
                # Check if screen saver is active
                screen_saver_active = win32api.GetSystemPowerStatus()[0] == win32con.MONITOR_STATE_OFF
                
                # Update screen state if changed
                if self.screen_on and screen_saver_active:
                    self.screen_on = False
                    self.logger.info("Screen turned off")
                elif not self.screen_on and not screen_saver_active:
                    self.screen_on = True
                    self.logger.info("Screen turned on")
            except Exception as e:
                self.logger.error(f"Error checking screen state: {e}")
    
    def _screen_off(self):
        """Handle screen turning off"""
        self.screen_on = False
        self.logger.info("Screen turned off due to inactivity")
        
        # Enter low power mode if enabled
        if self.low_power_mode and not self.in_low_power_mode:
            self._enter_low_power_mode()
    
    def _wake_screen(self):
        """Wake the screen"""
        self.screen_on = True
        self.logger.info("Waking screen")
        
        # Exit low power mode if active
        if self.in_low_power_mode:
            self._exit_low_power_mode()
        
        # Wake screen on Windows
        if os.name == 'nt' and WINDOWS_SUPPORT:
            try:
                # Simulate mouse movement to wake screen
                windll.user32.mouse_event(
                    win32con.MOUSEEVENTF_MOVE,
                    0, 0, 0, 0
                )
            except Exception as e:
                self.logger.error(f"Error waking screen: {e}")
    
    def _enter_low_power_mode(self):
        """Enter low power mode to conserve resources"""
        self.in_low_power_mode = True
        self.logger.info("Entering low power mode")
        
        # Adjust voice engine for low power mode
        if self.voice_engine:
            # Reduce wake word detection sensitivity to save power
            # but keep it running to respond to commands
            self.voice_engine.set_low_power_mode(True)
    
    def _exit_low_power_mode(self):
        """Exit low power mode"""
        self.in_low_power_mode = False
        self.logger.info("Exiting low power mode")
        
        # Restore voice engine to normal operation
        if self.voice_engine:
            self.voice_engine.set_low_power_mode(False)
    
    def _adjust_voice_engine(self):
        """Adjust voice engine based on current system state"""
        if not self.voice_engine:
            return
        
        # Ensure wake word detection is always running
        if not self.voice_engine.is_wake_word_detection_running():
            self.logger.info("Restarting wake word detection")
            self.voice_engine.start_wake_word_detection()
        
        # Adjust for battery level
        if not self.on_ac_power and self.battery_level < self.power_save_threshold:
            # Enable extreme power saving if battery is low
            if not self.in_low_power_mode:
                self._enter_low_power_mode()
        elif self.in_low_power_mode and self.screen_on:
            # Exit low power mode if screen is on
            self._exit_low_power_mode()
    
    def _notification_callback(self, notification):
        """Handle notifications
        
        Args:
            notification: The notification object
        """
        if not self.wake_on_notification:
            return
        
        # Check if this is an important notification
        level = notification.get("level", "")
        channel = notification.get("channel", "")
        
        # Wake screen for important notifications
        if level in ["critical", "warning"] or channel == "email":
            if not self.screen_on:
                self._wake_screen()
                
                # Speak notification if voice engine is available
                if self.voice_engine:
                    title = notification.get("title", "Important notification")
                    message = notification.get("message", "")
                    self.voice_engine.speak(f"{title}. {message}")
    
    def _register_commands(self):
        """Register Always-On commands"""
        self.register_command(
            "always_on_status",
            self._cmd_always_on_status,
            "Check Always-On status",
            "Check the status of the Always-On voice activation system",
            "always_on_status",
            ["always_on_status"],
            {}
        )
        
        self.register_command(
            "toggle_always_on",
            self._cmd_toggle_always_on,
            "Toggle Always-On mode",
            "Enable or disable the Always-On voice activation system",
            "toggle_always_on [enable]",
            ["toggle_always_on", "toggle_always_on true"],
            {
                "enable": {
                    "type": "boolean",
                    "description": "Enable or disable Always-On mode",
                    "default": None
                }
            }
        )
    
    def _register_intents(self):
        """Register Always-On intents"""
        self.register_intent(
            "always_on_status",
            self._intent_always_on_status,
            [
                "is always on mode active",
                "check always on status",
                "is the system in low power mode",
                "are you listening when my screen is off"
            ]
        )
        
        self.register_intent(
            "toggle_always_on",
            self._intent_toggle_always_on,
            [
                "turn on always listening mode",
                "enable always on voice activation",
                "disable always on mode",
                "stop listening when screen is off",
                "keep listening when screen is off"
            ]
        )
    
    def _cmd_always_on_status(self):
        """Command to check Always-On status
            
        Returns:
            Command result
        """
        status = {
            "enabled": self.enabled,
            "screen_on": self.screen_on,
            "in_low_power_mode": self.in_low_power_mode,
            "battery_level": self.battery_level,
            "on_ac_power": self.on_ac_power,
            "wake_word_active": self.voice_engine.is_wake_word_detection_running() if self.voice_engine else False
        }
        
        return {
            "success": True,
            "message": "Always-On status retrieved",
            "status": status
        }
    
    def _cmd_toggle_always_on(self, enable=None):
        """Command to toggle Always-On mode
        
        Args:
            enable: Enable or disable Always-On mode
            
        Returns:
            Command result
        """
        # Toggle if not specified
        if enable is None:
            enable = not self.enabled
        
        # Update enabled state
        self.enabled = enable
        
        # Update configuration
        if "plugins" not in self.assistant.config:
            self.assistant.config["plugins"] = {}
        if "always_on" not in self.assistant.config["plugins"]:
            self.assistant.config["plugins"]["always_on"] = {}
        
        self.assistant.config["plugins"]["always_on"]["enabled"] = enable
        self.assistant.save_config()
        
        # Adjust voice engine based on new state
        if enable:
            if self.voice_engine and not self.voice_engine.is_wake_word_detection_running():
                self.voice_engine.start_wake_word_detection()
        
        return {
            "success": True,
            "message": f"Always-On mode {'enabled' if enable else 'disabled'}"
        }
    
    def _intent_always_on_status(self, text, entities):
        """Handle Always-On status intent
        
        Args:
            text: Intent text
            entities: Extracted entities
            
        Returns:
            Response text
        """
        result = self._cmd_always_on_status()
        
        if result["success"]:
            status = result["status"]
            
            if status["enabled"]:
                if status["screen_on"]:
                    return "Always-On mode is active. I'm currently in normal mode with the screen on."
                else:
                    if status["in_low_power_mode"]:
                        return "Always-On mode is active. The screen is off and I'm in low power mode, but still listening for wake words."
                    else:
                        return "Always-On mode is active. The screen is off but I'm still in normal mode."
            else:
                return "Always-On mode is currently disabled."
        else:
            return "Sorry, I couldn't check the Always-On status."
    
    def _intent_toggle_always_on(self, text, entities):
        """Handle toggle Always-On intent
        
        Args:
            text: Intent text
            entities: Extracted entities
            
        Returns:
            Response text
        """
        # Determine if we should enable or disable
        enable = None
        if any(word in text.lower() for word in ["enable", "turn on", "activate", "keep"]):
            enable = True
        elif any(word in text.lower() for word in ["disable", "turn off", "deactivate", "stop"]):
            enable = False
        
        # Call command
        result = self._cmd_toggle_always_on(enable)
        
        if result["success"]:
            if enable or (enable is None and self.enabled):
                return "Always-On mode is now enabled. I'll keep listening for wake words even when the screen is off."
            else:
                return "Always-On mode is now disabled. I'll stop listening when the screen is off."
        else:
            return "Sorry, I couldn't change the Always-On mode."
    
    def shutdown(self):
        """Shutdown the Always-On plugin"""
        self.running = False
        
        # Stop activity monitoring
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        
        if self.mouse_listener:
            self.mouse_listener.stop()
        
        # Wait for monitor thread to finish
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
        
        # Unregister notification callback
        if self.notification_manager and self.wake_on_notification:
            self.notification_manager.unregister_callback(self._notification_callback)
        
        self.logger.info("Always-On plugin shut down")