#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Conversation Manager for Jarvis Assistant

This module handles the conversation processing for the Jarvis assistant,
coordinating between the NLP engine, memory, and other modules to provide
a coherent conversation experience.
"""

import logging
import re
import time
from typing import Dict, List, Any, Optional, Callable
import yaml
from pathlib import Path
import sqlite3
import chromadb
from sentence_transformers import SentenceTransformer
from loguru import logger

# Import core components
from core.nlp_engine import NLPEngine
from core.memory import Memory

def load_config(path="config/config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)

CONFIG = load_config()

DB_PATH = Path("jarvis_memory.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS memory (
      id INTEGER PRIMARY KEY,
      user TEXT,
      message TEXT,
      response TEXT,
      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()

class ConversationManager:
    """Manages conversations between the user and Jarvis"""
    
    def __init__(self, nlp_engine: NLPEngine, memory: Memory):
        """Initialize the conversation manager
        
        Args:
            nlp_engine: The NLP engine for processing language
            memory: The memory system for context
        """
        self.logger = logging.getLogger("jarvis.conversation")
        self.nlp_engine = nlp_engine
        self.memory = memory
        
        # Voice engine (optional, set via register_voice_engine)
        self.voice_engine = None
        
        # Module registry for handling specific intents
        self.modules = {}
        
        # Command patterns for direct commands
        self.command_patterns = self._initialize_command_patterns()
        
        self.logger.info("Conversation manager initialized")
    
    def _initialize_command_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Initialize command patterns for direct command processing
        
        Returns:
            Dictionary of command patterns and their handlers
        """
        return {
            # System commands
            "exit|quit|shutdown|goodbye": {
                "module": "system",
                "function": "shutdown",
                "description": "Exit or shutdown Jarvis"
            },
            "restart|reboot": {
                "module": "system",
                "function": "restart",
                "description": "Restart Jarvis"
            },
            "status|system status|how are you running": {
                "module": "system",
                "function": "get_status",
                "description": "Get system status"
            },
            
            # Home control commands
            "turn on (the )?(?P<device>.+)": {
                "module": "home_control",
                "function": "turn_on",
                "description": "Turn on a device",
                "args": ["device"]
            },
            "turn off (the )?(?P<device>.+)": {
                "module": "home_control",
                "function": "turn_off",
                "description": "Turn off a device",
                "args": ["device"]
            },
            "set (the )?(?P<device>.+) to (?P<value>.+)": {
                "module": "home_control",
                "function": "set_device",
                "description": "Set a device to a specific value",
                "args": ["device", "value"]
            },
            
            # Media commands
            "play (the )?(song|music|track) (?P<title>.+)": {
                "module": "media",
                "function": "play_music",
                "description": "Play a song",
                "args": ["title"]
            },
            "stop (the )?(music|playback|song|track)": {
                "module": "media",
                "function": "stop_music",
                "description": "Stop music playback"
            },
            
            # Web search commands
            "search (for )?(?P<query>.+)": {
                "module": "web",
                "function": "search",
                "description": "Search the web",
                "args": ["query"]
            },
            "what is (?P<query>.+)": {
                "module": "web",
                "function": "search",
                "description": "Search for information",
                "args": ["query"]
            },
            "who is (?P<query>.+)": {
                "module": "web",
                "function": "search",
                "description": "Search for a person",
                "args": ["query"]
            },
            
            # Time and date commands
            "what (time|day|date) is it|what's the (time|date)": {
                "module": "system",
                "function": "get_time",
                "description": "Get the current time or date"
            },
            
            # Weather commands
            "what('s| is) the weather( like)?( in (?P<location>.+))?": {
                "module": "web",
                "function": "get_weather",
                "description": "Get weather information",
                "args": ["location"]
            },
        }
    
    def register_module(self, name: str, module: Any):
        """Register a module for handling specific intents
        
        Args:
            name: The name of the module
            module: The module instance
        """
        self.modules[name] = module
        self.logger.debug(f"Registered module: {name}")
    
    def register_voice_engine(self, voice_engine: Any):
        """Register the voice engine
        
        Args:
            voice_engine: The voice engine instance
        """
        self.voice_engine = voice_engine
        self.logger.debug("Registered voice engine")
    
    def process_input(self, user_input: str) -> str:
        """Process user input and generate a response
        
        Args:
            user_input: The user's input text
            
        Returns:
            The assistant's response
        """
        if not user_input or user_input.strip() == "":
            return "I didn't catch that. Could you please repeat?"
        
        self.logger.info(f"Processing user input: {user_input}")
        
        # Check for direct commands first
        command_response = self._process_direct_command(user_input)
        if command_response is not None:
            # Add to memory
            self.memory.add_conversation(user_input, command_response)
            return command_response
        
        # Get context for the query
        context = self.memory.get_context_for_query(user_input)
        
        # Process with NLP engine
        response = self.nlp_engine.process_query(user_input, context)
        
        # Add to memory
        self.memory.add_conversation(user_input, response)
        
        return response
    
    def _process_direct_command(self, user_input: str) -> Optional[str]:
        """Process direct commands using regex patterns
        
        Args:
            user_input: The user's input text
            
        Returns:
            Response string if a command was processed, None otherwise
        """
        user_input_lower = user_input.lower()
        
        for pattern, command_info in self.command_patterns.items():
            # Try to match the pattern
            match = re.match(f"^{pattern}$", user_input_lower, re.IGNORECASE)
            if match:
                self.logger.debug(f"Matched command pattern: {pattern}")
                
                # Get module and function
                module_name = command_info["module"]
                function_name = command_info["function"]
                
                # Check if module exists
                if module_name not in self.modules:
                    self.logger.warning(f"Module not found: {module_name}")
                    return f"I'm sorry, but I can't process that command right now. The {module_name} module is not available."
                
                module = self.modules[module_name]
                
                # Check if function exists
                if not hasattr(module, function_name):
                    self.logger.warning(f"Function not found: {function_name} in module {module_name}")
                    return f"I'm sorry, but I can't process that command right now. The {function_name} function is not available."
                
                # Get function
                func = getattr(module, function_name)
                
                # Extract arguments if needed
                if "args" in command_info:
                    args = [match.group(arg) if arg in match.groupdict() else None for arg in command_info["args"]]
                    
                    # Call function with arguments
                    try:
                        result = func(*args)
                        return result
                    except Exception as e:
                        self.logger.error(f"Error executing command: {e}")
                        return f"I'm sorry, but I encountered an error while processing your command: {str(e)}"
                else:
                    # Call function without arguments
                    try:
                        result = func()
                        return result
                    except Exception as e:
                        self.logger.error(f"Error executing command: {e}")
                        return f"I'm sorry, but I encountered an error while processing your command: {str(e)}"
        
        # No command pattern matched
        return None
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze the sentiment of a text
        
        Args:
            text: The text to analyze
            
        Returns:
            Dictionary with sentiment analysis results
        """
        return self.nlp_engine.analyze_sentiment(text)
    
    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities from text
        
        Args:
            text: The text to analyze
            
        Returns:
            List of extracted entities with their types
        """
        return self.nlp_engine.extract_entities(text)
    
    def detect_intent(self, text: str) -> Dict[str, Any]:
        """Detect the intent of a user query
        
        Args:
            text: The user's query
            
        Returns:
            Dictionary with intent information
        """
        return self.nlp_engine.detect_intent(text)
    
    def get_command_help(self) -> str:
        """Get help information about available commands
        
        Returns:
            String with command help information
        """
        help_text = "Here are some commands you can use:\n\n"
        
        for pattern, command_info in self.command_patterns.items():
            # Simplify pattern for display
            display_pattern = pattern.replace("(?P<", "{").replace(">.+)", "}")
            display_pattern = re.sub(r'\(.*?\)\?', '', display_pattern)
            display_pattern = display_pattern.replace("|", " or ")
            
            # Add to help text
            help_text += f"- {display_pattern}: {command_info['description']}\n"
        
        return help_text

client = chromadb.Client()
collection = client.create_collection("jarvis_memory")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

def add_memory(text, memory_id):
    embedding = embedding_model.encode(text)
    collection.add(documents=[text], embeddings=[embedding], ids=[memory_id])

Path("audio_logs").mkdir(exist_ok=True)
Path("screenshots").mkdir(exist_ok=True)

logger.add("jarvis.log", rotation="1 MB")
logger.info("Jarvis started listening")