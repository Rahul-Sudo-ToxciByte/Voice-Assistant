#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Plugin Manager for Jarvis Assistant

This module handles the loading, management, and execution of plugins for the Jarvis assistant.
Plugins allow for extending the functionality of Jarvis without modifying the core code.
"""

import os
import sys
import json
import logging
import importlib
import importlib.util
import inspect
from typing import Dict, List, Any, Optional, Tuple, Union, Callable, Type
from datetime import datetime
import threading
import traceback


class PluginMetadata:
    """Metadata for a plugin"""
    
    def __init__(self, name: str, version: str, description: str, author: str,
                 requirements: List[str] = None, dependencies: List[str] = None,
                 permissions: List[str] = None, config_schema: Dict[str, Any] = None):
        """Initialize plugin metadata
        
        Args:
            name: Plugin name
            version: Plugin version
            description: Plugin description
            author: Plugin author
            requirements: List of Python package requirements
            dependencies: List of other plugins this plugin depends on
            permissions: List of permissions required by the plugin
            config_schema: JSON schema for plugin configuration
        """
        self.name = name
        self.version = version
        self.description = description
        self.author = author
        self.requirements = requirements or []
        self.dependencies = dependencies or []
        self.permissions = permissions or []
        self.config_schema = config_schema or {}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PluginMetadata':
        """Create plugin metadata from dictionary
        
        Args:
            data: Dictionary containing plugin metadata
            
        Returns:
            PluginMetadata object
        """
        return cls(
            name=data.get("name", "Unknown"),
            version=data.get("version", "0.0.0"),
            description=data.get("description", ""),
            author=data.get("author", "Unknown"),
            requirements=data.get("requirements", []),
            dependencies=data.get("dependencies", []),
            permissions=data.get("permissions", []),
            config_schema=data.get("config_schema", {})
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert plugin metadata to dictionary
        
        Returns:
            Dictionary representation of plugin metadata
        """
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "requirements": self.requirements,
            "dependencies": self.dependencies,
            "permissions": self.permissions,
            "config_schema": self.config_schema
        }


class Plugin:
    """Base class for Jarvis plugins"""
    
    def __init__(self, manager: 'PluginManager', metadata: PluginMetadata, config: Dict[str, Any]):
        """Initialize plugin
        
        Args:
            manager: Plugin manager instance
            metadata: Plugin metadata
            config: Plugin configuration
        """
        self.manager = manager
        self.metadata = metadata
        self.config = config
        self.logger = logging.getLogger(f"jarvis.plugins.{metadata.name}")
        self.enabled = True
        self.initialized = False
        self.error = None
    
    def initialize(self) -> bool:
        """Initialize the plugin
        
        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            self._initialize()
            self.initialized = True
            return True
        except Exception as e:
            self.error = str(e)
            self.logger.error(f"Error initializing plugin: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def _initialize(self):
        """Plugin-specific initialization
        
        This method should be overridden by plugin implementations.
        """
        pass
    
    def shutdown(self):
        """Shutdown the plugin
        
        This method should be overridden by plugin implementations.
        """
        pass
    
    def get_commands(self) -> Dict[str, Dict[str, Any]]:
        """Get commands provided by the plugin
        
        Returns:
            Dictionary of command names to command metadata
        """
        return {}
    
    def execute_command(self, command: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a command
        
        Args:
            command: Command name
            args: Command arguments
            
        Returns:
            Command result
        """
        raise NotImplementedError(f"Command '{command}' not implemented")
    
    def get_intents(self) -> Dict[str, List[str]]:
        """Get intents provided by the plugin
        
        Returns:
            Dictionary of intent names to example phrases
        """
        return {}
    
    def handle_intent(self, intent: str, entities: Dict[str, Any], text: str) -> Dict[str, Any]:
        """Handle an intent
        
        Args:
            intent: Intent name
            entities: Extracted entities
            text: Original text
            
        Returns:
            Intent handling result
        """
        raise NotImplementedError(f"Intent '{intent}' not implemented")
    
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
        raise NotImplementedError(f"Hook '{hook}' not implemented")


class PluginManager:
    """Plugin Manager for Jarvis Assistant"""
    
    def __init__(self, config: Dict[str, Any], jarvis=None):
        """Initialize the plugin manager
        
        Args:
            config: Configuration dictionary for plugin settings
            jarvis: Jarvis assistant instance
        """
        self.logger = logging.getLogger("jarvis.plugins")
        self.config = config
        self.jarvis = jarvis
        
        # Set up plugin configuration
        self.enabled = config.get("enable_plugins", True)
        self.auto_load = config.get("auto_load_plugins", True)
        self.safe_mode = config.get("plugin_safe_mode", True)
        self.plugin_dirs = config.get("plugin_directories", ["plugins"])
        
        # Ensure plugin directories exist
        for plugin_dir in self.plugin_dirs:
            os.makedirs(plugin_dir, exist_ok=True)
        
        # Initialize plugin dictionaries
        self.plugins: Dict[str, Plugin] = {}
        self.plugin_modules: Dict[str, Any] = {}
        self.plugin_classes: Dict[str, Type[Plugin]] = {}
        self.plugin_metadata: Dict[str, PluginMetadata] = {}
        
        # Initialize command, intent, and hook registries
        self.commands: Dict[str, Tuple[str, Dict[str, Any]]] = {}
        self.intents: Dict[str, Tuple[str, List[str]]] = {}
        self.hooks: Dict[str, Dict[str, List[str]]] = {}
        
        # Initialize lock for thread safety
        self.lock = threading.RLock()
        
        self.logger.info(f"Plugin manager initialized (enabled: {self.enabled})")
    
    def discover_plugins(self) -> Dict[str, PluginMetadata]:
        """Discover available plugins
        
        Returns:
            Dictionary of plugin names to metadata
        """
        if not self.enabled:
            return {}
        
        discovered_plugins = {}
        
        for plugin_dir in self.plugin_dirs:
            if not os.path.isdir(plugin_dir):
                continue
            
            # Look for plugin directories (containing plugin.json)
            for item in os.listdir(plugin_dir):
                item_path = os.path.join(plugin_dir, item)
                
                if not os.path.isdir(item_path):
                    continue
                
                # Check for plugin.json
                metadata_file = os.path.join(item_path, "plugin.json")
                if not os.path.isfile(metadata_file):
                    continue
                
                try:
                    # Load metadata
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata_dict = json.load(f)
                    
                    # Create metadata object
                    metadata = PluginMetadata.from_dict(metadata_dict)
                    
                    # Add to discovered plugins
                    discovered_plugins[metadata.name] = metadata
                    
                    self.logger.debug(f"Discovered plugin: {metadata.name} v{metadata.version}")
                
                except Exception as e:
                    self.logger.error(f"Error loading plugin metadata from {metadata_file}: {e}")
        
        return discovered_plugins
    
    def load_plugin(self, plugin_name: str) -> bool:
        """Load a plugin
        
        Args:
            plugin_name: Name of the plugin to load
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        with self.lock:
            # Check if plugin is already loaded
            if plugin_name in self.plugins:
                self.logger.warning(f"Plugin '{plugin_name}' is already loaded")
                return True
            
            # Find plugin directory
            plugin_path = None
            metadata_file = None
            
            for plugin_dir in self.plugin_dirs:
                candidate_path = os.path.join(plugin_dir, plugin_name)
                candidate_metadata = os.path.join(candidate_path, "plugin.json")
                
                if os.path.isdir(candidate_path) and os.path.isfile(candidate_metadata):
                    plugin_path = candidate_path
                    metadata_file = candidate_metadata
                    break
            
            if not plugin_path or not metadata_file:
                self.logger.error(f"Plugin '{plugin_name}' not found")
                return False
            
            try:
                # Load metadata
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata_dict = json.load(f)
                
                metadata = PluginMetadata.from_dict(metadata_dict)
                
                # Check dependencies
                for dependency in metadata.dependencies:
                    if dependency not in self.plugins:
                        self.logger.error(f"Plugin '{plugin_name}' depends on '{dependency}' which is not loaded")
                        return False
                
                # Load plugin module
                module_path = os.path.join(plugin_path, "__init__.py")
                if not os.path.isfile(module_path):
                    self.logger.error(f"Plugin '{plugin_name}' is missing __init__.py")
                    return False
                
                # Import module
                spec = importlib.util.spec_from_file_location(f"jarvis_plugin_{plugin_name}", module_path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
                
                # Find plugin class
                plugin_class = None
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and issubclass(obj, Plugin) and obj != Plugin):
                        plugin_class = obj
                        break
                
                if not plugin_class:
                    self.logger.error(f"Plugin '{plugin_name}' does not contain a Plugin subclass")
                    return False
                
                # Get plugin configuration
                plugin_config = self.config.get("plugin_configs", {}).get(plugin_name, {})
                
                # Create plugin instance
                plugin = plugin_class(self, metadata, plugin_config)
                
                # Initialize plugin
                if not plugin.initialize():
                    self.logger.error(f"Failed to initialize plugin '{plugin_name}'")
                    return False
                
                # Register plugin
                self.plugins[plugin_name] = plugin
                self.plugin_modules[plugin_name] = module
                self.plugin_classes[plugin_name] = plugin_class
                self.plugin_metadata[plugin_name] = metadata
                
                # Register commands, intents, and hooks
                self._register_plugin_commands(plugin_name)
                self._register_plugin_intents(plugin_name)
                self._register_plugin_hooks(plugin_name)
                
                self.logger.info(f"Loaded plugin: {plugin_name} v{metadata.version}")
                
                return True
            
            except Exception as e:
                self.logger.error(f"Error loading plugin '{plugin_name}': {e}")
                self.logger.error(traceback.format_exc())
                return False
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a plugin
        
        Args:
            plugin_name: Name of the plugin to unload
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        with self.lock:
            # Check if plugin is loaded
            if plugin_name not in self.plugins:
                self.logger.warning(f"Plugin '{plugin_name}' is not loaded")
                return False
            
            # Check if other plugins depend on this one
            for name, metadata in self.plugin_metadata.items():
                if name != plugin_name and plugin_name in metadata.dependencies:
                    self.logger.error(f"Cannot unload plugin '{plugin_name}' because '{name}' depends on it")
                    return False
            
            try:
                # Get plugin
                plugin = self.plugins[plugin_name]
                
                # Shutdown plugin
                plugin.shutdown()
                
                # Unregister commands, intents, and hooks
                self._unregister_plugin_commands(plugin_name)
                self._unregister_plugin_intents(plugin_name)
                self._unregister_plugin_hooks(plugin_name)
                
                # Remove plugin
                del self.plugins[plugin_name]
                del self.plugin_modules[plugin_name]
                del self.plugin_classes[plugin_name]
                del self.plugin_metadata[plugin_name]
                
                # Remove from sys.modules
                module_name = f"jarvis_plugin_{plugin_name}"
                if module_name in sys.modules:
                    del sys.modules[module_name]
                
                self.logger.info(f"Unloaded plugin: {plugin_name}")
                
                return True
            
            except Exception as e:
                self.logger.error(f"Error unloading plugin '{plugin_name}': {e}")
                self.logger.error(traceback.format_exc())
                return False
    
    def reload_plugin(self, plugin_name: str) -> bool:
        """Reload a plugin
        
        Args:
            plugin_name: Name of the plugin to reload
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        # Unload plugin
        if not self.unload_plugin(plugin_name):
            return False
        
        # Load plugin
        return self.load_plugin(plugin_name)
    
    def load_all_plugins(self) -> Dict[str, bool]:
        """Load all available plugins
        
        Returns:
            Dictionary of plugin names to load status
        """
        if not self.enabled:
            return {}
        
        # Discover plugins
        discovered_plugins = self.discover_plugins()
        
        # Load plugins
        results = {}
        for plugin_name in discovered_plugins.keys():
            results[plugin_name] = self.load_plugin(plugin_name)
        
        return results
    
    def unload_all_plugins(self) -> Dict[str, bool]:
        """Unload all loaded plugins
        
        Returns:
            Dictionary of plugin names to unload status
        """
        if not self.enabled:
            return {}
        
        # Unload plugins in reverse dependency order
        results = {}
        plugin_names = list(self.plugins.keys())
        
        # Keep trying to unload plugins until no more can be unloaded
        while plugin_names:
            progress = False
            
            for plugin_name in plugin_names.copy():
                # Check if other plugins depend on this one
                has_dependents = False
                for name, metadata in self.plugin_metadata.items():
                    if name != plugin_name and plugin_name in metadata.dependencies and name in plugin_names:
                        has_dependents = True
                        break
                
                if not has_dependents:
                    # Unload plugin
                    results[plugin_name] = self.unload_plugin(plugin_name)
                    plugin_names.remove(plugin_name)
                    progress = True
            
            if not progress:
                # Circular dependency or other issue
                for plugin_name in plugin_names:
                    results[plugin_name] = False
                break
        
        return results
    
    def _register_plugin_commands(self, plugin_name: str):
        """Register commands provided by a plugin
        
        Args:
            plugin_name: Name of the plugin
        """
        plugin = self.plugins[plugin_name]
        
        # Get commands
        commands = plugin.get_commands()
        
        # Register commands
        for command_name, command_meta in commands.items():
            # Check if command already exists
            if command_name in self.commands:
                self.logger.warning(f"Command '{command_name}' from plugin '{plugin_name}' conflicts with existing command")
                continue
            
            # Register command
            self.commands[command_name] = (plugin_name, command_meta)
            self.logger.debug(f"Registered command '{command_name}' from plugin '{plugin_name}'")
    
    def _unregister_plugin_commands(self, plugin_name: str):
        """Unregister commands provided by a plugin
        
        Args:
            plugin_name: Name of the plugin
        """
        # Find commands from this plugin
        commands_to_remove = []
        for command_name, (provider, _) in self.commands.items():
            if provider == plugin_name:
                commands_to_remove.append(command_name)
        
        # Remove commands
        for command_name in commands_to_remove:
            del self.commands[command_name]
            self.logger.debug(f"Unregistered command '{command_name}' from plugin '{plugin_name}'")
    
    def _register_plugin_intents(self, plugin_name: str):
        """Register intents provided by a plugin
        
        Args:
            plugin_name: Name of the plugin
        """
        plugin = self.plugins[plugin_name]
        
        # Get intents
        intents = plugin.get_intents()
        
        # Register intents
        for intent_name, examples in intents.items():
            # Check if intent already exists
            if intent_name in self.intents:
                self.logger.warning(f"Intent '{intent_name}' from plugin '{plugin_name}' conflicts with existing intent")
                continue
            
            # Register intent
            self.intents[intent_name] = (plugin_name, examples)
            self.logger.debug(f"Registered intent '{intent_name}' from plugin '{plugin_name}'")
    
    def _unregister_plugin_intents(self, plugin_name: str):
        """Unregister intents provided by a plugin
        
        Args:
            plugin_name: Name of the plugin
        """
        # Find intents from this plugin
        intents_to_remove = []
        for intent_name, (provider, _) in self.intents.items():
            if provider == plugin_name:
                intents_to_remove.append(intent_name)
        
        # Remove intents
        for intent_name in intents_to_remove:
            del self.intents[intent_name]
            self.logger.debug(f"Unregistered intent '{intent_name}' from plugin '{plugin_name}'")
    
    def _register_plugin_hooks(self, plugin_name: str):
        """Register hooks provided by a plugin
        
        Args:
            plugin_name: Name of the plugin
        """
        plugin = self.plugins[plugin_name]
        
        # Get hooks
        hooks = plugin.get_hooks()
        
        # Register hooks
        for hook_name, event_types in hooks.items():
            # Initialize hook if it doesn't exist
            if hook_name not in self.hooks:
                self.hooks[hook_name] = {}
            
            # Register hook for each event type
            for event_type in event_types:
                if event_type not in self.hooks[hook_name]:
                    self.hooks[hook_name][event_type] = []
                
                self.hooks[hook_name][event_type].append(plugin_name)
                self.logger.debug(f"Registered hook '{hook_name}' for event '{event_type}' from plugin '{plugin_name}'")
    
    def _unregister_plugin_hooks(self, plugin_name: str):
        """Unregister hooks provided by a plugin
        
        Args:
            plugin_name: Name of the plugin
        """
        # Find hooks from this plugin
        for hook_name, event_types in self.hooks.copy().items():
            for event_type, providers in event_types.copy().items():
                if plugin_name in providers:
                    providers.remove(plugin_name)
                    self.logger.debug(f"Unregistered hook '{hook_name}' for event '{event_type}' from plugin '{plugin_name}'")
                
                # Remove event type if no providers
                if not providers:
                    del self.hooks[hook_name][event_type]
            
            # Remove hook if no event types
            if not self.hooks[hook_name]:
                del self.hooks[hook_name]
    
    def execute_command(self, command: str, args: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute a command
        
        Args:
            command: Command name
            args: Command arguments
            
        Returns:
            Command result
        """
        if not self.enabled:
            return {"success": False, "error": "Plugin system is disabled"}
        
        args = args or {}
        
        # Check if command exists
        if command not in self.commands:
            return {"success": False, "error": f"Command '{command}' not found"}
        
        # Get plugin and command metadata
        plugin_name, command_meta = self.commands[command]
        
        try:
            # Get plugin
            plugin = self.plugins[plugin_name]
            
            # Execute command
            result = plugin.execute_command(command, args)
            
            # Ensure result is a dictionary
            if not isinstance(result, dict):
                result = {"result": result}
            
            # Add success flag if not present
            if "success" not in result:
                result["success"] = True
            
            return result
        
        except Exception as e:
            self.logger.error(f"Error executing command '{command}' from plugin '{plugin_name}': {e}")
            self.logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}
    
    def handle_intent(self, intent: str, entities: Dict[str, Any], text: str) -> Dict[str, Any]:
        """Handle an intent
        
        Args:
            intent: Intent name
            entities: Extracted entities
            text: Original text
            
        Returns:
            Intent handling result
        """
        if not self.enabled:
            return {"success": False, "error": "Plugin system is disabled"}
        
        # Check if intent exists
        if intent not in self.intents:
            return {"success": False, "error": f"Intent '{intent}' not found"}
        
        # Get plugin
        plugin_name, _ = self.intents[intent]
        
        try:
            # Get plugin
            plugin = self.plugins[plugin_name]
            
            # Handle intent
            result = plugin.handle_intent(intent, entities, text)
            
            # Ensure result is a dictionary
            if not isinstance(result, dict):
                result = {"result": result}
            
            # Add success flag if not present
            if "success" not in result:
                result["success"] = True
            
            return result
        
        except Exception as e:
            self.logger.error(f"Error handling intent '{intent}' from plugin '{plugin_name}': {e}")
            self.logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}
    
    def trigger_hook(self, hook: str, event_type: str, data: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Trigger a hook
        
        Args:
            hook: Hook name
            event_type: Event type
            data: Event data
            
        Returns:
            List of hook handling results
        """
        if not self.enabled:
            return []
        
        data = data or {}
        results = []
        
        # Check if hook exists
        if hook not in self.hooks or event_type not in self.hooks[hook]:
            return results
        
        # Get plugins for this hook and event type
        plugin_names = self.hooks[hook][event_type]
        
        for plugin_name in plugin_names:
            try:
                # Get plugin
                plugin = self.plugins[plugin_name]
                
                # Handle hook
                result = plugin.handle_hook(hook, event_type, data)
                
                # Ensure result is a dictionary
                if not isinstance(result, dict):
                    result = {"result": result}
                
                # Add plugin name and success flag
                result["plugin"] = plugin_name
                if "success" not in result:
                    result["success"] = True
                
                results.append(result)
            
            except Exception as e:
                self.logger.error(f"Error triggering hook '{hook}' for event '{event_type}' from plugin '{plugin_name}': {e}")
                self.logger.error(traceback.format_exc())
                results.append({"plugin": plugin_name, "success": False, "error": str(e)})
        
        return results
    
    def get_plugin_info(self, plugin_name: str = None) -> Dict[str, Any]:
        """Get information about plugins
        
        Args:
            plugin_name: Name of the plugin to get information about, or None for all plugins
            
        Returns:
            Dictionary of plugin information
        """
        if not self.enabled:
            return {}
        
        if plugin_name:
            # Get information about a specific plugin
            if plugin_name not in self.plugins:
                return {}
            
            plugin = self.plugins[plugin_name]
            metadata = self.plugin_metadata[plugin_name]
            
            return {
                "name": plugin_name,
                "version": metadata.version,
                "description": metadata.description,
                "author": metadata.author,
                "requirements": metadata.requirements,
                "dependencies": metadata.dependencies,
                "permissions": metadata.permissions,
                "enabled": plugin.enabled,
                "initialized": plugin.initialized,
                "error": plugin.error,
                "commands": plugin.get_commands(),
                "intents": plugin.get_intents(),
                "hooks": plugin.get_hooks()
            }
        else:
            # Get information about all plugins
            info = {}
            
            for name, plugin in self.plugins.items():
                metadata = self.plugin_metadata[name]
                
                info[name] = {
                    "version": metadata.version,
                    "description": metadata.description,
                    "author": metadata.author,
                    "enabled": plugin.enabled,
                    "initialized": plugin.initialized,
                    "error": plugin.error
                }
            
            return info
    
    def get_available_commands(self) -> Dict[str, Dict[str, Any]]:
        """Get available commands
        
        Returns:
            Dictionary of command names to command metadata
        """
        if not self.enabled:
            return {}
        
        commands = {}
        
        for command_name, (plugin_name, command_meta) in self.commands.items():
            # Add plugin name to metadata
            meta = command_meta.copy()
            meta["plugin"] = plugin_name
            
            commands[command_name] = meta
        
        return commands
    
    def get_available_intents(self) -> Dict[str, Dict[str, Any]]:
        """Get available intents
        
        Returns:
            Dictionary of intent names to intent metadata
        """
        if not self.enabled:
            return {}
        
        intents = {}
        
        for intent_name, (plugin_name, examples) in self.intents.items():
            intents[intent_name] = {
                "plugin": plugin_name,
                "examples": examples
            }
        
        return intents
    
    def create_plugin_template(self, plugin_name: str, author: str, description: str) -> bool:
        """Create a plugin template
        
        Args:
            plugin_name: Plugin name
            author: Plugin author
            description: Plugin description
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        # Validate plugin name
        if not plugin_name or not plugin_name.isalnum():
            self.logger.error(f"Invalid plugin name: {plugin_name}")
            return False
        
        # Create plugin directory
        plugin_dir = os.path.join(self.plugin_dirs[0], plugin_name)
        
        if os.path.exists(plugin_dir):
            self.logger.error(f"Plugin directory already exists: {plugin_dir}")
            return False
        
        try:
            # Create plugin directory
            os.makedirs(plugin_dir)
            
            # Create plugin.json
            metadata = {
                "name": plugin_name,
                "version": "0.1.0",
                "description": description,
                "author": author,
                "requirements": [],
                "dependencies": [],
                "permissions": [],
                "config_schema": {}
            }
            
            with open(os.path.join(plugin_dir, "plugin.json"), 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            # Create __init__.py
            with open(os.path.join(plugin_dir, "__init__.py"), 'w', encoding='utf-8') as f:
                f.write(f"""\
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
{plugin_name} Plugin for Jarvis Assistant

{description}
"""

from jarvis.modules.plugins.plugin_manager import Plugin
from typing import Dict, List, Any, Optional


class {plugin_name.capitalize()}Plugin(Plugin):
    """Plugin implementation for {plugin_name}"""
    
    def _initialize(self):
        """Initialize the plugin"""
        self.logger.info("Initializing {plugin_name} plugin")
        
        # TODO: Add initialization code here
    
    def shutdown(self):
        """Shutdown the plugin"""
        self.logger.info("Shutting down {plugin_name} plugin")
        
        # TODO: Add cleanup code here
    
    def get_commands(self) -> Dict[str, Dict[str, Any]]:
        """Get commands provided by the plugin
        
        Returns:
            Dictionary of command names to command metadata
        """
        return {{
            # TODO: Add commands here
            # "command_name": {{
            #     "description": "Command description",
            #     "usage": "command_name [args]",
            #     "examples": ["command_name arg1 arg2"],
            #     "args": {{
            #         "arg1": {{
            #             "description": "Argument description",
            #             "required": True,
            #             "type": "string"
            #         }}
            #     }}
            # }}
        }}
    
    def execute_command(self, command: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a command
        
        Args:
            command: Command name
            args: Command arguments
            
        Returns:
            Command result
        """
        # TODO: Implement command execution
        raise NotImplementedError(f"Command '{{command}}' not implemented")
    
    def get_intents(self) -> Dict[str, List[str]]:
        """Get intents provided by the plugin
        
        Returns:
            Dictionary of intent names to example phrases
        """
        return {{
            # TODO: Add intents here
            # "intent_name": [
            #     "Example phrase 1",
            #     "Example phrase 2"
            # ]
        }}
    
    def handle_intent(self, intent: str, entities: Dict[str, Any], text: str) -> Dict[str, Any]:
        """Handle an intent
        
        Args:
            intent: Intent name
            entities: Extracted entities
            text: Original text
            
        Returns:
            Intent handling result
        """
        # TODO: Implement intent handling
        raise NotImplementedError(f"Intent '{{intent}}' not implemented")
    
    def get_hooks(self) -> Dict[str, List[str]]:
        """Get hooks provided by the plugin
        
        Returns:
            Dictionary of hook names to event types
        """
        return {{
            # TODO: Add hooks here
            # "hook_name": [
            #     "event_type_1",
            #     "event_type_2"
            # ]
        }}
    
    def handle_hook(self, hook: str, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a hook
        
        Args:
            hook: Hook name
            event_type: Event type
            data: Event data
            
        Returns:
            Hook handling result
        """
        # TODO: Implement hook handling
        raise NotImplementedError(f"Hook '{{hook}}' for event '{{event_type}}' not implemented")
""")
            
            # Create README.md
            with open(os.path.join(plugin_dir, "README.md"), 'w', encoding='utf-8') as f:
                f.write(f"""\
# {plugin_name} Plugin for Jarvis Assistant

{description}

## Installation

1. Copy this directory to the `plugins` directory of your Jarvis installation.
2. Restart Jarvis or load the plugin using the `load_plugin` command.

## Usage

<!-- TODO: Add usage instructions here -->

## Commands

<!-- TODO: Add command documentation here -->

## Intents

<!-- TODO: Add intent documentation here -->

## Hooks

<!-- TODO: Add hook documentation here -->

## Configuration

<!-- TODO: Add configuration documentation here -->

## License

<!-- TODO: Add license information here -->
""")
            
            self.logger.info(f"Created plugin template: {plugin_name}")
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error creating plugin template: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def start(self):
        """Start the plugin manager"""
        if not self.enabled:
            return
        
        # Auto-load plugins
        if self.auto_load:
            self.load_all_plugins()
    
    def shutdown(self):
        """Shutdown the plugin manager"""
        if not self.enabled:
            return
        
        # Unload all plugins
        self.unload_all_plugins()
        
        self.logger.info("Plugin manager shut down")