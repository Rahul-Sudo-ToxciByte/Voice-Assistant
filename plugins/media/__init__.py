#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Media Controller Plugin for Jarvis Assistant

This plugin provides media playback control functionality using keyboard shortcuts
and application-specific controls.
"""

import os
import sys
import time
import logging
import subprocess
from typing import Dict, List, Any, Optional, Tuple

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

# Windows-specific imports
if sys.platform == "win32":
    try:
        import win32gui
        import win32process
        import win32api
        import win32con
        WINDOWS_API_AVAILABLE = True
    except ImportError:
        WINDOWS_API_AVAILABLE = False
else:
    WINDOWS_API_AVAILABLE = False

from modules.plugins.plugin_manager import Plugin


class MediaControllerPlugin(Plugin):
    """Media controller plugin for Jarvis Assistant"""
    
    def _initialize(self):
        """Initialize the plugin"""
        self.logger.info("Initializing media controller plugin")
        
        # Check if pyautogui is available
        if not PYAUTOGUI_AVAILABLE:
            self.error = "The 'pyautogui' package is required for the media controller plugin"
            self.logger.error(self.error)
            return False
        
        # Get configuration
        self.use_keyboard_shortcuts = self.config.get("use_keyboard_shortcuts", True)
        self.default_player = self.config.get("default_player", "system")
        self.volume_step = self.config.get("volume_step", 10)
        self.launch_player_on_command = self.config.get("launch_player_on_command", True)
        
        # Define keyboard shortcuts for media control
        self.media_keys = {
            "play_pause": "playpause",
            "next": "nexttrack",
            "previous": "prevtrack",
            "stop": "stop",
            "volume_up": "volumeup",
            "volume_down": "volumedown",
            "mute": "volumemute"
        }
        
        # Define player-specific commands
        self.player_commands = {
            "vlc": {
                "launch": "vlc",
                "process_name": "vlc.exe" if sys.platform == "win32" else "vlc"
            },
            "spotify": {
                "launch": "spotify",
                "process_name": "Spotify.exe" if sys.platform == "win32" else "spotify"
            },
            "windows_media_player": {
                "launch": "wmplayer",
                "process_name": "wmplayer.exe"
            }
        }
        
        # Initialize state
        self.current_player = None
        self.is_playing = False
        
        self.logger.info("Media controller plugin initialized successfully")
        return True
    
    def _is_player_running(self, player: str) -> bool:
        """Check if a media player is running
        
        Args:
            player: Player name
            
        Returns:
            True if player is running, False otherwise
        """
        if player == "system":
            # Can't check for system-wide media player
            return True
        
        if player not in self.player_commands:
            return False
        
        process_name = self.player_commands[player]["process_name"]
        
        # Check if process is running
        if sys.platform == "win32" and WINDOWS_API_AVAILABLE:
            def callback(hwnd, process_names):
                if win32gui.IsWindowVisible(hwnd) and win32gui.IsWindowEnabled(hwnd):
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    try:
                        process_handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
                        if process_handle:
                            try:
                                exe = win32process.GetModuleFileNameEx(process_handle, 0)
                                if exe.endswith(process_name):
                                    process_names.append(exe)
                            finally:
                                win32api.CloseHandle(process_handle)
                    except:
                        pass
                return True
            
            process_names = []
            win32gui.EnumWindows(callback, process_names)
            return len(process_names) > 0
        else:
            # Fallback to subprocess for non-Windows platforms
            try:
                if sys.platform == "win32":
                    output = subprocess.check_output(["tasklist", "/FI", f"IMAGENAME eq {process_name}"], text=True)
                    return process_name in output
                else:
                    output = subprocess.check_output(["pgrep", "-f", process_name], text=True)
                    return bool(output.strip())
            except (subprocess.SubprocessError, FileNotFoundError):
                return False
    
    def _launch_player(self, player: str) -> bool:
        """Launch a media player
        
        Args:
            player: Player name
            
        Returns:
            True if player was launched successfully, False otherwise
        """
        if player == "system" or player not in self.player_commands:
            return False
        
        if self._is_player_running(player):
            return True
        
        try:
            launch_command = self.player_commands[player]["launch"]
            subprocess.Popen(launch_command, shell=True)
            
            # Wait for player to start
            for _ in range(10):
                time.sleep(0.5)
                if self._is_player_running(player):
                    return True
            
            return False
        except Exception as e:
            self.logger.error(f"Error launching player {player}: {e}")
            return False
    
    def _send_media_key(self, key: str) -> bool:
        """Send a media key press
        
        Args:
            key: Media key name
            
        Returns:
            True if key was sent successfully, False otherwise
        """
        if not self.use_keyboard_shortcuts or key not in self.media_keys:
            return False
        
        try:
            pyautogui.press(self.media_keys[key])
            return True
        except Exception as e:
            self.logger.error(f"Error sending media key {key}: {e}")
            return False
    
    def _send_player_command(self, player: str, command: str) -> bool:
        """Send a command to a specific player
        
        Args:
            player: Player name
            command: Command name
            
        Returns:
            True if command was sent successfully, False otherwise
        """
        # Currently, we only support media keys for all players
        # This method can be extended to support player-specific commands
        return self._send_media_key(command)
    
    def _execute_media_command(self, command: str, player: Optional[str] = None) -> bool:
        """Execute a media command
        
        Args:
            command: Command name
            player: Player name (optional)
            
        Returns:
            True if command was executed successfully, False otherwise
        """
        # Determine which player to use
        target_player = player or self.current_player or self.default_player
        
        # Check if player is running
        if not self._is_player_running(target_player):
            if self.launch_player_on_command and target_player != "system":
                # Try to launch the player
                if not self._launch_player(target_player):
                    # Fall back to system-wide media keys
                    target_player = "system"
            else:
                # Fall back to system-wide media keys
                target_player = "system"
        
        # Update current player
        self.current_player = target_player
        
        # Execute command
        if target_player == "system" or self.use_keyboard_shortcuts:
            return self._send_media_key(command)
        else:
            return self._send_player_command(target_player, command)
    
    def _update_play_state(self, command: str):
        """Update the playing state based on command
        
        Args:
            command: Command name
        """
        if command == "play":
            self.is_playing = True
        elif command == "pause" or command == "stop":
            self.is_playing = False
        elif command == "play_pause":
            self.is_playing = not self.is_playing
    
    def get_commands(self) -> Dict[str, Dict[str, Any]]:
        """Get commands provided by the plugin
        
        Returns:
            Dictionary of command names to command metadata
        """
        return {
            "play": {
                "description": "Play media",
                "usage": "play [player]",
                "examples": ["play", "play spotify"],
                "args": {
                    "player": {
                        "description": "Media player to use",
                        "required": False,
                        "type": "string",
                        "enum": ["system", "vlc", "spotify", "windows_media_player"]
                    }
                }
            },
            "pause": {
                "description": "Pause media playback",
                "usage": "pause [player]",
                "examples": ["pause", "pause spotify"],
                "args": {
                    "player": {
                        "description": "Media player to use",
                        "required": False,
                        "type": "string",
                        "enum": ["system", "vlc", "spotify", "windows_media_player"]
                    }
                }
            },
            "stop": {
                "description": "Stop media playback",
                "usage": "stop [player]",
                "examples": ["stop", "stop vlc"],
                "args": {
                    "player": {
                        "description": "Media player to use",
                        "required": False,
                        "type": "string",
                        "enum": ["system", "vlc", "spotify", "windows_media_player"]
                    }
                }
            },
            "next": {
                "description": "Play next track",
                "usage": "next [player]",
                "examples": ["next", "next spotify"],
                "args": {
                    "player": {
                        "description": "Media player to use",
                        "required": False,
                        "type": "string",
                        "enum": ["system", "vlc", "spotify", "windows_media_player"]
                    }
                }
            },
            "previous": {
                "description": "Play previous track",
                "usage": "previous [player]",
                "examples": ["previous", "previous spotify"],
                "args": {
                    "player": {
                        "description": "Media player to use",
                        "required": False,
                        "type": "string",
                        "enum": ["system", "vlc", "spotify", "windows_media_player"]
                    }
                }
            },
            "volume_up": {
                "description": "Increase volume",
                "usage": "volume_up [player] [amount]",
                "examples": ["volume_up", "volume_up spotify 20"],
                "args": {
                    "player": {
                        "description": "Media player to use",
                        "required": False,
                        "type": "string",
                        "enum": ["system", "vlc", "spotify", "windows_media_player"]
                    },
                    "amount": {
                        "description": "Amount to increase volume by (percentage)",
                        "required": False,
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100
                    }
                }
            },
            "volume_down": {
                "description": "Decrease volume",
                "usage": "volume_down [player] [amount]",
                "examples": ["volume_down", "volume_down spotify 20"],
                "args": {
                    "player": {
                        "description": "Media player to use",
                        "required": False,
                        "type": "string",
                        "enum": ["system", "vlc", "spotify", "windows_media_player"]
                    },
                    "amount": {
                        "description": "Amount to decrease volume by (percentage)",
                        "required": False,
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100
                    }
                }
            },
            "mute": {
                "description": "Mute/unmute media playback",
                "usage": "mute [player]",
                "examples": ["mute", "mute spotify"],
                "args": {
                    "player": {
                        "description": "Media player to use",
                        "required": False,
                        "type": "string",
                        "enum": ["system", "vlc", "spotify", "windows_media_player"]
                    }
                }
            },
            "launch_player": {
                "description": "Launch a media player",
                "usage": "launch_player <player>",
                "examples": ["launch_player spotify", "launch_player vlc"],
                "args": {
                    "player": {
                        "description": "Media player to launch",
                        "required": True,
                        "type": "string",
                        "enum": ["vlc", "spotify", "windows_media_player"]
                    }
                }
            }
        }
    
    def execute_command(self, command: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a command
        
        Args:
            command: Command name
            args: Command arguments
            
        Returns:
            Command result
        """
        player = args.get("player")
        
        if command == "play":
            success = self._execute_media_command("play_pause" if not self.is_playing else "play", player)
            if success:
                self.is_playing = True
            
            return {
                "success": success,
                "result": "Media playback started" if success else "Failed to start media playback"
            }
        
        elif command == "pause":
            success = self._execute_media_command("play_pause" if self.is_playing else "pause", player)
            if success:
                self.is_playing = False
            
            return {
                "success": success,
                "result": "Media playback paused" if success else "Failed to pause media playback"
            }
        
        elif command == "stop":
            success = self._execute_media_command("stop", player)
            if success:
                self.is_playing = False
            
            return {
                "success": success,
                "result": "Media playback stopped" if success else "Failed to stop media playback"
            }
        
        elif command == "next":
            success = self._execute_media_command("next", player)
            
            return {
                "success": success,
                "result": "Playing next track" if success else "Failed to play next track"
            }
        
        elif command == "previous":
            success = self._execute_media_command("previous", player)
            
            return {
                "success": success,
                "result": "Playing previous track" if success else "Failed to play previous track"
            }
        
        elif command == "volume_up":
            amount = args.get("amount", self.volume_step)
            
            # Repeat volume up key press based on amount
            success = True
            for _ in range(max(1, amount // self.volume_step)):
                if not self._execute_media_command("volume_up", player):
                    success = False
                    break
            
            return {
                "success": success,
                "result": f"Volume increased by {amount}%" if success else "Failed to increase volume"
            }
        
        elif command == "volume_down":
            amount = args.get("amount", self.volume_step)
            
            # Repeat volume down key press based on amount
            success = True
            for _ in range(max(1, amount // self.volume_step)):
                if not self._execute_media_command("volume_down", player):
                    success = False
                    break
            
            return {
                "success": success,
                "result": f"Volume decreased by {amount}%" if success else "Failed to decrease volume"
            }
        
        elif command == "mute":
            success = self._execute_media_command("mute", player)
            
            return {
                "success": success,
                "result": "Media muted/unmuted" if success else "Failed to mute/unmute media"
            }
        
        elif command == "launch_player":
            if not player or player == "system":
                return {
                    "success": False,
                    "error": "Must specify a player to launch"
                }
            
            success = self._launch_player(player)
            
            if success:
                self.current_player = player
            
            return {
                "success": success,
                "result": f"Launched {player}" if success else f"Failed to launch {player}"
            }
        
        else:
            return {
                "success": False,
                "error": f"Unknown command: {command}"
            }
    
    def get_intents(self) -> Dict[str, List[str]]:
        """Get intents provided by the plugin
        
        Returns:
            Dictionary of intent names to example phrases
        """
        return {
            "media_control": [
                "Play music",
                "Pause the music",
                "Stop playback",
                "Play the next song",
                "Go to the previous track",
                "Turn up the volume",
                "Turn down the volume",
                "Mute the audio",
                "Launch Spotify",
                "Open VLC",
                "Play music on Spotify"
            ]
        }
    
    def handle_intent(self, intent: str, entities: Dict[str, Any], text: str) -> Dict[str, Any]:
        """Handle an intent
        
        Args:
            intent: Intent name
            entities: Extracted entities
            text: Original text
            
        Returns:
            Intent handling result
        """
        if intent == "media_control":
            # Extract player from entities
            player = None
            if "player" in entities:
                player = entities["player"]
            else:
                # Try to extract player from text
                for p in ["spotify", "vlc", "windows media player"]:
                    if p in text.lower():
                        player = p.replace(" ", "_")
                        break
            
            # Extract command from text
            command = None
            
            if any(word in text.lower() for word in ["play", "start", "resume", "begin"]):
                command = "play"
            elif any(word in text.lower() for word in ["pause", "hold", "wait"]):
                command = "pause"
            elif any(word in text.lower() for word in ["stop", "end", "finish"]):
                command = "stop"
            elif any(word in text.lower() for word in ["next", "skip", "forward"]):
                command = "next"
            elif any(word in text.lower() for word in ["previous", "back", "backward", "last"]):
                command = "previous"
            elif any(phrase in text.lower() for phrase in ["volume up", "louder", "increase volume", "turn up"]):
                command = "volume_up"
            elif any(phrase in text.lower() for phrase in ["volume down", "quieter", "decrease volume", "turn down"]):
                command = "volume_down"
            elif any(word in text.lower() for word in ["mute", "silence", "quiet"]):
                command = "mute"
            elif any(phrase in text.lower() for phrase in ["launch", "open", "start", "run"]):
                command = "launch_player"
            
            # Extract amount for volume commands
            amount = None
            if command in ["volume_up", "volume_down"] and "amount" in entities:
                try:
                    amount = int(entities["amount"])
                except (ValueError, TypeError):
                    pass
            
            # Execute command if found
            if command:
                args = {}
                
                if player:
                    args["player"] = player
                
                if amount is not None:
                    args["amount"] = amount
                
                return self.execute_command(command, args)
        
        return {
            "success": False,
            "error": f"Unknown intent: {intent}"
        }
    
    def get_hooks(self) -> Dict[str, List[str]]:
        """Get hooks provided by the plugin
        
        Returns:
            Dictionary of hook names to event types
        """
        return {}
    
    def handle_hook(self, hook: str, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a hook
        
        Args:
            hook: Hook name
            event_type: Event type
            data: Event data
            
        Returns:
            Hook handling result
        """
        return {"success": False, "error": f"Unknown hook or event type: {hook}/{event_type}"}
    
    def shutdown(self):
        """Shutdown the plugin"""
        self.logger.info("Shutting down media controller plugin")