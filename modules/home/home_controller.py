#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Home Controller for Jarvis Assistant

This module handles the smart home control capabilities of the Jarvis assistant,
including integration with home automation platforms and direct device control.
"""

import os
import json
import logging
import threading
import time
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime

# Import for MQTT
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False

# Import for Home Assistant API
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class HomeController:
    """Smart home controller for Jarvis Assistant"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the home controller
        
        Args:
            config: Configuration dictionary for home controller settings
        """
        self.logger = logging.getLogger("jarvis.home")
        self.config = config
        
        # Set up home controller configuration
        self.enabled = config.get("enable_home_control", False)
        self.platform = config.get("platform", "mqtt").lower()  # mqtt, home_assistant, or custom
        
        # Device state tracking
        self.devices = {}
        self.rooms = {}
        self.device_callbacks = {}
        
        # Initialize platform connection
        self.client = None
        self.connected = False
        
        if self.enabled:
            self._initialize_platform()
            self._load_devices()
        
        self.logger.info(f"Home controller initialized (enabled: {self.enabled}, platform: {self.platform})")
    
    def _initialize_platform(self):
        """Initialize the home automation platform connection"""
        if self.platform == "mqtt":
            self._initialize_mqtt()
        elif self.platform == "home_assistant":
            self._initialize_home_assistant()
        elif self.platform == "custom":
            self._initialize_custom()
        else:
            self.logger.error(f"Unsupported home automation platform: {self.platform}")
            self.enabled = False
    
    def _initialize_mqtt(self):
        """Initialize MQTT connection"""
        if not MQTT_AVAILABLE:
            self.logger.error("MQTT client not available. MQTT integration will be disabled.")
            self.enabled = False
            return
        
        try:
            # Get MQTT configuration
            mqtt_config = self.config.get("mqtt", {})
            broker = mqtt_config.get("broker", "localhost")
            port = mqtt_config.get("port", 1883)
            username = mqtt_config.get("username")
            password = mqtt_config.get("password")
            client_id = mqtt_config.get("client_id", f"jarvis_home_controller_{int(time.time())}")
            
            # Initialize MQTT client
            self.client = mqtt.Client(client_id=client_id)
            
            # Set up callbacks
            self.client.on_connect = self._on_mqtt_connect
            self.client.on_message = self._on_mqtt_message
            self.client.on_disconnect = self._on_mqtt_disconnect
            
            # Set username and password if provided
            if username and password:
                self.client.username_pw_set(username, password)
            
            # Connect to broker
            self.client.connect_async(broker, port, 60)
            
            # Start the loop in a separate thread
            self.client.loop_start()
            
            self.logger.info(f"MQTT client initialized, connecting to {broker}:{port}")
        
        except Exception as e:
            self.logger.error(f"Error initializing MQTT client: {e}")
            self.enabled = False
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback for when the MQTT client connects"""
        if rc == 0:
            self.logger.info("Connected to MQTT broker")
            self.connected = True
            
            # Subscribe to device state topics
            for device_id, device in self.devices.items():
                if "state_topic" in device:
                    self.client.subscribe(device["state_topic"])
                    self.logger.debug(f"Subscribed to {device['state_topic']} for {device_id}")
        else:
            self.logger.error(f"Failed to connect to MQTT broker, return code: {rc}")
            self.connected = False
    
    def _on_mqtt_message(self, client, userdata, msg):
        """Callback for when a message is received from the MQTT broker"""
        try:
            topic = msg.topic
            payload = msg.payload.decode("utf-8")
            
            self.logger.debug(f"MQTT message received: {topic} = {payload}")
            
            # Find device with matching state topic
            for device_id, device in self.devices.items():
                if "state_topic" in device and device["state_topic"] == topic:
                    # Update device state
                    try:
                        # Try to parse JSON payload
                        state = json.loads(payload)
                    except json.JSONDecodeError:
                        # Use raw payload as state
                        state = payload
                    
                    self._update_device_state(device_id, state)
                    break
        
        except Exception as e:
            self.logger.error(f"Error processing MQTT message: {e}")
    
    def _on_mqtt_disconnect(self, client, userdata, rc):
        """Callback for when the MQTT client disconnects"""
        self.logger.warning(f"Disconnected from MQTT broker with code: {rc}")
        self.connected = False
    
    def _initialize_home_assistant(self):
        """Initialize Home Assistant API connection"""
        if not REQUESTS_AVAILABLE:
            self.logger.error("Requests library not available. Home Assistant integration will be disabled.")
            self.enabled = False
            return
        
        try:
            # Get Home Assistant configuration
            ha_config = self.config.get("home_assistant", {})
            self.ha_url = ha_config.get("url", "http://localhost:8123")
            self.ha_token = ha_config.get("token")
            
            if not self.ha_token:
                self.logger.error("Home Assistant token not provided")
                self.enabled = False
                return
            
            # Set up API headers
            self.ha_headers = {
                "Authorization": f"Bearer {self.ha_token}",
                "Content-Type": "application/json"
            }
            
            # Test connection
            response = requests.get(f"{self.ha_url}/api/", headers=self.ha_headers)
            if response.status_code == 200:
                self.connected = True
                self.logger.info("Connected to Home Assistant API")
            else:
                self.logger.error(f"Failed to connect to Home Assistant API: {response.status_code}")
                self.enabled = False
        
        except Exception as e:
            self.logger.error(f"Error initializing Home Assistant connection: {e}")
            self.enabled = False
    
    def _initialize_custom(self):
        """Initialize custom home automation platform"""
        self.logger.info("Using custom home automation platform")
        self.connected = True
        
        # Custom platform initialization would go here
        # This is a placeholder for custom implementations
    
    def _load_devices(self):
        """Load devices from configuration"""
        # Load devices from config
        devices_config = self.config.get("devices", {})
        for device_id, device_config in devices_config.items():
            self.devices[device_id] = device_config
            
            # Add device to room mapping
            if "room" in device_config:
                room = device_config["room"]
                if room not in self.rooms:
                    self.rooms[room] = []
                self.rooms[room].append(device_id)
        
        # Load devices from file if available
        devices_file = os.path.join("data", "home", "devices.json")
        if os.path.exists(devices_file):
            try:
                with open(devices_file, 'r', encoding='utf-8') as f:
                    file_devices = json.load(f)
                
                # Merge with existing devices
                for device_id, device_config in file_devices.items():
                    if device_id not in self.devices:
                        self.devices[device_id] = device_config
                        
                        # Add device to room mapping
                        if "room" in device_config:
                            room = device_config["room"]
                            if room not in self.rooms:
                                self.rooms[room] = []
                            self.rooms[room].append(device_id)
            
            except Exception as e:
                self.logger.error(f"Error loading devices from file: {e}")
        
        self.logger.info(f"Loaded {len(self.devices)} devices in {len(self.rooms)} rooms")
    
    def _save_devices(self):
        """Save devices to file"""
        devices_dir = os.path.join("data", "home")
        os.makedirs(devices_dir, exist_ok=True)
        
        devices_file = os.path.join(devices_dir, "devices.json")
        try:
            with open(devices_file, 'w', encoding='utf-8') as f:
                json.dump(self.devices, f, indent=2, ensure_ascii=False)
            self.logger.debug(f"Saved {len(self.devices)} devices to file")
        except Exception as e:
            self.logger.error(f"Error saving devices to file: {e}")
    
    def _update_device_state(self, device_id: str, state: Any):
        """Update device state and trigger callbacks
        
        Args:
            device_id: Device ID
            state: New device state
        """
        if device_id not in self.devices:
            self.logger.warning(f"Received state update for unknown device: {device_id}")
            return
        
        # Update device state
        old_state = self.devices[device_id].get("state")
        self.devices[device_id]["state"] = state
        self.devices[device_id]["last_updated"] = datetime.now().isoformat()
        
        # Trigger callbacks
        if device_id in self.device_callbacks:
            for callback in self.device_callbacks[device_id]:
                try:
                    callback(device_id, state, old_state)
                except Exception as e:
                    self.logger.error(f"Error in device callback: {e}")
    
    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get device information
        
        Args:
            device_id: Device ID
            
        Returns:
            Device information dictionary, or None if not found
        """
        return self.devices.get(device_id)
    
    def get_devices(self, room: Optional[str] = None, device_type: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """Get devices, optionally filtered by room or type
        
        Args:
            room: Optional room to filter by
            device_type: Optional device type to filter by
            
        Returns:
            Dictionary of devices
        """
        if room is None and device_type is None:
            return self.devices
        
        filtered_devices = {}
        
        for device_id, device in self.devices.items():
            # Filter by room if specified
            if room is not None and device.get("room") != room:
                continue
            
            # Filter by type if specified
            if device_type is not None and device.get("type") != device_type:
                continue
            
            filtered_devices[device_id] = device
        
        return filtered_devices
    
    def get_rooms(self) -> List[str]:
        """Get list of rooms
        
        Returns:
            List of room names
        """
        return list(self.rooms.keys())
    
    def get_device_types(self) -> List[str]:
        """Get list of device types
        
        Returns:
            List of device types
        """
        types = set()
        for device in self.devices.values():
            if "type" in device:
                types.add(device["type"])
        return list(types)
    
    def control_device(self, device_id: str, command: str, value: Optional[Any] = None) -> bool:
        """Control a device
        
        Args:
            device_id: Device ID
            command: Command to send (e.g., "turn_on", "set_temperature")
            value: Optional value for the command
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.connected:
            self.logger.error("Home controller not enabled or not connected")
            return False
        
        if device_id not in self.devices:
            self.logger.error(f"Unknown device: {device_id}")
            return False
        
        device = self.devices[device_id]
        
        # Handle platform-specific control
        if self.platform == "mqtt":
            return self._control_device_mqtt(device_id, device, command, value)
        elif self.platform == "home_assistant":
            return self._control_device_home_assistant(device_id, device, command, value)
        elif self.platform == "custom":
            return self._control_device_custom(device_id, device, command, value)
        else:
            self.logger.error(f"Unsupported platform: {self.platform}")
            return False
    
    def _control_device_mqtt(self, device_id: str, device: Dict[str, Any], command: str, value: Optional[Any] = None) -> bool:
        """Control device via MQTT
        
        Args:
            device_id: Device ID
            device: Device configuration
            command: Command to send
            value: Optional value for the command
            
        Returns:
            True if successful, False otherwise
        """
        if not MQTT_AVAILABLE or self.client is None:
            return False
        
        try:
            # Get command topic
            if "command_topic" not in device:
                self.logger.error(f"Device {device_id} does not have a command topic")
                return False
            
            command_topic = device["command_topic"]
            
            # Prepare payload
            if "command_template" in device:
                # Use command template if available
                template = device["command_template"]
                payload = template.format(command=command, value=value)
            elif value is not None:
                # Use JSON payload with command and value
                payload = json.dumps({"command": command, "value": value})
            else:
                # Use command as payload
                payload = command
            
            # Send command
            self.client.publish(command_topic, payload)
            self.logger.info(f"Sent command to {device_id}: {command} {value if value is not None else ''}")
            
            # Update local state if immediate feedback is not available
            if "state_topic" not in device:
                self._update_device_state(device_id, {"command": command, "value": value})
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error controlling device via MQTT: {e}")
            return False
    
    def _control_device_home_assistant(self, device_id: str, device: Dict[str, Any], command: str, value: Optional[Any] = None) -> bool:
        """Control device via Home Assistant API
        
        Args:
            device_id: Device ID
            device: Device configuration
            command: Command to send
            value: Optional value for the command
            
        Returns:
            True if successful, False otherwise
        """
        if not REQUESTS_AVAILABLE:
            return False
        
        try:
            # Get entity ID
            if "entity_id" not in device:
                self.logger.error(f"Device {device_id} does not have an entity ID")
                return False
            
            entity_id = device["entity_id"]
            
            # Map command to Home Assistant service
            service = self._map_command_to_service(device, command)
            if not service:
                self.logger.error(f"Unknown command for device {device_id}: {command}")
                return False
            
            # Prepare service data
            service_data = {"entity_id": entity_id}
            
            # Add value to service data if provided
            if value is not None:
                # Map value to appropriate service data field
                if command == "turn_on" and device.get("type") == "light":
                    if isinstance(value, int):
                        service_data["brightness"] = value
                    elif isinstance(value, str):
                        service_data["color_name"] = value
                elif command == "set_temperature":
                    service_data["temperature"] = value
                elif command == "set_fan_mode":
                    service_data["fan_mode"] = value
                elif command == "set_hvac_mode":
                    service_data["hvac_mode"] = value
                elif command == "set_volume_level":
                    service_data["volume_level"] = value
                elif command == "select_source":
                    service_data["source"] = value
                elif command == "set_value":
                    service_data["value"] = value
                else:
                    # Generic value field
                    service_data["value"] = value
            
            # Send command to Home Assistant API
            domain, service_name = service.split(".", 1)
            url = f"{self.ha_url}/api/services/{domain}/{service_name}"
            
            response = requests.post(url, headers=self.ha_headers, json=service_data)
            
            if response.status_code in (200, 201):
                self.logger.info(f"Sent command to {device_id} via Home Assistant: {service} {service_data}")
                return True
            else:
                self.logger.error(f"Error sending command to Home Assistant: {response.status_code} {response.text}")
                return False
        
        except Exception as e:
            self.logger.error(f"Error controlling device via Home Assistant: {e}")
            return False
    
    def _map_command_to_service(self, device: Dict[str, Any], command: str) -> Optional[str]:
        """Map command to Home Assistant service
        
        Args:
            device: Device configuration
            command: Command to map
            
        Returns:
            Home Assistant service, or None if not found
        """
        # Get device type
        device_type = device.get("type", "switch")
        
        # Command mapping
        command_map = {
            # Generic commands
            "turn_on": f"{device_type}.turn_on",
            "turn_off": f"{device_type}.turn_off",
            "toggle": f"{device_type}.toggle",
            
            # Climate commands
            "set_temperature": "climate.set_temperature",
            "set_hvac_mode": "climate.set_hvac_mode",
            "set_fan_mode": "climate.set_fan_mode",
            
            # Media player commands
            "media_play": "media_player.media_play",
            "media_pause": "media_player.media_pause",
            "media_stop": "media_player.media_stop",
            "media_next_track": "media_player.media_next_track",
            "media_previous_track": "media_player.media_previous_track",
            "volume_up": "media_player.volume_up",
            "volume_down": "media_player.volume_down",
            "volume_mute": "media_player.volume_mute",
            "set_volume_level": "media_player.volume_set",
            "select_source": "media_player.select_source",
            
            # Cover commands
            "open_cover": "cover.open_cover",
            "close_cover": "cover.close_cover",
            "stop_cover": "cover.stop_cover",
            "set_cover_position": "cover.set_cover_position",
            
            # Input select commands
            "select_option": "input_select.select_option",
            
            # Input number commands
            "set_value": "input_number.set_value",
        }
        
        # Custom command mapping from device config
        if "command_map" in device and command in device["command_map"]:
            return device["command_map"][command]
        
        # Use standard mapping
        return command_map.get(command)
    
    def _control_device_custom(self, device_id: str, device: Dict[str, Any], command: str, value: Optional[Any] = None) -> bool:
        """Control device via custom platform
        
        Args:
            device_id: Device ID
            device: Device configuration
            command: Command to send
            value: Optional value for the command
            
        Returns:
            True if successful, False otherwise
        """
        # This is a placeholder for custom implementations
        self.logger.info(f"Custom control for {device_id}: {command} {value if value is not None else ''}")
        
        # Update local state
        self._update_device_state(device_id, {"command": command, "value": value})
        
        return True
    
    def register_device_callback(self, device_id: str, callback: Callable[[str, Any, Any], None]) -> bool:
        """Register a callback for device state changes
        
        Args:
            device_id: Device ID
            callback: Callback function that takes (device_id, new_state, old_state)
            
        Returns:
            True if successful, False otherwise
        """
        if device_id not in self.devices:
            self.logger.error(f"Cannot register callback for unknown device: {device_id}")
            return False
        
        if device_id not in self.device_callbacks:
            self.device_callbacks[device_id] = []
        
        self.device_callbacks[device_id].append(callback)
        return True
    
    def add_device(self, device_id: str, device_config: Dict[str, Any]) -> bool:
        """Add a new device
        
        Args:
            device_id: Device ID
            device_config: Device configuration
            
        Returns:
            True if successful, False otherwise
        """
        if device_id in self.devices:
            self.logger.warning(f"Device {device_id} already exists, updating configuration")
        
        # Add device
        self.devices[device_id] = device_config
        
        # Add to room mapping
        if "room" in device_config:
            room = device_config["room"]
            if room not in self.rooms:
                self.rooms[room] = []
            if device_id not in self.rooms[room]:
                self.rooms[room].append(device_id)
        
        # Subscribe to state topic if using MQTT
        if self.platform == "mqtt" and self.client and self.connected:
            if "state_topic" in device_config:
                self.client.subscribe(device_config["state_topic"])
                self.logger.debug(f"Subscribed to {device_config['state_topic']} for {device_id}")
        
        # Save devices
        self._save_devices()
        
        self.logger.info(f"Added device: {device_id}")
        return True
    
    def remove_device(self, device_id: str) -> bool:
        """Remove a device
        
        Args:
            device_id: Device ID
            
        Returns:
            True if successful, False otherwise
        """
        if device_id not in self.devices:
            self.logger.warning(f"Cannot remove unknown device: {device_id}")
            return False
        
        # Get device config
        device = self.devices[device_id]
        
        # Unsubscribe from state topic if using MQTT
        if self.platform == "mqtt" and self.client and self.connected:
            if "state_topic" in device:
                self.client.unsubscribe(device["state_topic"])
        
        # Remove from room mapping
        if "room" in device:
            room = device["room"]
            if room in self.rooms and device_id in self.rooms[room]:
                self.rooms[room].remove(device_id)
                if not self.rooms[room]:
                    del self.rooms[room]
        
        # Remove callbacks
        if device_id in self.device_callbacks:
            del self.device_callbacks[device_id]
        
        # Remove device
        del self.devices[device_id]
        
        # Save devices
        self._save_devices()
        
        self.logger.info(f"Removed device: {device_id}")
        return True
    
    def execute_scene(self, scene_id: str) -> bool:
        """Execute a scene (predefined set of device states)
        
        Args:
            scene_id: Scene ID
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.connected:
            self.logger.error("Home controller not enabled or not connected")
            return False
        
        # Check if scene exists in config
        scenes = self.config.get("scenes", {})
        if scene_id not in scenes:
            self.logger.error(f"Unknown scene: {scene_id}")
            return False
        
        scene = scenes[scene_id]
        
        # Execute scene actions
        success = True
        for action in scene.get("actions", []):
            if "device_id" in action and "command" in action:
                device_id = action["device_id"]
                command = action["command"]
                value = action.get("value")
                
                if not self.control_device(device_id, command, value):
                    self.logger.warning(f"Failed to execute action for device {device_id} in scene {scene_id}")
                    success = False
        
        if success:
            self.logger.info(f"Executed scene: {scene_id}")
        else:
            self.logger.warning(f"Scene {scene_id} executed with some errors")
        
        return success
    
    def get_scenes(self) -> Dict[str, Dict[str, Any]]:
        """Get available scenes
        
        Returns:
            Dictionary of scenes
        """
        return self.config.get("scenes", {})
    
    def refresh_devices(self) -> bool:
        """Refresh device states
        
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.connected:
            return False
        
        if self.platform == "home_assistant":
            return self._refresh_devices_home_assistant()
        
        # For MQTT, we rely on subscriptions for updates
        return True
    
    def _refresh_devices_home_assistant(self) -> bool:
        """Refresh device states from Home Assistant
        
        Returns:
            True if successful, False otherwise
        """
        if not REQUESTS_AVAILABLE:
            return False
        
        try:
            # Get states from Home Assistant API
            response = requests.get(f"{self.ha_url}/api/states", headers=self.ha_headers)
            
            if response.status_code != 200:
                self.logger.error(f"Error getting states from Home Assistant: {response.status_code}")
                return False
            
            states = response.json()
            
            # Update device states
            for device_id, device in self.devices.items():
                if "entity_id" in device:
                    entity_id = device["entity_id"]
                    
                    # Find matching state
                    for state in states:
                        if state["entity_id"] == entity_id:
                            self._update_device_state(device_id, state["state"])
                            break
            
            self.logger.info("Refreshed device states from Home Assistant")
            return True
        
        except Exception as e:
            self.logger.error(f"Error refreshing devices from Home Assistant: {e}")
            return False
    
    def shutdown(self):
        """Shutdown the home controller"""
        # Save devices
        self._save_devices()
        
        # Disconnect MQTT client
        if self.platform == "mqtt" and self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.client = None
        
        self.connected = False
        self.logger.info("Home controller shut down")