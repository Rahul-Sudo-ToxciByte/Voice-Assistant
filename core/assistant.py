#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Jarvis Assistant Core

This module contains the main JarvisAssistant class that coordinates all the
functionality of the Jarvis AI assistant.
"""

import logging
import time
import threading
from typing import Dict, List, Optional, Any

# Import core components
from core.memory import Memory
from core.nlp_engine import NLPEngine
from core.voice_engine import VoiceEngine

# Import modules
from modules.conversation.manager import ConversationManager
from modules.vision.vision_system import VisionSystem
from modules.knowledge.knowledge_base import KnowledgeBase
from modules.home.home_controller import HomeController
from modules.system.system_monitor import SystemMonitor
from modules.web.web_services import WebServices

# Import UI
from modules.ui.gui import GUI


class JarvisAssistant:
    """Main Jarvis Assistant class that coordinates all functionality"""
    
    def __init__(
        self,
        config: Dict[str, Any],
        enable_voice: bool = True,
        enable_gui: bool = True,
        debug_mode: bool = False
    ):
        """Initialize the Jarvis Assistant
        
        Args:
            config: Configuration dictionary
            enable_voice: Whether to enable voice interaction
            enable_gui: Whether to enable the GUI
            debug_mode: Whether to run in debug mode
        """
        self.logger = logging.getLogger("jarvis.assistant")
        self.config = config
        self.enable_voice = enable_voice
        self.enable_gui = enable_gui
        self.debug_mode = debug_mode
        
        self.running = False
        self.initialized = False
        
        # Initialize core components
        self.logger.info("Initializing core components...")
        self.memory = Memory(config.get("memory", {}))
        self.nlp_engine = NLPEngine(config.get("nlp", {}))
        
        if enable_voice:
            self.voice_engine = VoiceEngine(config.get("voice", {}))
        else:
            self.voice_engine = None
            self.logger.info("Voice interaction disabled")
        
        # Initialize modules
        self.logger.info("Initializing modules...")
        self.conversation = ConversationManager(self.nlp_engine, self.memory)
        self.vision = VisionSystem(config.get("vision", {}))
        self.knowledge = KnowledgeBase(config.get("knowledge", {}))
        self.home_control = HomeController(config.get("home_control", {}))
        self.system_monitor = SystemMonitor(config.get("system", {}))
        self.web_services = WebServices(config.get("web_services", {}))
        
        # Initialize UI
        if enable_gui:
            self.interface = GUI(config.get("ui", {}))
        else:
            self.interface = None
            self.logger.info("GUI disabled")
        
        # Register modules with each other as needed
        self._register_modules()
        
        self.initialized = True
        self.logger.info("Jarvis Assistant initialized successfully")
    
    def _register_modules(self):
        """Register modules with each other for inter-module communication"""
        # Register modules with conversation manager
        self.conversation.register_module("vision", self.vision)
        self.conversation.register_module("knowledge", self.knowledge)
        self.conversation.register_module("home_control", self.home_control)
        self.conversation.register_module("system", self.system_monitor)
        self.conversation.register_module("web", self.web_services)
        
        # Register voice engine with conversation
        if self.voice_engine:
            self.conversation.register_voice_engine(self.voice_engine)
    
    def run(self):
        """Run the assistant"""
        if not self.initialized:
            self.logger.error("Cannot run: Jarvis not properly initialized")
            return
        
        self.running = True
        
        # Start system monitoring
        self.system_monitor._start_monitoring()
        
        # Start voice engine if enabled
        if self.voice_engine:
            self.voice_engine.start()
            self.voice_engine.set_wake_word_callback(self._wake_word_detected)
        
        # Start UI if enabled
        if self.interface:
            # Use run_in_thread for GUI, run for CLI
            if hasattr(self.interface, 'run_in_thread'):
                self.interface.run_in_thread()
            elif hasattr(self.interface, 'run'):
                self.interface.run()
        
        # Main loop - keep running until shutdown
        try:
            while self.running:
                # This loop keeps the main thread alive
                # Most processing happens in other threads
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.shutdown()
    
    def _wake_word_detected(self):
        """Callback for when wake word is detected"""
        self.logger.info("Wake word detected")
        
        if self.voice_engine:
            # Activate voice listening
            self.voice_engine.listen_for_command(self._process_voice_command)
            
            # Visual feedback
            if self.interface:
                self.interface.show_listening()
    
    def _process_voice_command(self, command: str):
        """Process a voice command"""
        if not command:
            self.logger.debug("Empty command received")
            return
        
        self.logger.info(f"Processing command: {command}")
        
        # Process the command through conversation manager
        response = self.conversation.process_input(command)
        
        # Speak the response if voice is enabled
        if self.voice_engine:
            self.voice_engine.speak(response)
        
        # Update UI if enabled
        if self.interface:
            self.interface.update_conversation(command, response)
    
    def process_text_input(self, text: str) -> str:
        """Process text input from the UI
        
        Args:
            text: The text input to process
            
        Returns:
            The response from the assistant
        """
        self.logger.info(f"Processing text input: {text}")
        
        # Process through conversation manager
        response = self.conversation.process_input(text)
        
        # Update UI if enabled
        if self.interface:
            self.interface.update_conversation(text, response)
        
        return response
    
    def shutdown(self):
        """Shutdown the assistant and all its components"""
        self.logger.info("Shutting down Jarvis...")
        self.running = False
        
        # Shutdown voice engine
        if self.voice_engine:
            self.voice_engine.stop()
        
        # Shutdown system monitoring
        self.system_monitor.shutdown()
        
        # Shutdown UI
        if self.interface:
            if hasattr(self.interface, 'shutdown'):
                self.interface.shutdown()
            elif hasattr(self.interface, 'stop'):
                self.interface.stop()
        
        # Save memory and other persistent data
        self.memory.save()
        self.knowledge.save()
        
        self.logger.info("Jarvis shutdown complete")