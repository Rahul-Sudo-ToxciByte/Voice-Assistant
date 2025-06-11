#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Auto Startup Plugin for Jarvis Assistant

This plugin enables Jarvis to start automatically when the system boots up.
It creates a registry entry or startup shortcut depending on the operating system.
"""

import os
import sys
import logging
import platform
from typing import Dict, Any

# Import for Windows registry access
try:
    import winreg
    import win32com.client
    WINDOWS_SUPPORT = True
except ImportError:
    WINDOWS_SUPPORT = False

# Import Plugin base class
from core.plugin import Plugin


class AutoStartupPlugin(Plugin):
    """Auto Startup Plugin for Jarvis Assistant"""
    
    def __init__(self, assistant):
        """Initialize the Auto Startup plugin
        
        Args:
            assistant: The Jarvis assistant instance
        """
        super().__init__(assistant)
        self.logger = logging.getLogger("jarvis.plugins.auto_startup")
        
        # Check if required libraries are available
        if not WINDOWS_SUPPORT and platform.system() == 'Windows':
            self.logger.error("Windows support libraries not available. Please install with 'pip install pywin32'")
        
        # Get plugin configuration
        self.config = self.assistant.config.get("plugins", {}).get("auto_startup", {})
        self.enabled = self.config.get("enabled", True)
        self.minimize_on_startup = self.config.get("minimize_on_startup", False)
        self.delay_seconds = self.config.get("delay_seconds", 10)
        
        # Get application path
        self.app_path = os.path.abspath(sys.argv[0])
        self.app_dir = os.path.dirname(self.app_path)
        
        self.logger.info("Auto Startup plugin initialized")
    
    def activate(self):
        """Activate the Auto Startup plugin"""
        if self.enabled:
            # Set up auto startup based on operating system
            if platform.system() == 'Windows':
                if WINDOWS_SUPPORT:
                    self._setup_windows_startup()
                else:
                    self.logger.error("Cannot set up Windows auto startup: pywin32 not available")
                    return False
            elif platform.system() == 'Linux':
                self._setup_linux_startup()
            elif platform.system() == 'Darwin':  # macOS
                self._setup_macos_startup()
            else:
                self.logger.error(f"Unsupported operating system: {platform.system()}")
                return False
        
        # Register commands
        self._register_commands()
        
        self.logger.info("Auto Startup plugin activated")
        return True
    
    def _setup_windows_startup(self):
        """Set up auto startup on Windows"""
        try:
            # Create a shortcut in the startup folder
            startup_folder = os.path.join(os.environ["APPDATA"], 
                                         "Microsoft", "Windows", "Start Menu", 
                                         "Programs", "Startup")
            
            shortcut_path = os.path.join(startup_folder, "Jarvis Assistant.lnk")
            
            # Create shortcut using Windows Script Host
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(shortcut_path)
            
            # Set shortcut properties
            shortcut.TargetPath = self.app_path
            shortcut.WorkingDirectory = self.app_dir
            
            # Add startup parameters if needed
            args = []
            if self.minimize_on_startup:
                args.append("--minimize")
            if self.delay_seconds > 0:
                args.append(f"--startup-delay={self.delay_seconds}")
            
            shortcut.Arguments = " ".join(args)
            shortcut.Description = "Jarvis AI Assistant"
            shortcut.IconLocation = os.path.join(self.app_dir, "assets", "icon.ico")
            
            # Save the shortcut
            shortcut.save()
            
            self.logger.info(f"Created startup shortcut at {shortcut_path}")
            
            # Alternative: Add to registry
            # key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
            #                     "Software\\Microsoft\\Windows\\CurrentVersion\\Run", 
            #                     0, winreg.KEY_SET_VALUE)
            # winreg.SetValueEx(key, "Jarvis Assistant", 0, winreg.REG_SZ, f'"{self.app_path}" {" ".join(args)}')
            # winreg.CloseKey(key)
            # self.logger.info("Added to Windows registry for auto startup")
            
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to set up Windows auto startup: {e}")
            return False
    
    def _setup_linux_startup(self):
        """Set up auto startup on Linux"""
        try:
            # Create autostart desktop entry
            autostart_dir = os.path.expanduser("~/.config/autostart")
            os.makedirs(autostart_dir, exist_ok=True)
            
            desktop_file_path = os.path.join(autostart_dir, "jarvis-assistant.desktop")
            
            # Build command with arguments
            command = f"python3 {self.app_path}"
            if self.minimize_on_startup:
                command += " --minimize"
            if self.delay_seconds > 0:
                command += f" --startup-delay={self.delay_seconds}"
            
            # Create desktop entry file
            with open(desktop_file_path, "w") as f:
                f.write("[Desktop Entry]\n")
                f.write("Type=Application\n")
                f.write("Name=Jarvis Assistant\n")
                f.write(f"Exec={command}\n")
                f.write("Terminal=false\n")
                f.write("X-GNOME-Autostart-enabled=true\n")
                f.write("Comment=AI Assistant for your desktop\n")
            
            # Make executable
            os.chmod(desktop_file_path, 0o755)
            
            self.logger.info(f"Created Linux autostart entry at {desktop_file_path}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to set up Linux auto startup: {e}")
            return False
    
    def _setup_macos_startup(self):
        """Set up auto startup on macOS"""
        try:
            # Create LaunchAgents plist file
            launch_agents_dir = os.path.expanduser("~/Library/LaunchAgents")
            os.makedirs(launch_agents_dir, exist_ok=True)
            
            plist_file_path = os.path.join(launch_agents_dir, "com.jarvis.assistant.plist")
            
            # Build command with arguments
            program_args = [self.app_path]
            if self.minimize_on_startup:
                program_args.append("--minimize")
            if self.delay_seconds > 0:
                program_args.append(f"--startup-delay={self.delay_seconds}")
            
            # Create plist file content
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.jarvis.assistant</string>
    <key>ProgramArguments</key>
    <array>
        <string>python3</string>
        <string>{self.app_path}</string>"""
            
            for arg in program_args[1:]:
                plist_content += f"""
        <string>{arg}</string>"""
            
            plist_content += f"""
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>WorkingDirectory</key>
    <string>{self.app_dir}</string>
</dict>
</plist>
"""
            
            # Write plist file
            with open(plist_file_path, "w") as f:
                f.write(plist_content)
            
            # Load the plist file
            os.system(f"launchctl load {plist_file_path}")
            
            self.logger.info(f"Created macOS LaunchAgent at {plist_file_path}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to set up macOS auto startup: {e}")
            return False
    
    def _register_commands(self):
        """Register Auto Startup commands"""
        self.register_command(
            "toggle_auto_startup",
            self._cmd_toggle_auto_startup,
            "Toggle auto startup",
            "Enable or disable Jarvis starting automatically on system boot",
            "toggle_auto_startup [enable]",
            ["toggle_auto_startup", "toggle_auto_startup true"],
            {
                "enable": {
                    "type": "boolean",
                    "description": "Enable or disable auto startup",
                    "default": None
                }
            }
        )
    
    def _cmd_toggle_auto_startup(self, enable=None):
        """Command to toggle auto startup
        
        Args:
            enable: Enable or disable auto startup
            
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
        if "auto_startup" not in self.assistant.config["plugins"]:
            self.assistant.config["plugins"]["auto_startup"] = {}
        
        self.assistant.config["plugins"]["auto_startup"]["enabled"] = enable
        self.assistant.save_config()
        
        # Apply the change
        if enable:
            if platform.system() == 'Windows':
                if WINDOWS_SUPPORT:
                    success = self._setup_windows_startup()
                else:
                    return {"success": False, "message": "Windows support libraries not available"}
            elif platform.system() == 'Linux':
                success = self._setup_linux_startup()
            elif platform.system() == 'Darwin':
                success = self._setup_macos_startup()
            else:
                return {"success": False, "message": f"Unsupported operating system: {platform.system()}"}
            
            if not success:
                return {"success": False, "message": "Failed to enable auto startup"}
        else:
            # Remove auto startup entries
            if platform.system() == 'Windows':
                if WINDOWS_SUPPORT:
                    try:
                        # Remove shortcut from startup folder
                        startup_folder = os.path.join(os.environ["APPDATA"], 
                                                    "Microsoft", "Windows", "Start Menu", 
                                                    "Programs", "Startup")
                        shortcut_path = os.path.join(startup_folder, "Jarvis Assistant.lnk")
                        
                        if os.path.exists(shortcut_path):
                            os.remove(shortcut_path)
                            self.logger.info(f"Removed startup shortcut at {shortcut_path}")
                        
                        # Alternative: Remove from registry
                        # key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                        #                     "Software\\Microsoft\\Windows\\CurrentVersion\\Run", 
                        #                     0, winreg.KEY_SET_VALUE)
                        # try:
                        #     winreg.DeleteValue(key, "Jarvis Assistant")
                        #     self.logger.info("Removed from Windows registry auto startup")
                        # except FileNotFoundError:
                        #     pass  # Key doesn't exist, which is fine
                        # winreg.CloseKey(key)
                    except Exception as e:
                        self.logger.error(f"Failed to remove Windows auto startup: {e}")
                        return {"success": False, "message": f"Failed to disable auto startup: {e}"}
                else:
                    return {"success": False, "message": "Windows support libraries not available"}
            
            elif platform.system() == 'Linux':
                try:
                    desktop_file_path = os.path.expanduser("~/.config/autostart/jarvis-assistant.desktop")
                    if os.path.exists(desktop_file_path):
                        os.remove(desktop_file_path)
                        self.logger.info(f"Removed Linux autostart entry at {desktop_file_path}")
                except Exception as e:
                    self.logger.error(f"Failed to remove Linux auto startup: {e}")
                    return {"success": False, "message": f"Failed to disable auto startup: {e}"}
            
            elif platform.system() == 'Darwin':
                try:
                    plist_file_path = os.path.expanduser("~/Library/LaunchAgents/com.jarvis.assistant.plist")
                    if os.path.exists(plist_file_path):
                        os.system(f"launchctl unload {plist_file_path}")
                        os.remove(plist_file_path)
                        self.logger.info(f"Removed macOS LaunchAgent at {plist_file_path}")
                except Exception as e:
                    self.logger.error(f"Failed to remove macOS auto startup: {e}")
                    return {"success": False, "message": f"Failed to disable auto startup: {e}"}
        
        return {
            "success": True,
            "message": f"Auto startup {'enabled' if enable else 'disabled'}"
        }
    
    def shutdown(self):
        """Shutdown the Auto Startup plugin"""
        self.logger.info("Auto Startup plugin shut down")