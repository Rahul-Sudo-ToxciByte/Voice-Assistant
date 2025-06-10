#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Command Line Interface for Jarvis Assistant

This module provides a text-based interface for interacting with the Jarvis assistant
through the command line, useful for systems without GUI support or for users who
prefer terminal-based interaction.
"""

import os
import sys
import time
import logging
import threading
from typing import Dict, List, Any, Optional, Callable, Tuple, Union
from datetime import datetime
import re
import signal

# Try to import readline for better input handling
try:
    import readline
    READLINE_AVAILABLE = True
except ImportError:
    READLINE_AVAILABLE = False

# Try to import colorama for colored output
try:
    from colorama import init, Fore, Back, Style
    init()  # Initialize colorama
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False


class CLI:
    """Command Line Interface for Jarvis Assistant"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the CLI
        
        Args:
            config: Configuration dictionary for CLI settings
        """
        self.logger = logging.getLogger("jarvis.ui.cli")
        self.config = config
        
        # Set up CLI configuration
        self.enabled = config.get("enable_cli", True)
        self.prompt = config.get("cli_prompt", "Jarvis> ")
        self.history_file = config.get("cli_history_file", os.path.join("data", "cli_history"))
        self.max_history = config.get("cli_max_history", 1000)
        self.use_colors = config.get("cli_use_colors", True) and COLORAMA_AVAILABLE
        
        # Callback functions
        self.on_command = None
        self.on_exit = None
        
        # State variables
        self.is_running = False
        self.is_listening = False
        self.is_speaking = False
        self.is_processing = False
        
        # Command history
        self.command_history = []
        
        # Initialize readline if available
        if READLINE_AVAILABLE:
            self._setup_readline()
        
        self.logger.info(f"CLI initialized (enabled: {self.enabled})")
    
    def _setup_readline(self):
        """Set up readline for command history and tab completion"""
        # Set up command history
        try:
            # Create history file directory if it doesn't exist
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            
            # Load history file if it exists
            if os.path.exists(self.history_file):
                readline.read_history_file(self.history_file)
                # Truncate history if it's too long
                if readline.get_current_history_length() > self.max_history:
                    readline.clear_history()
                    self.logger.info("History file too long, cleared")
            
            # Set history file for writing
            readline.set_history_length(self.max_history)
            
        except Exception as e:
            self.logger.error(f"Error setting up readline history: {e}")
        
        # Set up tab completion
        readline.parse_and_bind("tab: complete")
        readline.set_completer(self._completer)
    
    def _completer(self, text, state):
        """Tab completion function for readline
        
        Args:
            text: Text to complete
            state: State of completion (0 for first match, 1 for second, etc.)
            
        Returns:
            Possible completion or None if no more completions
        """
        # List of common commands for tab completion
        commands = [
            "help", "exit", "quit", "clear", "status", "history",
            "weather", "time", "date", "search", "system", "memory",
            "home", "device", "camera", "vision", "knowledge",
            "remind", "alarm", "timer", "volume", "mute", "unmute"
        ]
        
        # Filter commands that start with the text
        matches = [cmd for cmd in commands if cmd.startswith(text.lower())]
        
        # Return the state-th match or None if no more matches
        if state < len(matches):
            return matches[state]
        else:
            return None
    
    def _save_history(self):
        """Save command history to file"""
        if READLINE_AVAILABLE:
            try:
                readline.write_history_file(self.history_file)
            except Exception as e:
                self.logger.error(f"Error saving history file: {e}")
    
    def _print_colored(self, text: str, color: str = None, style: str = None):
        """Print colored text if colorama is available
        
        Args:
            text: Text to print
            color: Text color (default: None)
            style: Text style (default: None)
        """
        if self.use_colors and COLORAMA_AVAILABLE:
            # Set color
            color_code = ""
            if color:
                color = color.upper()
                if hasattr(Fore, color):
                    color_code += getattr(Fore, color)
            
            # Set style
            style_code = ""
            if style:
                style = style.upper()
                if hasattr(Style, style):
                    style_code += getattr(Style, style)
            
            # Print with color and style
            print(f"{color_code}{style_code}{text}{Style.RESET_ALL}")
        else:
            # Print without color
            print(text)
    
    def _print_header(self):
        """Print the CLI header"""
        if self.use_colors and COLORAMA_AVAILABLE:
            print(f"{Fore.CYAN}{Style.BRIGHT}")
        
        print("""
    ╔════════════════════════════════════════════════════════════╗
    ║                   JARVIS ASSISTANT CLI                    ║
    ╚════════════════════════════════════════════════════════════╝
    """)
        
        if self.use_colors and COLORAMA_AVAILABLE:
            print(f"{Style.RESET_ALL}")
        
        print("Type 'help' for a list of commands or 'exit' to quit.\n")
    
    def _print_help(self):
        """Print help information"""
        help_text = """
Available Commands:
-----------------
help                 - Show this help message
exit, quit           - Exit the assistant
clear                - Clear the screen
status               - Show system status
history              - Show command history

General Commands:
---------------
time                 - Show current time
date                 - Show current date
weather [location]   - Show weather information
search <query>       - Search the web

System Commands:
--------------
system status        - Show system information
system memory        - Show memory usage
system cpu           - Show CPU usage
system disk          - Show disk usage

Home Automation:
--------------
home list            - List all devices
home status          - Show status of all devices
device <name> on     - Turn on a device
device <name> off    - Turn off a device

Other Commands:
-------------
camera on            - Turn on camera
camera off           - Turn off camera
vision on            - Enable vision processing
vision off           - Disable vision processing
knowledge <query>    - Query knowledge base

Note: You can also just type natural language commands.
"""
        self._print_colored(help_text, "cyan")
    
    def _handle_command(self, command: str):
        """Handle a command
        
        Args:
            command: Command to handle
        """
        # Strip whitespace
        command = command.strip()
        
        # Skip empty commands
        if not command:
            return
        
        # Add to history
        self.command_history.append(command)
        
        # Handle built-in commands
        if command.lower() in ["exit", "quit"]:
            self._print_colored("Exiting Jarvis Assistant...", "yellow")
            self.stop()
            return
        
        elif command.lower() == "help":
            self._print_help()
            return
        
        elif command.lower() == "clear":
            os.system("cls" if os.name == "nt" else "clear")
            self._print_header()
            return
        
        elif command.lower() == "status":
            self._show_status()
            return
        
        elif command.lower() == "history":
            self._show_history()
            return
        
        # Call the command callback if registered
        if self.on_command:
            self.is_processing = True
            self._print_colored("Processing...", "yellow")
            self.on_command(command)
            self.is_processing = False
    
    def _show_status(self):
        """Show system status"""
        status_text = """
System Status:
-------------
Running: {running}
Listening: {listening}
Speaking: {speaking}
Processing: {processing}
""".format(
            running=self.is_running,
            listening=self.is_listening,
            speaking=self.is_speaking,
            processing=self.is_processing
        )
        
        self._print_colored(status_text, "green")
    
    def _show_history(self):
        """Show command history"""
        if not self.command_history:
            self._print_colored("No command history", "yellow")
            return
        
        history_text = "\nCommand History:\n---------------\n"
        for i, cmd in enumerate(self.command_history[-20:], 1):
            history_text += f"{i}. {cmd}\n"
        
        self._print_colored(history_text, "cyan")
    
    def display_response(self, response: str, is_error: bool = False):
        """Display a response from the assistant
        
        Args:
            response: Response text
            is_error: Whether the response is an error message
        """
        if not self.enabled:
            return
        
        # Format timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Print response with timestamp
        if is_error:
            self._print_colored(f"[{timestamp}] Error: {response}", "red")
        else:
            self._print_colored(f"[{timestamp}] Jarvis: {response}", "green")
    
    def update_status(self, status_type: str, value: bool):
        """Update a status indicator
        
        Args:
            status_type: Type of status to update (listening, speaking, processing)
            value: New status value
        """
        if not self.enabled:
            return
        
        if status_type == "listening":
            self.is_listening = value
            if value:
                self._print_colored("[Listening...]", "blue")
            else:
                self._print_colored("[Stopped listening]", "blue")
        
        elif status_type == "speaking":
            self.is_speaking = value
        
        elif status_type == "processing":
            self.is_processing = value
    
    def register_callbacks(self, on_command: Callable[[str], None] = None, on_exit: Callable[[], None] = None):
        """Register callback functions
        
        Args:
            on_command: Callback for when a command is entered
            on_exit: Callback for when the CLI is exited
        """
        self.on_command = on_command
        self.on_exit = on_exit
    
    def run(self):
        """Run the CLI main loop"""
        if not self.enabled:
            return
        
        self.is_running = True
        
        # Print header
        self._print_header()
        
        # Set up signal handler for Ctrl+C
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Main loop
        while self.is_running:
            try:
                # Get command from user
                command = input(self.prompt)
                
                # Handle command
                self._handle_command(command)
                
            except EOFError:
                # Ctrl+D
                print("\n")
                self.stop()
                break
            
            except KeyboardInterrupt:
                # Ctrl+C (should be handled by signal handler)
                pass
            
            except Exception as e:
                self.logger.error(f"Error in CLI main loop: {e}")
                self._print_colored(f"Error: {e}", "red")
        
        # Save history before exiting
        self._save_history()
    
    def _signal_handler(self, sig, frame):
        """Handle signals (e.g., Ctrl+C)
        
        Args:
            sig: Signal number
            frame: Current stack frame
        """
        print("\n")
        self.stop()
    
    def run_in_thread(self):
        """Run the CLI in a separate thread"""
        if not self.enabled:
            return
        
        # Create and start thread
        self.cli_thread = threading.Thread(target=self.run, daemon=True)
        self.cli_thread.start()
        
        self.logger.info("CLI started in separate thread")
    
    def stop(self):
        """Stop the CLI"""
        self.is_running = False
        
        # Call the exit callback if registered
        if self.on_exit:
            self.on_exit()
        
        self.logger.info("CLI stopped")
    
    def shutdown(self):
        """Shutdown the CLI"""
        self.stop()
        
        # Save history
        self._save_history()
        
        self.logger.info("CLI shut down")