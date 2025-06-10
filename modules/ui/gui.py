#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GUI Module for Jarvis Assistant

This module provides a graphical user interface for the Jarvis assistant,
allowing for visual interaction with the assistant's capabilities.
"""

import os
import sys
import time
import logging
import threading
from typing import Dict, List, Any, Optional, Callable, Tuple, Union
from datetime import datetime

# Import for GUI
try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox, filedialog
    from PIL import Image, ImageTk
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False

# Import for plotting
try:
    import matplotlib
    matplotlib.use('TkAgg')  # Use TkAgg backend for matplotlib
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


class GUI:
    """Graphical User Interface for Jarvis Assistant"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the GUI
        
        Args:
            config: Configuration dictionary for GUI settings
        """
        self.logger = logging.getLogger("jarvis.ui")
        self.config = config
        
        # Set up GUI configuration
        self.enabled = config.get("enable_gui", True)
        self.theme = config.get("gui_theme", "system")
        self.window_title = config.get("window_title", "Jarvis Assistant")
        self.window_size = config.get("window_size", (800, 600))
        self.icon_path = config.get("icon_path", os.path.join("assets", "icons", "jarvis.ico"))
        self.assets_dir = config.get("assets_dir", os.path.join("assets"))
        
        # GUI components
        self.root = None
        self.main_frame = None
        self.chat_frame = None
        self.status_frame = None
        self.visualization_frame = None
        self.chat_history = None
        self.input_field = None
        self.send_button = None
        self.status_indicators = {}
        self.visualization_canvas = None
        
        # Callback functions
        self.on_send_message = None
        self.on_exit = None
        
        # State variables
        self.is_listening = False
        self.is_speaking = False
        self.is_processing = False
        self.is_running = False
        
        # Initialize GUI if enabled
        if self.enabled and TKINTER_AVAILABLE:
            self._initialize_gui()
        elif self.enabled and not TKINTER_AVAILABLE:
            self.logger.error("GUI enabled but tkinter is not available. Install tkinter to use GUI.")
            self.enabled = False
        else:
            self.logger.info("GUI disabled in configuration")
    
    def _initialize_gui(self):
        """Initialize the GUI components"""
        # Create root window
        self.root = tk.Tk()
        self.root.title(self.window_title)
        self.root.geometry(f"{self.window_size[0]}x{self.window_size[1]}")
        
        # Set window icon if available
        if os.path.exists(self.icon_path):
            try:
                icon = ImageTk.PhotoImage(file=self.icon_path)
                self.root.iconphoto(True, icon)
            except Exception as e:
                self.logger.error(f"Error setting window icon: {e}")
        
        # Set theme
        self._set_theme()
        
        # Create main frame
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create layout
        self._create_layout()
        
        # Set up event handlers
        self._setup_event_handlers()
        
        # Protocol for window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self.logger.info("GUI initialized")
    
    def _set_theme(self):
        """Set the GUI theme"""
        try:
            # Check if ttk has themed styles
            style = ttk.Style()
            
            # Set theme based on configuration
            if self.theme == "dark":
                # Dark theme (if available)
                try:
                    style.theme_use("clam")
                    style.configure(".", background="#2E2E2E", foreground="#FFFFFF")
                    style.configure("TFrame", background="#2E2E2E")
                    style.configure("TButton", background="#5E5E5E", foreground="#FFFFFF")
                    style.configure("TLabel", background="#2E2E2E", foreground="#FFFFFF")
                    style.configure("TEntry", fieldbackground="#3E3E3E", foreground="#FFFFFF")
                    
                    # Configure root window colors
                    self.root.configure(background="#2E2E2E")
                except Exception as e:
                    self.logger.error(f"Error setting dark theme: {e}")
                    style.theme_use("clam")  # Fallback to clam theme
            
            elif self.theme == "light":
                # Light theme
                try:
                    style.theme_use("clam")
                    style.configure(".", background="#F0F0F0", foreground="#000000")
                    style.configure("TFrame", background="#F0F0F0")
                    style.configure("TButton", background="#E0E0E0", foreground="#000000")
                    style.configure("TLabel", background="#F0F0F0", foreground="#000000")
                    style.configure("TEntry", fieldbackground="#FFFFFF", foreground="#000000")
                    
                    # Configure root window colors
                    self.root.configure(background="#F0F0F0")
                except Exception as e:
                    self.logger.error(f"Error setting light theme: {e}")
                    style.theme_use("clam")  # Fallback to clam theme
            
            else:
                # System theme (default)
                available_themes = style.theme_names()
                if "vista" in available_themes and sys.platform == "win32":
                    style.theme_use("vista")
                elif "aqua" in available_themes and sys.platform == "darwin":
                    style.theme_use("aqua")
                elif "clam" in available_themes:
                    style.theme_use("clam")
        
        except Exception as e:
            self.logger.error(f"Error setting theme: {e}")
    
    def _create_layout(self):
        """Create the GUI layout"""
        # Create frames for different sections
        self._create_status_frame()
        self._create_chat_frame()
        self._create_visualization_frame()
    
    def _create_status_frame(self):
        """Create the status frame with indicators"""
        # Status frame at the top
        self.status_frame = ttk.LabelFrame(self.main_frame, text="Status")
        self.status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Status indicators
        status_items = [
            ("system", "System"),
            ("listening", "Listening"),
            ("speaking", "Speaking"),
            ("processing", "Processing"),
            ("network", "Network"),
            ("home", "Smart Home")
        ]
        
        # Create status indicators
        for i, (key, label) in enumerate(status_items):
            frame = ttk.Frame(self.status_frame)
            frame.grid(row=0, column=i, padx=10, pady=5)
            
            # Create colored indicator
            indicator = tk.Canvas(frame, width=15, height=15, bg="gray", highlightthickness=0)
            indicator.pack(side=tk.LEFT, padx=2)
            
            # Create label
            label_widget = ttk.Label(frame, text=label)
            label_widget.pack(side=tk.LEFT, padx=2)
            
            # Store indicator reference
            self.status_indicators[key] = indicator
        
        # Set initial status
        self.update_status("system", "online")
    
    def _create_chat_frame(self):
        """Create the chat interface frame"""
        # Chat frame in the middle
        self.chat_frame = ttk.LabelFrame(self.main_frame, text="Conversation")
        self.chat_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Chat history display
        self.chat_history = scrolledtext.ScrolledText(
            self.chat_frame,
            wrap=tk.WORD,
            width=40,
            height=10,
            font=("TkDefaultFont", 10)
        )
        self.chat_history.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.chat_history.config(state=tk.DISABLED)  # Make it read-only
        
        # Input frame at the bottom of chat frame
        input_frame = ttk.Frame(self.chat_frame)
        input_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Text input field
        self.input_field = ttk.Entry(input_frame)
        self.input_field.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # Send button
        self.send_button = ttk.Button(
            input_frame,
            text="Send",
            command=self._on_send
        )
        self.send_button.pack(side=tk.RIGHT)
        
        # Bind Enter key to send message
        self.input_field.bind("<Return>", lambda event: self._on_send())
        
        # Voice button
        self.voice_button = ttk.Button(
            input_frame,
            text="🎤",  # Microphone emoji
            width=3,
            command=self._on_voice_button
        )
        self.voice_button.pack(side=tk.RIGHT, padx=5)
    
    def _create_visualization_frame(self):
        """Create the visualization frame"""
        # Visualization frame at the bottom
        self.visualization_frame = ttk.LabelFrame(self.main_frame, text="Visualization")
        self.visualization_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Notebook for different visualizations
        self.notebook = ttk.Notebook(self.visualization_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # System tab
        self.system_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.system_tab, text="System")
        
        # Create system visualization if matplotlib is available
        if MATPLOTLIB_AVAILABLE:
            self._create_system_visualization()
        else:
            ttk.Label(self.system_tab, text="Matplotlib not available for system visualization").pack(pady=20)
        
        # Camera tab
        self.camera_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.camera_tab, text="Camera")
        
        # Create camera display
        self.camera_label = ttk.Label(self.camera_tab)
        self.camera_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Home tab
        self.home_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.home_tab, text="Smart Home")
        
        # Create home visualization placeholder
        ttk.Label(self.home_tab, text="Smart Home visualization will appear here").pack(pady=20)
    
    def _create_system_visualization(self):
        """Create system monitoring visualization"""
        # Create matplotlib figure
        self.system_fig = Figure(figsize=(5, 4), dpi=100)
        
        # CPU subplot
        self.cpu_ax = self.system_fig.add_subplot(2, 1, 1)
        self.cpu_ax.set_title("CPU Usage")
        self.cpu_ax.set_ylim(0, 100)
        self.cpu_ax.set_ylabel("Usage %")
        self.cpu_line, = self.cpu_ax.plot([], [], 'b-')
        
        # Memory subplot
        self.mem_ax = self.system_fig.add_subplot(2, 1, 2)
        self.mem_ax.set_title("Memory Usage")
        self.mem_ax.set_ylim(0, 100)
        self.mem_ax.set_ylabel("Usage %")
        self.mem_line, = self.mem_ax.plot([], [], 'g-')
        
        # Adjust layout
        self.system_fig.tight_layout()
        
        # Create canvas
        self.system_canvas = FigureCanvasTkAgg(self.system_fig, master=self.system_tab)
        self.system_canvas.draw()
        self.system_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Initialize data
        self.cpu_data = [0] * 60  # 60 data points
        self.mem_data = [0] * 60
    
    def _setup_event_handlers(self):
        """Set up event handlers for GUI components"""
        # Add menu bar
        self._create_menu()
    
    def _create_menu(self):
        """Create the menu bar"""
        # Create menu bar
        menubar = tk.Menu(self.root)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Settings", command=self._show_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Clear Chat", command=self._clear_chat)
        menubar.add_cascade(label="View", menu=view_menu)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        help_menu.add_command(label="Help", command=self._show_help)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        # Set the menu bar
        self.root.config(menu=menubar)
    
    def _on_send(self):
        """Handle send button click or Enter key press"""
        # Get message from input field
        message = self.input_field.get().strip()
        
        # Clear input field
        self.input_field.delete(0, tk.END)
        
        # If message is empty, do nothing
        if not message:
            return
        
        # Add message to chat history
        self.add_message("You", message)
        
        # Call the message callback if registered
        if self.on_send_message:
            self.on_send_message(message)
    
    def _on_voice_button(self):
        """Handle voice button click"""
        # Toggle listening state
        self.is_listening = not self.is_listening
        
        # Update button appearance based on state
        if self.is_listening:
            self.voice_button.configure(text="⏹️")  # Stop emoji
            self.update_status("listening", "active")
        else:
            self.voice_button.configure(text="🎤")  # Microphone emoji
            self.update_status("listening", "inactive")
    
    def _on_close(self):
        """Handle window close event"""
        # Call the exit callback if registered
        if self.on_exit:
            self.on_exit()
        
        # Destroy the window
        if self.root:
            self.root.destroy()
            self.root = None
        
        self.is_running = False
        self.logger.info("GUI closed")
    
    def _show_settings(self):
        """Show settings dialog"""
        # Create settings dialog
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Settings")
        settings_window.geometry("400x300")
        settings_window.transient(self.root)  # Make it modal
        settings_window.grab_set()
        
        # Create settings notebook
        settings_notebook = ttk.Notebook(settings_window)
        settings_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # General settings tab
        general_tab = ttk.Frame(settings_notebook)
        settings_notebook.add(general_tab, text="General")
        
        # Theme setting
        ttk.Label(general_tab, text="Theme:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        theme_var = tk.StringVar(value=self.theme)
        theme_combo = ttk.Combobox(general_tab, textvariable=theme_var, values=["system", "light", "dark"])
        theme_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Voice settings tab
        voice_tab = ttk.Frame(settings_notebook)
        settings_notebook.add(voice_tab, text="Voice")
        
        # Enable voice checkbox
        voice_enabled_var = tk.BooleanVar(value=self.config.get("enable_voice", True))
        ttk.Checkbutton(voice_tab, text="Enable Voice", variable=voice_enabled_var).grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=5
        )
        
        # Wake word setting
        ttk.Label(voice_tab, text="Wake Word:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        wake_word_var = tk.StringVar(value=self.config.get("wake_word", "Jarvis"))
        ttk.Entry(voice_tab, textvariable=wake_word_var).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Buttons frame
        buttons_frame = ttk.Frame(settings_window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Save button
        ttk.Button(
            buttons_frame,
            text="Save",
            command=lambda: self._save_settings(
                settings_window,
                {
                    "gui_theme": theme_var.get(),
                    "enable_voice": voice_enabled_var.get(),
                    "wake_word": wake_word_var.get()
                }
            )
        ).pack(side=tk.RIGHT, padx=5)
        
        # Cancel button
        ttk.Button(
            buttons_frame,
            text="Cancel",
            command=settings_window.destroy
        ).pack(side=tk.RIGHT, padx=5)
    
    def _save_settings(self, window, settings):
        """Save settings and close the settings window
        
        Args:
            window: Settings window to close
            settings: Dictionary of settings to save
        """
        # Update config
        self.config.update(settings)
        
        # Update theme if changed
        if settings.get("gui_theme") != self.theme:
            self.theme = settings.get("gui_theme")
            self._set_theme()
        
        # Close window
        window.destroy()
        
        # Log settings change
        self.logger.info("Settings updated")
    
    def _show_about(self):
        """Show about dialog"""
        messagebox.showinfo(
            "About Jarvis Assistant",
            "Jarvis Assistant\n\n"
            "A personal AI assistant inspired by Iron Man's JARVIS.\n\n"
            "Version: 1.0.0\n"
            "© 2023 Jarvis Project"
        )
    
    def _show_help(self):
        """Show help dialog"""
        help_text = """\
Jarvis Assistant Help

Voice Commands:
- Say "Jarvis" followed by your command
- Example: "Jarvis, what's the weather today?"

Text Commands:
- Type your command in the input field and press Enter or click Send
- You can omit "Jarvis" when typing commands

Common Commands:
- "What time is it?" - Get the current time
- "What's the weather in [location]?" - Get weather information
- "Open [program]" - Open a program or application
- "Search for [query]" - Search the web
- "Tell me about [topic]" - Get information about a topic
- "Turn on/off [device]" - Control smart home devices
- "System status" - Get system information
- "Help" - Show this help dialog
"""
        
        # Create help window
        help_window = tk.Toplevel(self.root)
        help_window.title("Jarvis Help")
        help_window.geometry("500x400")
        help_window.transient(self.root)  # Make it modal
        
        # Create text widget
        help_text_widget = scrolledtext.ScrolledText(
            help_window,
            wrap=tk.WORD,
            width=60,
            height=20,
            font=("TkDefaultFont", 10)
        )
        help_text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Insert help text
        help_text_widget.insert(tk.END, help_text)
        help_text_widget.config(state=tk.DISABLED)  # Make it read-only
        
        # Close button
        ttk.Button(
            help_window,
            text="Close",
            command=help_window.destroy
        ).pack(pady=10)
    
    def _clear_chat(self):
        """Clear the chat history"""
        self.chat_history.config(state=tk.NORMAL)
        self.chat_history.delete(1.0, tk.END)
        self.chat_history.config(state=tk.DISABLED)
    
    def add_message(self, sender: str, message: str):
        """Add a message to the chat history
        
        Args:
            sender: Name of the message sender
            message: Message content
        """
        if not self.enabled or not self.root:
            return
        
        # Enable editing
        self.chat_history.config(state=tk.NORMAL)
        
        # Add timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Format message
        formatted_message = f"[{timestamp}] {sender}: {message}\n\n"
        
        # Insert message at the end
        self.chat_history.insert(tk.END, formatted_message)
        
        # Auto-scroll to the end
        self.chat_history.see(tk.END)
        
        # Disable editing
        self.chat_history.config(state=tk.DISABLED)
    
    def update_status(self, status_key: str, state: str):
        """Update a status indicator
        
        Args:
            status_key: Key of the status indicator to update
            state: New state ("online", "offline", "active", "inactive", "error")
        """
        if not self.enabled or not self.root or status_key not in self.status_indicators:
            return
        
        # Get indicator canvas
        indicator = self.status_indicators[status_key]
        
        # Set color based on state
        if state == "online" or state == "active":
            color = "green"
        elif state == "offline" or state == "inactive":
            color = "gray"
        elif state == "error":
            color = "red"
        elif state == "warning":
            color = "orange"
        else:
            color = "blue"
        
        # Update indicator color
        indicator.config(bg=color)
    
    def update_system_chart(self, cpu_percent: float, memory_percent: float):
        """Update the system monitoring chart
        
        Args:
            cpu_percent: CPU usage percentage
            memory_percent: Memory usage percentage
        """
        if not self.enabled or not self.root or not MATPLOTLIB_AVAILABLE:
            return
        
        # Update data
        self.cpu_data.pop(0)
        self.cpu_data.append(cpu_percent)
        
        self.mem_data.pop(0)
        self.mem_data.append(memory_percent)
        
        # Update plot data
        self.cpu_line.set_data(range(len(self.cpu_data)), self.cpu_data)
        self.mem_line.set_data(range(len(self.mem_data)), self.mem_data)
        
        # Adjust x-axis limits
        self.cpu_ax.set_xlim(0, len(self.cpu_data) - 1)
        self.mem_ax.set_xlim(0, len(self.mem_data) - 1)
        
        # Redraw canvas
        self.system_canvas.draw()
    
    def update_camera_feed(self, frame):
        """Update the camera feed display
        
        Args:
            frame: Image frame to display (PIL Image or numpy array)
        """
        if not self.enabled or not self.root:
            return
        
        try:
            # Convert frame to PhotoImage
            if hasattr(frame, "convert"):
                # It's already a PIL Image
                pil_image = frame
            else:
                # Convert numpy array to PIL Image
                from PIL import Image
                pil_image = Image.fromarray(frame)
            
            # Resize image to fit the display
            width, height = self.camera_tab.winfo_width(), self.camera_tab.winfo_height()
            if width > 1 and height > 1:  # Ensure valid dimensions
                pil_image = pil_image.resize((width, height), Image.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(pil_image)
            
            # Update label
            self.camera_label.config(image=photo)
            self.camera_label.image = photo  # Keep a reference to prevent garbage collection
        
        except Exception as e:
            self.logger.error(f"Error updating camera feed: {e}")
    
    def update_home_devices(self, devices: List[Dict[str, Any]]):
        """Update the smart home devices display
        
        Args:
            devices: List of device dictionaries with name, type, and state
        """
        if not self.enabled or not self.root:
            return
        
        # Clear existing widgets
        for widget in self.home_tab.winfo_children():
            widget.destroy()
        
        # Create scrollable frame
        canvas = tk.Canvas(self.home_tab)
        scrollbar = ttk.Scrollbar(self.home_tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Add devices
        for i, device in enumerate(devices):
            device_frame = ttk.Frame(scrollable_frame)
            device_frame.pack(fill=tk.X, padx=5, pady=5)
            
            # Device name and type
            ttk.Label(
                device_frame,
                text=f"{device['name']} ({device['type']})"
            ).pack(side=tk.LEFT, padx=5)
            
            # Device state
            if device['type'] in ['light', 'switch', 'outlet']:
                # Toggle button for binary devices
                state_var = tk.BooleanVar(value=device['state'] == 'on')
                ttk.Checkbutton(
                    device_frame,
                    variable=state_var,
                    text="On" if state_var.get() else "Off",
                    command=lambda d=device, v=state_var: self._on_device_toggle(d, v)
                ).pack(side=tk.RIGHT, padx=5)
            
            elif device['type'] in ['thermostat']:
                # Slider for thermostat
                ttk.Label(
                    device_frame,
                    text=f"{device['state']}°"
                ).pack(side=tk.RIGHT, padx=5)
                
                slider = ttk.Scale(
                    device_frame,
                    from_=10,
                    to=30,
                    orient=tk.HORIZONTAL,
                    value=float(device['state']),
                    command=lambda v, d=device: self._on_thermostat_change(d, v)
                )
                slider.pack(side=tk.RIGHT, padx=5)
            
            else:
                # Simple state display for other devices
                ttk.Label(
                    device_frame,
                    text=f"State: {device['state']}"
                ).pack(side=tk.RIGHT, padx=5)
    
    def _on_device_toggle(self, device: Dict[str, Any], state_var: tk.BooleanVar):
        """Handle device toggle button click
        
        Args:
            device: Device dictionary
            state_var: State variable from the toggle button
        """
        # Log device toggle
        new_state = "on" if state_var.get() else "off"
        self.logger.info(f"Device {device['name']} toggled to {new_state}")
        
        # Here you would call a callback to actually control the device
        # This is just a placeholder for the UI demonstration
    
    def _on_thermostat_change(self, device: Dict[str, Any], value):
        """Handle thermostat slider change
        
        Args:
            device: Device dictionary
            value: New temperature value
        """
        # Log thermostat change
        self.logger.info(f"Thermostat {device['name']} set to {float(value):.1f}°")
        
        # Here you would call a callback to actually control the thermostat
        # This is just a placeholder for the UI demonstration
    
    def register_callbacks(self, on_send_message: Callable[[str], None] = None, on_exit: Callable[[], None] = None):
        """Register callback functions
        
        Args:
            on_send_message: Callback for when a message is sent
            on_exit: Callback for when the GUI is closed
        """
        self.on_send_message = on_send_message
        self.on_exit = on_exit
    
    def run(self):
        """Run the GUI main loop"""
        if not self.enabled or not self.root:
            return
        
        self.is_running = True
        
        try:
            self.root.mainloop()
        except Exception as e:
            self.logger.error(f"Error in GUI main loop: {e}")
            self.is_running = False
    
    def run_in_thread(self):
        """Run the GUI in a separate thread"""
        if not self.enabled or not self.root:
            return
        
        # Create and start thread
        self.gui_thread = threading.Thread(target=self.run, daemon=True)
        self.gui_thread.start()
        
        self.logger.info("GUI started in separate thread")
    
    def update(self):
        """Update the GUI (call periodically if running in main thread)"""
        if not self.enabled or not self.root:
            return
        
        # Process pending events
        self.root.update_idletasks()
        self.root.update()
    
    def shutdown(self):
        """Shutdown the GUI"""
        if self.root:
            self.root.quit()
            self.root.destroy()
            self.root = None
        
        self.is_running = False
        self.logger.info("GUI shut down")