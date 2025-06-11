#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Enhanced Voice Commands Plugin for Jarvis Assistant

This plugin adds advanced voice command capabilities to Jarvis,
allowing it to control applications, perform system operations,
and execute various tasks based on voice input.
"""

import os
import re
import sys
import logging
import subprocess
import threading
import time
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime

# Import for system operations
import psutil

# Import for GUI automation
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

# Import for Windows-specific functionality
try:
    import win32api
    import win32con
    import win32gui
    import win32process
    import win32com.client
    from win32com.shell import shell, shellcon
    import pywintypes
    WINDOWS_SUPPORT = True
except ImportError:
    WINDOWS_SUPPORT = False

# Import Plugin base class
from core.plugin import Plugin


class EnhancedCommandsPlugin(Plugin):
    """Enhanced Voice Commands Plugin for Jarvis Assistant"""
    
    def __init__(self, assistant):
        """Initialize the Enhanced Commands plugin
        
        Args:
            assistant: The Jarvis assistant instance
        """
        super().__init__(assistant)
        self.logger = logging.getLogger("jarvis.plugins.enhanced_commands")
        
        # Check if required libraries are available
        if not PYAUTOGUI_AVAILABLE:
            self.logger.error("PyAutoGUI not available. Please install with 'pip install pyautogui'")
        
        if not WINDOWS_SUPPORT and os.name == 'nt':
            self.logger.error("Windows support libraries not available. Please install with 'pip install pywin32'")
        
        # Get plugin configuration
        self.config = self.assistant.config.get("plugins", {}).get("enhanced_commands", {})
        self.enabled = self.config.get("enabled", True)
        
        # Get application paths
        self.app_paths = self.config.get("app_paths", {})
        
        # Get custom commands
        self.custom_commands = self.config.get("custom_commands", {})
        
        # Get confirmation required actions
        self.confirmation_required = self.config.get("confirmation_required", 
                                                   ["delete", "shutdown", "restart"])
        
        # Get default file locations
        self.default_file_locations = self.config.get("default_file_locations", {})
        
        # Expand environment variables in paths
        self._expand_path_variables()
        
        # Active confirmation requests
        self.pending_confirmations = {}
        
        # NLP engine reference
        self.nlp_engine = None
        
        self.logger.info("Enhanced Commands plugin initialized")
    
    def _expand_path_variables(self):
        """Expand environment variables in paths"""
        # Expand app paths
        for app, path in self.app_paths.items():
            if isinstance(path, str):
                self.app_paths[app] = os.path.expandvars(path)
        
        # Expand file locations
        for location, path in self.default_file_locations.items():
            if isinstance(path, str):
                self.default_file_locations[location] = os.path.expandvars(path)
    
    def activate(self):
        """Activate the Enhanced Commands plugin"""
        # Get reference to NLP engine
        self.nlp_engine = self.assistant.get_module("nlp_engine")
        
        if not self.nlp_engine:
            self.logger.warning("NLP engine not available, some features may be limited")
        
        # Register commands
        self._register_commands()
        
        # Register intents
        self._register_intents()
        
        self.logger.info("Enhanced Commands plugin activated")
        return True
    
    def _register_commands(self):
        """Register Enhanced Commands"""
        # Application control commands
        self.register_command(
            "open_app",
            self._cmd_open_app,
            "Open application",
            "Open a specified application",
            "open_app <app_name>",
            ["open_app chrome", "open_app notepad"],
            {
                "app_name": {
                    "type": "string",
                    "description": "Name of the application to open",
                    "required": True
                }
            }
        )
        
        self.register_command(
            "close_app",
            self._cmd_close_app,
            "Close application",
            "Close a specified application",
            "close_app <app_name>",
            ["close_app chrome", "close_app notepad"],
            {
                "app_name": {
                    "type": "string",
                    "description": "Name of the application to close",
                    "required": True
                }
            }
        )
        
        # File operations commands
        self.register_command(
            "find_file",
            self._cmd_find_file,
            "Find file",
            "Find a file on the system",
            "find_file <file_name> [location]",
            ["find_file report.docx", "find_file budget.xlsx documents"],
            {
                "file_name": {
                    "type": "string",
                    "description": "Name of the file to find",
                    "required": True
                },
                "location": {
                    "type": "string",
                    "description": "Location to search in",
                    "default": None
                }
            }
        )
        
        self.register_command(
            "open_file",
            self._cmd_open_file,
            "Open file",
            "Open a specified file",
            "open_file <file_path>",
            ["open_file C:\\Users\\User\\Documents\\report.docx"],
            {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to open",
                    "required": True
                }
            }
        )
        
        # System control commands
        self.register_command(
            "system_action",
            self._cmd_system_action,
            "System action",
            "Perform a system action like shutdown, restart, etc.",
            "system_action <action>",
            ["system_action lock", "system_action sleep"],
            {
                "action": {
                    "type": "string",
                    "description": "System action to perform (lock, sleep, hibernate, shutdown, restart)",
                    "required": True
                }
            }
        )
        
        # Custom command execution
        self.register_command(
            "run_custom_command",
            self._cmd_run_custom_command,
            "Run custom command",
            "Run a predefined custom command",
            "run_custom_command <command_name>",
            ["run_custom_command backup_documents"],
            {
                "command_name": {
                    "type": "string",
                    "description": "Name of the custom command to run",
                    "required": True
                }
            }
        )
    
    def _register_intents(self):
        """Register Enhanced Commands intents"""
        # Application control intents
        self.register_intent(
            "open_application",
            self._intent_open_application,
            [
                "open {app}",
                "launch {app}",
                "start {app}",
                "run {app}",
                "execute {app}"
            ],
            {
                "app": "APP_NAME"
            }
        )
        
        self.register_intent(
            "close_application",
            self._intent_close_application,
            [
                "close {app}",
                "exit {app}",
                "quit {app}",
                "terminate {app}",
                "shut down {app}"
            ],
            {
                "app": "APP_NAME"
            }
        )
        
        # File operations intents
        self.register_intent(
            "find_file",
            self._intent_find_file,
            [
                "find {file}",
                "locate {file}",
                "search for {file}",
                "where is {file}",
                "find {file} in {location}"
            ],
            {
                "file": "FILE_NAME",
                "location": "LOCATION"
            }
        )
        
        self.register_intent(
            "open_file",
            self._intent_open_file,
            [
                "open {file}",
                "open the file {file}",
                "show {file}",
                "display {file}"
            ],
            {
                "file": "FILE_NAME"
            }
        )
        
        # System control intents
        self.register_intent(
            "system_control",
            self._intent_system_control,
            [
                "lock the computer",
                "lock my pc",
                "put the computer to sleep",
                "sleep mode",
                "hibernate the computer",
                "shut down the computer",
                "restart the computer",
                "reboot the system"
            ]
        )
        
        # Birthday reminder intent
        self.register_intent(
            "birthday_reminder",
            self._intent_birthday_reminder,
            [
                "remind me about {person}'s birthday",
                "set a birthday reminder for {person}",
                "when is {person}'s birthday",
                "send birthday wishes to {person}",
                "today is {person}'s birthday"
            ],
            {
                "person": "PERSON"
            }
        )
    
    def _cmd_open_app(self, app_name):
        """Command to open an application
        
        Args:
            app_name: Name of the application to open
            
        Returns:
            Command result
        """
        try:
            # Check if app name is in configured paths
            app_path = None
            for name, path in self.app_paths.items():
                if app_name.lower() in name.lower():
                    app_path = path
                    break
            
            # If not found in configured paths, try common locations
            if not app_path:
                # Try to find the application in common locations
                if os.name == 'nt':  # Windows
                    # Check Program Files
                    program_files = os.environ.get('ProgramFiles', 'C:\\Program Files')
                    program_files_x86 = os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)')
                    
                    # Common executable extensions
                    exts = ['.exe', '.bat', '.cmd']
                    
                    # Search in Program Files
                    for root_dir in [program_files, program_files_x86]:
                        for root, dirs, files in os.walk(root_dir):
                            for file in files:
                                if any(file.lower() == f"{app_name.lower()}{ext}" for ext in exts):
                                    app_path = os.path.join(root, file)
                                    break
                            if app_path:
                                break
                        if app_path:
                            break
                    
                    # If still not found, try Start Menu
                    if not app_path:
                        start_menu = os.path.join(os.environ.get('APPDATA', ''), 
                                                 'Microsoft', 'Windows', 'Start Menu', 'Programs')
                        for root, dirs, files in os.walk(start_menu):
                            for file in files:
                                if file.lower().startswith(app_name.lower()) and file.lower().endswith('.lnk'):
                                    # Get target from shortcut
                                    shell_obj = win32com.client.Dispatch("WScript.Shell")
                                    shortcut = shell_obj.CreateShortCut(os.path.join(root, file))
                                    app_path = shortcut.Targetpath
                                    break
                            if app_path:
                                break
            
            # If app path found, open it
            if app_path and os.path.exists(app_path):
                if os.name == 'nt':  # Windows
                    os.startfile(app_path)
                else:  # Linux/Mac
                    subprocess.Popen([app_path])
                
                return {
                    "success": True,
                    "message": f"Opened {app_name}",
                    "app_path": app_path
                }
            else:
                # Try to run the app name directly
                try:
                    if os.name == 'nt':  # Windows
                        subprocess.Popen([app_name], shell=True)
                    else:  # Linux/Mac
                        subprocess.Popen([app_name])
                    
                    return {
                        "success": True,
                        "message": f"Opened {app_name}",
                        "app_path": app_name
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "message": f"Could not find or open {app_name}: {str(e)}"
                    }
        
        except Exception as e:
            self.logger.error(f"Error opening application {app_name}: {e}")
            return {
                "success": False,
                "message": f"Error opening {app_name}: {str(e)}"
            }
    
    def _cmd_close_app(self, app_name):
        """Command to close an application
        
        Args:
            app_name: Name of the application to close
            
        Returns:
            Command result
        """
        try:
            closed = False
            
            # Find processes matching the app name
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    # Check if process name contains app name (case insensitive)
                    if app_name.lower() in proc.info['name'].lower():
                        # Terminate the process
                        process = psutil.Process(proc.info['pid'])
                        process.terminate()
                        closed = True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            if closed:
                return {
                    "success": True,
                    "message": f"Closed {app_name}"
                }
            else:
                return {
                    "success": False,
                    "message": f"Could not find running application: {app_name}"
                }
        
        except Exception as e:
            self.logger.error(f"Error closing application {app_name}: {e}")
            return {
                "success": False,
                "message": f"Error closing {app_name}: {str(e)}"
            }
    
    def _cmd_find_file(self, file_name, location=None):
        """Command to find a file
        
        Args:
            file_name: Name of the file to find
            location: Location to search in (optional)
            
        Returns:
            Command result
        """
        try:
            # Determine search location
            search_path = None
            if location:
                # Check if location is in default locations
                if location.lower() in self.default_file_locations:
                    search_path = self.default_file_locations[location.lower()]
                else:
                    # Try to use location as direct path
                    if os.path.exists(location):
                        search_path = location
            
            if not search_path:
                # Default to user profile directory
                search_path = os.path.expanduser("~")
            
            # Find files matching the name
            found_files = []
            for root, dirs, files in os.walk(search_path):
                for file in files:
                    if file_name.lower() in file.lower():
                        found_files.append(os.path.join(root, file))
                        # Limit to 10 results to avoid excessive searching
                        if len(found_files) >= 10:
                            break
                if len(found_files) >= 10:
                    break
            
            if found_files:
                return {
                    "success": True,
                    "message": f"Found {len(found_files)} files matching '{file_name}'",
                    "files": found_files
                }
            else:
                return {
                    "success": False,
                    "message": f"Could not find any files matching '{file_name}' in {search_path}"
                }
        
        except Exception as e:
            self.logger.error(f"Error finding file {file_name}: {e}")
            return {
                "success": False,
                "message": f"Error finding file: {str(e)}"
            }
    
    def _cmd_open_file(self, file_path):
        """Command to open a file
        
        Args:
            file_path: Path to the file to open
            
        Returns:
            Command result
        """
        try:
            # Check if file exists
            if os.path.exists(file_path):
                # Open the file with default application
                if os.name == 'nt':  # Windows
                    os.startfile(file_path)
                else:  # Linux/Mac
                    subprocess.Popen(['xdg-open', file_path])
                
                return {
                    "success": True,
                    "message": f"Opened file: {file_path}"
                }
            else:
                return {
                    "success": False,
                    "message": f"File not found: {file_path}"
                }
        
        except Exception as e:
            self.logger.error(f"Error opening file {file_path}: {e}")
            return {
                "success": False,
                "message": f"Error opening file: {str(e)}"
            }
    
    def _cmd_system_action(self, action):
        """Command to perform a system action
        
        Args:
            action: System action to perform (lock, sleep, hibernate, shutdown, restart)
            
        Returns:
            Command result
        """
        try:
            # Check if action requires confirmation
            if action.lower() in self.confirmation_required:
                # Generate a unique confirmation ID
                confirmation_id = f"system_action_{int(time.time())}"
                
                # Store the pending confirmation
                self.pending_confirmations[confirmation_id] = {
                    "action": "system_action",
                    "params": {"action": action},
                    "timestamp": time.time(),
                    "expires": time.time() + 60  # Expires in 60 seconds
                }
                
                return {
                    "success": True,
                    "requires_confirmation": True,
                    "confirmation_id": confirmation_id,
                    "message": f"Are you sure you want to {action} the system?"
                }
            
            # Perform the action
            return self._perform_system_action(action)
        
        except Exception as e:
            self.logger.error(f"Error performing system action {action}: {e}")
            return {
                "success": False,
                "message": f"Error performing system action: {str(e)}"
            }
    
    def _perform_system_action(self, action):
        """Perform a system action
        
        Args:
            action: System action to perform
            
        Returns:
            Result dictionary
        """
        action = action.lower()
        
        if os.name == 'nt':  # Windows
            if action == "lock":
                ctypes.windll.user32.LockWorkStation()
                return {"success": True, "message": "Computer locked"}
            
            elif action == "sleep" or action == "suspend":
                # Set system to sleep mode
                win32api.SetSystemPowerState(True, True)
                return {"success": True, "message": "Computer is going to sleep"}
            
            elif action == "hibernate":
                # Set system to hibernate
                win32api.SetSystemPowerState(False, True)
                return {"success": True, "message": "Computer is hibernating"}
            
            elif action == "shutdown":
                # Shut down the system
                os.system("shutdown /s /t 5 /f")
                return {"success": True, "message": "Computer will shut down in 5 seconds"}
            
            elif action == "restart" or action == "reboot":
                # Restart the system
                os.system("shutdown /r /t 5 /f")
                return {"success": True, "message": "Computer will restart in 5 seconds"}
            
            else:
                return {"success": False, "message": f"Unknown system action: {action}"}
        
        else:  # Linux/Mac
            if action == "lock":
                if platform.system() == 'Darwin':  # macOS
                    subprocess.call(['pmset', 'displaysleepnow'])
                else:  # Linux
                    subprocess.call(['xdg-screensaver', 'lock'])
                return {"success": True, "message": "Computer locked"}
            
            elif action == "sleep" or action == "suspend":
                if platform.system() == 'Darwin':  # macOS
                    subprocess.call(['pmset', 'sleepnow'])
                else:  # Linux
                    subprocess.call(['systemctl', 'suspend'])
                return {"success": True, "message": "Computer is going to sleep"}
            
            elif action == "hibernate":
                if platform.system() == 'Darwin':  # macOS
                    # macOS doesn't have true hibernate
                    subprocess.call(['pmset', 'sleepnow'])
                else:  # Linux
                    subprocess.call(['systemctl', 'hibernate'])
                return {"success": True, "message": "Computer is hibernating"}
            
            elif action == "shutdown":
                if platform.system() == 'Darwin':  # macOS
                    subprocess.call(['osascript', '-e', 'tell app "System Events" to shut down'])
                else:  # Linux
                    subprocess.call(['systemctl', 'poweroff'])
                return {"success": True, "message": "Computer is shutting down"}
            
            elif action == "restart" or action == "reboot":
                if platform.system() == 'Darwin':  # macOS
                    subprocess.call(['osascript', '-e', 'tell app "System Events" to restart'])
                else:  # Linux
                    subprocess.call(['systemctl', 'reboot'])
                return {"success": True, "message": "Computer is restarting"}
            
            else:
                return {"success": False, "message": f"Unknown system action: {action}"}
    
    def _cmd_run_custom_command(self, command_name):
        """Command to run a custom command
        
        Args:
            command_name: Name of the custom command to run
            
        Returns:
            Command result
        """
        try:
            # Check if command exists in custom commands
            if command_name in self.custom_commands:
                command = self.custom_commands[command_name]
                
                # Check command type
                if isinstance(command, str):
                    # Run as shell command
                    process = subprocess.Popen(
                        command,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    stdout, stderr = process.communicate()
                    
                    if process.returncode == 0:
                        return {
                            "success": True,
                            "message": f"Custom command '{command_name}' executed successfully",
                            "output": stdout
                        }
                    else:
                        return {
                            "success": False,
                            "message": f"Custom command '{command_name}' failed: {stderr}"
                        }
                
                elif isinstance(command, dict) and "type" in command:
                    # Handle different command types
                    if command["type"] == "app":
                        # Open application
                        return self._cmd_open_app(command.get("app_name", ""))
                    
                    elif command["type"] == "url":
                        # Open URL
                        url = command.get("url", "")
                        if url:
                            if os.name == 'nt':  # Windows
                                os.startfile(url)
                            else:  # Linux/Mac
                                subprocess.Popen(['xdg-open', url])
                            
                            return {
                                "success": True,
                                "message": f"Opened URL: {url}"
                            }
                        else:
                            return {
                                "success": False,
                                "message": "No URL specified in custom command"
                            }
                    
                    elif command["type"] == "script":
                        # Run script file
                        script_path = command.get("script_path", "")
                        if script_path and os.path.exists(script_path):
                            process = subprocess.Popen(
                                script_path,
                                shell=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            stdout, stderr = process.communicate()
                            
                            if process.returncode == 0:
                                return {
                                    "success": True,
                                    "message": f"Script '{script_path}' executed successfully",
                                    "output": stdout
                                }
                            else:
                                return {
                                    "success": False,
                                    "message": f"Script '{script_path}' failed: {stderr}"
                                }
                        else:
                            return {
                                "success": False,
                                "message": f"Script not found: {script_path}"
                            }
                    
                    else:
                        return {
                            "success": False,
                            "message": f"Unknown custom command type: {command['type']}"
                        }
                
                else:
                    return {
                        "success": False,
                        "message": f"Invalid custom command format for '{command_name}'"
                    }
            
            else:
                return {
                    "success": False,
                    "message": f"Custom command not found: {command_name}"
                }
        
        except Exception as e:
            self.logger.error(f"Error running custom command {command_name}: {e}")
            return {
                "success": False,
                "message": f"Error running custom command: {str(e)}"
            }
    
    def _intent_open_application(self, text, entities):
        """Handle open application intent
        
        Args:
            text: Intent text
            entities: Extracted entities
            
        Returns:
            Response text
        """
        if "app" in entities:
            app_name = entities["app"]
            result = self._cmd_open_app(app_name)
            
            if result["success"]:
                return f"Opening {app_name} for you."
            else:
                return f"Sorry, I couldn't open {app_name}. {result['message']}"
        else:
            return "What application would you like me to open?"
    
    def _intent_close_application(self, text, entities):
        """Handle close application intent
        
        Args:
            text: Intent text
            entities: Extracted entities
            
        Returns:
            Response text
        """
        if "app" in entities:
            app_name = entities["app"]
            result = self._cmd_close_app(app_name)
            
            if result["success"]:
                return f"I've closed {app_name} for you."
            else:
                return f"Sorry, I couldn't close {app_name}. {result['message']}"
        else:
            return "What application would you like me to close?"
    
    def _intent_find_file(self, text, entities):
        """Handle find file intent
        
        Args:
            text: Intent text
            entities: Extracted entities
            
        Returns:
            Response text
        """
        if "file" in entities:
            file_name = entities["file"]
            location = entities.get("location", None)
            
            result = self._cmd_find_file(file_name, location)
            
            if result["success"]:
                if len(result["files"]) == 1:
                    file_path = result["files"][0]
                    return f"I found the file at {file_path}. Would you like me to open it?"
                else:
                    files_list = "\n".join([f"- {file}" for file in result["files"][:5]])
                    if len(result["files"]) > 5:
                        files_list += f"\n...and {len(result['files']) - 5} more."
                    return f"I found {len(result['files'])} files matching '{file_name}':\n{files_list}"
            else:
                return f"Sorry, I couldn't find any files matching '{file_name}'. {result['message']}"
        else:
            return "What file would you like me to find?"
    
    def _intent_open_file(self, text, entities):
        """Handle open file intent
        
        Args:
            text: Intent text
            entities: Extracted entities
            
        Returns:
            Response text
        """
        if "file" in entities:
            file_name = entities["file"]
            
            # First try to find the file
            find_result = self._cmd_find_file(file_name)
            
            if find_result["success"] and find_result["files"]:
                # Open the first matching file
                file_path = find_result["files"][0]
                open_result = self._cmd_open_file(file_path)
                
                if open_result["success"]:
                    return f"I've opened {os.path.basename(file_path)} for you."
                else:
                    return f"Sorry, I couldn't open the file. {open_result['message']}"
            else:
                return f"Sorry, I couldn't find any files matching '{file_name}'."
        else:
            return "What file would you like me to open?"
    
    def _intent_system_control(self, text, entities):
        """Handle system control intent
        
        Args:
            text: Intent text
            entities: Extracted entities
            
        Returns:
            Response text
        """
        # Determine the action from the text
        action = None
        
        if "lock" in text.lower():
            action = "lock"
        elif "sleep" in text.lower():
            action = "sleep"
        elif "hibernate" in text.lower():
            action = "hibernate"
        elif "shut down" in text.lower() or "shutdown" in text.lower():
            action = "shutdown"
        elif "restart" in text.lower() or "reboot" in text.lower():
            action = "restart"
        
        if action:
            result = self._cmd_system_action(action)
            
            if result.get("requires_confirmation", False):
                # Store confirmation ID in conversation context
                self.assistant.set_conversation_context("confirmation_id", result["confirmation_id"])
                return result["message"]
            
            elif result["success"]:
                return result["message"]
            else:
                return f"Sorry, I couldn't perform that action. {result['message']}"
        else:
            return "I'm not sure what system action you want me to perform. You can ask me to lock, sleep, hibernate, shut down, or restart the computer."
    
    def _intent_birthday_reminder(self, text, entities):
        """Handle birthday reminder intent
        
        Args:
            text: Intent text
            entities: Extracted entities
            
        Returns:
            Response text
        """
        if "person" in entities:
            person = entities["person"]
            
            # Check if this is about sending wishes
            if "send" in text.lower() and "wish" in text.lower():
                # Get Gmail plugin
                gmail_plugin = self.assistant.get_plugin("gmail")
                
                if gmail_plugin:
                    # Start a conversation flow to get more details
                    self.assistant.start_conversation_flow(
                        "birthday_wishes",
                        {"person": person},
                        self._complete_birthday_wishes
                    )
                    
                    return f"I'll help you send birthday wishes to {person}. What message would you like to send?"
                else:
                    return f"I'd like to help you send birthday wishes to {person}, but the Gmail plugin is not available."
            
            # Check if this is about setting a reminder
            elif "remind" in text.lower() or "reminder" in text.lower():
                # Get reminders plugin
                reminders_plugin = self.assistant.get_plugin("reminders")
                
                if reminders_plugin:
                    # Start a conversation flow to get more details
                    self.assistant.start_conversation_flow(
                        "birthday_reminder",
                        {"person": person},
                        self._complete_birthday_reminder
                    )
                    
                    return f"I'll help you set a birthday reminder for {person}. When is their birthday?"
                else:
                    return f"I'd like to help you set a birthday reminder for {person}, but the reminders plugin is not available."
            
            # Otherwise, just provide information
            else:
                return f"I don't have information about {person}'s birthday. Would you like to add it to your contacts?"
        else:
            return "Whose birthday are you referring to?"
    
    def _complete_birthday_wishes(self, data):
        """Complete the birthday wishes conversation flow
        
        Args:
            data: Collected conversation data
            
        Returns:
            Response text
        """
        person = data.get("person", "")
        message = data.get("message", f"Happy Birthday! Hope you have a wonderful day!")
        
        # Get Gmail plugin
        gmail_plugin = self.assistant.get_plugin("gmail")
        
        if gmail_plugin:
            # Try to find email address for the person
            email = data.get("email", "")
            
            if not email:
                # In a real implementation, we would search contacts
                return f"I couldn't find an email address for {person}. Please provide their email address."
            
            # Send email
            result = gmail_plugin._cmd_send_email(
                email,
                f"Happy Birthday {person}!",
                message
            )
            
            if result.get("success", False):
                return f"I've sent birthday wishes to {person} at {email}."
            else:
                return f"Sorry, I couldn't send the email. {result.get('message', '')}"
        else:
            return "Sorry, the Gmail plugin is not available."
    
    def _complete_birthday_reminder(self, data):
        """Complete the birthday reminder conversation flow
        
        Args:
            data: Collected conversation data
            
        Returns:
            Response text
        """
        person = data.get("person", "")
        date = data.get("date", "")
        
        # Get reminders plugin
        reminders_plugin = self.assistant.get_plugin("reminders")
        
        if reminders_plugin:
            # Create reminder
            result = reminders_plugin.create_reminder(
                title=f"{person}'s Birthday",
                description=f"Don't forget to wish {person} a happy birthday!",
                date=date,
                time="09:00",
                repeat="yearly"
            )
            
            if result.get("success", False):
                return f"I've set a yearly reminder for {person}'s birthday on {date}."
            else:
                return f"Sorry, I couldn't set the reminder. {result.get('message', '')}"
        else:
            return "Sorry, the reminders plugin is not available."
    
    def process_confirmation(self, confirmation_id, confirmed):
        """Process a confirmation response
        
        Args:
            confirmation_id: The confirmation ID
            confirmed: Whether the action was confirmed
            
        Returns:
            Response text
        """
        if confirmation_id in self.pending_confirmations:
            confirmation = self.pending_confirmations[confirmation_id]
            
            # Remove the confirmation
            del self.pending_confirmations[confirmation_id]
            
            if confirmed:
                # Execute the confirmed action
                if confirmation["action"] == "system_action":
                    action = confirmation["params"]["action"]
                    result = self._perform_system_action(action)
                    
                    if result["success"]:
                        return result["message"]
                    else:
                        return f"Sorry, I couldn't perform that action. {result['message']}"
                else:
                    return "Unknown action type."
            else:
                return "Action cancelled."
        else:
            return "Confirmation expired or not found."
    
    def cleanup_expired_confirmations(self):
        """Clean up expired confirmation requests"""
        current_time = time.time()
        expired_ids = []
        
        for confirmation_id, confirmation in self.pending_confirmations.items():
            if current_time > confirmation["expires"]:
                expired_ids.append(confirmation_id)
        
        for confirmation_id in expired_ids:
            del self.pending_confirmations[confirmation_id]
    
    def shutdown(self):
        """Shutdown the Enhanced Commands plugin"""
        self.logger.info("Enhanced Commands plugin shut down")