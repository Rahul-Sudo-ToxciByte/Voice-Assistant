# -*- coding: utf-8 -*-

"""
Plugin Base Class

This module provides the base class for all Jarvis plugins.
"""

import os
import json
from typing import Dict, List, Any, Optional

class PluginBase:
    """
    Base class for all Jarvis plugins.
    
    All plugins should inherit from this class and implement the required methods.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the plugin with configuration.
        
        Args:
            config: Dictionary containing plugin configuration
        """
        self.config = config
        self.name = "base_plugin"  # Should be overridden by child classes
        self.description = "Base plugin class"  # Should be overridden by child classes
        self.version = "1.0.0"  # Should be overridden by child classes
        self.author = "Jarvis"  # Should be overridden by child classes
        self.enabled = True
        
    def get_info(self) -> Dict[str, Any]:
        """
        Get plugin information.
        
        Returns:
            Dictionary containing plugin information
        """
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "enabled": self.enabled
        }
    
    def process_intent(self, intent: str, entities: Dict[str, Any], text: str) -> Dict[str, Any]:
        """
        Process an intent with entities.
        
        Args:
            intent: The detected intent
            entities: Dictionary of entities extracted from the text
            text: The original text input
            
        Returns:
            Response dictionary
        """
        # This should be implemented by child classes
        return {"error": "Not implemented"}
    
    def execute_command(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a command with parameters.
        
        Args:
            command: The command to execute
            params: Dictionary of parameters for the command
            
        Returns:
            Response dictionary
        """
        # This should be implemented by child classes
        return {"error": "Command not supported"}
    
    def initialize(self) -> bool:
        """
        Initialize the plugin. Called when the plugin is loaded.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        return True
    
    def shutdown(self) -> bool:
        """
        Shutdown the plugin. Called when the plugin is unloaded.
        
        Returns:
            True if shutdown was successful, False otherwise
        """
        return True
    
    def get_commands(self) -> List[str]:
        """
        Get a list of commands supported by this plugin.
        
        Returns:
            List of command names
        """
        return []
    
    def get_intents(self) -> List[str]:
        """
        Get a list of intents supported by this plugin.
        
        Returns:
            List of intent names
        """
        return []