#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Device Synchronization Module for Jarvis Assistant

This module handles the synchronization of multiple devices with the Jarvis assistant,
allowing for seamless interaction across phones, laptops, and other devices.
"""

import os
import json
import logging
import threading
import time
import uuid
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime
import socket
import ssl

# Import for WebSockets
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

# Import for encryption
try:
    from cryptography.fernet import Fernet
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False


class DeviceInfo:
    """Class to store information about connected devices"""
    
    def __init__(self, device_id: str, device_name: str, device_type: str, 
                 capabilities: List[str], last_seen: float = None):
        """Initialize device information
        
        Args:
            device_id: Unique identifier for the device
            device_name: Human-readable name for the device
            device_type: Type of device (phone, laptop, tablet, etc.)
            capabilities: List of capabilities the device supports
            last_seen: Timestamp when the device was last seen
        """
        self.device_id = device_id
        self.device_name = device_name
        self.device_type = device_type
        self.capabilities = capabilities
        self.last_seen = last_seen or time.time()
        self.connected = True
        self.connection = None  # WebSocket connection object
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert device info to dictionary
        
        Returns:
            Dictionary representation of device info
        """
        return {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "device_type": self.device_type,
            "capabilities": self.capabilities,
            "last_seen": self.last_seen,
            "connected": self.connected
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeviceInfo':
        """Create device info from dictionary
        
        Args:
            data: Dictionary containing device info
            
        Returns:
            DeviceInfo object
        """
        return cls(
            device_id=data.get("device_id", ""),
            device_name=data.get("device_name", "Unknown Device"),
            device_type=data.get("device_type", "unknown"),
            capabilities=data.get("capabilities", []),
            last_seen=data.get("last_seen", time.time())
        )


class DeviceSyncManager:
    """Manager for device synchronization across multiple platforms"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the device sync manager
        
        Args:
            config: Configuration dictionary
        """
        self.logger = logging.getLogger("jarvis.connectivity.device_sync")
        self.config = config
        
        # Check if required libraries are available
        if not WEBSOCKETS_AVAILABLE:
            self.logger.error("WebSockets library not available. Please install with 'pip install websockets'")
            raise ImportError("WebSockets library not available")
        
        # Configuration
        self.server_host = config.get("server_host", "0.0.0.0")
        self.server_port = config.get("server_port", 8765)
        self.use_ssl = config.get("use_ssl", False)
        self.ssl_cert = config.get("ssl_cert", "")
        self.ssl_key = config.get("ssl_key", "")
        self.device_timeout = config.get("device_timeout", 300)  # seconds
        self.ping_interval = config.get("ping_interval", 30)  # seconds
        
        # Generate encryption key if not exists
        self.encryption_key_file = os.path.join(
            config.get("data_dir", "data"),
            "connectivity",
            "encryption_key.key"
        )
        self._initialize_encryption()
        
        # Connected devices
        self.devices: Dict[str, DeviceInfo] = {}
        self.devices_lock = threading.RLock()
        
        # Device data storage
        self.data_dir = os.path.join(config.get("data_dir", "data"), "connectivity")
        self.devices_file = os.path.join(self.data_dir, "devices.json")
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Load saved devices
        self._load_devices()
        
        # Server control
        self.server = None
        self.running = False
        self.server_thread = None
        self.cleanup_thread = None
        
        # Message handlers
        self.message_handlers: Dict[str, Callable] = {}
        self._register_default_handlers()
        
        # Event callbacks
        self.on_device_connected = None
        self.on_device_disconnected = None
        self.on_message_received = None
        
        self.logger.info("Device sync manager initialized")
    
    def _initialize_encryption(self):
        """Initialize encryption for secure communication"""
        if not ENCRYPTION_AVAILABLE:
            self.logger.warning("Cryptography library not available. Communication will not be encrypted.")
            self.encryption = None
            self.encryption_enabled = False
            return
        
        try:
            if os.path.exists(self.encryption_key_file):
                with open(self.encryption_key_file, "rb") as f:
                    key = f.read()
            else:
                # Generate a new key
                key = Fernet.generate_key()
                os.makedirs(os.path.dirname(self.encryption_key_file), exist_ok=True)
                with open(self.encryption_key_file, "wb") as f:
                    f.write(key)
            
            self.encryption = Fernet(key)
            self.encryption_enabled = True
            self.logger.info("Encryption initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing encryption: {e}")
            self.encryption = None
            self.encryption_enabled = False
    
    def _load_devices(self):
        """Load saved devices from file"""
        if not os.path.exists(self.devices_file):
            return
        
        try:
            with open(self.devices_file, "r") as f:
                devices_data = json.load(f)
            
            with self.devices_lock:
                for device_data in devices_data:
                    device = DeviceInfo.from_dict(device_data)
                    device.connected = False  # All loaded devices start as disconnected
                    self.devices[device.device_id] = device
            
            self.logger.info(f"Loaded {len(self.devices)} saved devices")
        except Exception as e:
            self.logger.error(f"Error loading devices: {e}")
    
    def _save_devices(self):
        """Save devices to file"""
        try:
            with self.devices_lock:
                devices_data = [device.to_dict() for device in self.devices.values()]
            
            with open(self.devices_file, "w") as f:
                json.dump(devices_data, f, indent=2)
            
            self.logger.debug("Saved devices to file")
        except Exception as e:
            self.logger.error(f"Error saving devices: {e}")
    
    def _register_default_handlers(self):
        """Register default message handlers"""
        self.message_handlers["register"] = self._handle_register
        self.message_handlers["ping"] = self._handle_ping
        self.message_handlers["command"] = self._handle_command
        self.message_handlers["notification"] = self._handle_notification
    
    async def _handle_register(self, device_id: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle device registration
        
        Args:
            device_id: Device ID
            message: Registration message
            
        Returns:
            Response message
        """
        device_name = message.get("device_name", "Unknown Device")
        device_type = message.get("device_type", "unknown")
        capabilities = message.get("capabilities", [])
        
        with self.devices_lock:
            if device_id in self.devices:
                # Update existing device
                device = self.devices[device_id]
                device.device_name = device_name
                device.device_type = device_type
                device.capabilities = capabilities
                device.last_seen = time.time()
                device.connected = True
                self.logger.info(f"Device reconnected: {device_name} ({device_id})")
            else:
                # Register new device
                device = DeviceInfo(
                    device_id=device_id,
                    device_name=device_name,
                    device_type=device_type,
                    capabilities=capabilities
                )
                self.devices[device_id] = device
                self.logger.info(f"New device registered: {device_name} ({device_id})")
        
        # Save devices
        self._save_devices()
        
        # Call callback if registered
        if self.on_device_connected:
            self.on_device_connected(device)
        
        return {
            "status": "success",
            "message": "Device registered successfully",
            "server_name": self.config.get("server_name", "Jarvis Assistant"),
            "server_version": self.config.get("server_version", "1.0.0")
        }
    
    async def _handle_ping(self, device_id: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping message
        
        Args:
            device_id: Device ID
            message: Ping message
            
        Returns:
            Pong response
        """
        with self.devices_lock:
            if device_id in self.devices:
                self.devices[device_id].last_seen = time.time()
        
        return {
            "status": "success",
            "message": "pong",
            "timestamp": time.time()
        }
    
    async def _handle_command(self, device_id: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle command message
        
        Args:
            device_id: Device ID
            message: Command message
            
        Returns:
            Command response
        """
        command = message.get("command", "")
        args = message.get("args", {})
        
        self.logger.info(f"Received command from device {device_id}: {command}")
        
        # This would be handled by the main assistant
        if self.on_message_received:
            response = await self.on_message_received(device_id, "command", {
                "command": command,
                "args": args
            })
            return response
        
        return {
            "status": "error",
            "message": "Command handler not registered"
        }
    
    async def _handle_notification(self, device_id: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle notification message
        
        Args:
            device_id: Device ID
            message: Notification message
            
        Returns:
            Notification response
        """
        notification_type = message.get("type", "")
        notification_data = message.get("data", {})
        
        self.logger.info(f"Received notification from device {device_id}: {notification_type}")
        
        # This would be handled by the main assistant
        if self.on_message_received:
            response = await self.on_message_received(device_id, "notification", {
                "type": notification_type,
                "data": notification_data
            })
            return response
        
        return {
            "status": "success",
            "message": "Notification received"
        }
    
    async def start_server(self):
        """Start the WebSocket server"""
        if not WEBSOCKETS_AVAILABLE:
            self.logger.error("Cannot start server: WebSockets library not available")
            self.running = False
            return False
        
        if self.running:
            self.logger.warning("Server is already running")
            return True
        
        try:
            # Set up SSL if enabled
            ssl_context = None
            if self.use_ssl and self.ssl_cert and self.ssl_key:
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ssl_context.load_cert_chain(self.ssl_cert, self.ssl_key)
            
            # Start server
            self.server = await websockets.serve(
                self._handle_connection,
                self.server_host,
                self.server_port,
                ssl=ssl_context
            )
            
            self.running = True
            self.logger.info(f"WebSocket server started on {self.server_host}:{self.server_port}")
            
            # Start cleanup thread
            self.cleanup_thread = threading.Thread(target=self._cleanup_disconnected_devices)
            self.cleanup_thread.daemon = True
            self.cleanup_thread.start()
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error starting WebSocket server: {e}")
            return False
    
    def start(self):
        """Start the device sync manager in a separate thread"""
        if self.server_thread and self.server_thread.is_alive():
            self.logger.warning("Server thread is already running")
            return
        
        self.server_thread = threading.Thread(target=self._run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
    
    def _run_server(self):
        """Run the WebSocket server in a separate thread"""
        import asyncio
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self.start_server())
            loop.run_forever()
        except Exception as e:
            self.logger.error(f"Error in server thread: {e}")
        finally:
            loop.close()
    
    def stop(self):
        """Stop the device sync manager"""
        if not self.running:
            return
        
        self.running = False
        
        # Close server
        if self.server:
            self.server.close()
        
        # Save devices
        self._save_devices()
        
        self.logger.info("Device sync manager stopped")
    
    async def _handle_connection(self, websocket, path):
        """Handle a new WebSocket connection
        
        Args:
            websocket: WebSocket connection
            path: Connection path
        """
        device_id = None
        
        try:
            # Wait for registration message
            message = await websocket.recv()
            data = json.loads(message)
            
            # Decrypt message if encryption is enabled
            if self.encryption and "encrypted" in data and data["encrypted"]:
                encrypted_data = data.get("data", "")
                decrypted_data = self.encryption.decrypt(encrypted_data.encode()).decode()
                data = json.loads(decrypted_data)
            
            # Check message type
            if data.get("type") != "register":
                await websocket.send(json.dumps({
                    "status": "error",
                    "message": "First message must be registration"
                }))
                return
            
            # Get or generate device ID
            device_id = data.get("device_id")
            if not device_id:
                device_id = str(uuid.uuid4())
                data["device_id"] = device_id
            
            # Handle registration
            response = await self._handle_register(device_id, data)
            await websocket.send(json.dumps(response))
            
            # Store connection
            with self.devices_lock:
                if device_id in self.devices:
                    self.devices[device_id].connection = websocket
            
            # Handle messages
            while self.running:
                message = await websocket.recv()
                await self._process_message(device_id, websocket, message)
        
        except websockets.exceptions.ConnectionClosed:
            self.logger.info(f"Connection closed for device {device_id}")
        except Exception as e:
            self.logger.error(f"Error handling connection: {e}")
        finally:
            # Mark device as disconnected
            if device_id:
                with self.devices_lock:
                    if device_id in self.devices:
                        self.devices[device_id].connected = False
                        self.devices[device_id].connection = None
                
                # Call callback if registered
                if self.on_device_disconnected:
                    with self.devices_lock:
                        if device_id in self.devices:
                            self.on_device_disconnected(self.devices[device_id])
    
    async def _process_message(self, device_id: str, websocket, message: str):
        """Process a message from a device
        
        Args:
            device_id: Device ID
            websocket: WebSocket connection
            message: Message string
        """
        try:
            data = json.loads(message)
            
            # Decrypt message if encryption is enabled
            if self.encryption and "encrypted" in data and data["encrypted"]:
                encrypted_data = data.get("data", "")
                decrypted_data = self.encryption.decrypt(encrypted_data.encode()).decode()
                data = json.loads(decrypted_data)
            
            # Update last seen timestamp
            with self.devices_lock:
                if device_id in self.devices:
                    self.devices[device_id].last_seen = time.time()
            
            # Process message based on type
            message_type = data.get("type", "")
            if message_type in self.message_handlers:
                response = await self.message_handlers[message_type](device_id, data)
            else:
                response = {
                    "status": "error",
                    "message": f"Unknown message type: {message_type}"
                }
            
            # Encrypt response if encryption is enabled
            if self.encryption and "encrypted" in data and data["encrypted"]:
                encrypted_response = self.encryption.encrypt(json.dumps(response).encode()).decode()
                response = {
                    "encrypted": True,
                    "data": encrypted_response
                }
            
            # Send response
            await websocket.send(json.dumps(response))
        
        except json.JSONDecodeError:
            self.logger.error(f"Invalid JSON from device {device_id}")
            await websocket.send(json.dumps({
                "status": "error",
                "message": "Invalid JSON"
            }))
        except Exception as e:
            self.logger.error(f"Error processing message from device {device_id}: {e}")
            await websocket.send(json.dumps({
                "status": "error",
                "message": f"Error processing message: {str(e)}"
            }))
    
    def _cleanup_disconnected_devices(self):
        """Periodically clean up disconnected devices"""
        while self.running:
            try:
                current_time = time.time()
                devices_to_disconnect = []
                devices_info = {}
                
                with self.devices_lock:
                    for device_id, device in self.devices.items():
                        # Check if device has timed out
                        if device.connected and (current_time - device.last_seen) > self.device_timeout:
                            devices_to_disconnect.append(device_id)
                            # Store a copy of the device info for callback
                            devices_info[device_id] = self.devices[device_id]
                
                # Disconnect timed out devices
                for device_id in devices_to_disconnect:
                    self.logger.info(f"Device timed out: {device_id}")
                    with self.devices_lock:
                        if device_id in self.devices:
                            self.devices[device_id].connected = False
                            self.devices[device_id].connection = None
                    
                    # Call callback if registered
                    if self.on_device_disconnected and device_id in devices_info:
                        self.on_device_disconnected(devices_info[device_id])
                
                # Save devices periodically
                self._save_devices()
                
                # Sleep for a while
                time.sleep(self.ping_interval)
            
            except Exception as e:
                self.logger.error(f"Error in cleanup thread: {e}")
                time.sleep(self.ping_interval)
    
    async def send_message(self, device_id: str, message_type: str, data: Dict[str, Any]) -> bool:
        """Send a message to a specific device
        
        Args:
            device_id: Device ID
            message_type: Message type
            data: Message data
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        with self.devices_lock:
            if device_id not in self.devices or not self.devices[device_id].connected:
                self.logger.warning(f"Cannot send message to device {device_id}: Device not connected")
                return False
            
            websocket = self.devices[device_id].connection
        
        if not websocket:
            return False
        
        try:
            # Prepare message
            message = {
                "type": message_type,
                **data
            }
            
            # Encrypt message if encryption is enabled
            if self.encryption:
                encrypted_data = self.encryption.encrypt(json.dumps(message).encode()).decode()
                message = {
                    "encrypted": True,
                    "data": encrypted_data
                }
            
            # Send message
            await websocket.send(json.dumps(message))
            return True
        
        except Exception as e:
            self.logger.error(f"Error sending message to device {device_id}: {e}")
            return False
    
    def broadcast_message(self, message_type: str, data: Dict[str, Any], 
                         device_types: List[str] = None) -> int:
        """Broadcast a message to all connected devices
        
        Args:
            message_type: Message type
            data: Message data
            device_types: Optional list of device types to filter by
            
        Returns:
            Number of devices the message was sent to
        """
        import asyncio
        
        connected_devices = []
        
        with self.devices_lock:
            for device_id, device in self.devices.items():
                if device.connected and (not device_types or device.device_type in device_types):
                    connected_devices.append(device_id)
        
        if not connected_devices:
            return 0
        
        # Use a single event loop for all send operations
        loop = asyncio.new_event_loop()
        try:
            async def send_all():
                sent_count = 0
                for device_id in connected_devices:
                    try:
                        if await self.send_message(device_id, message_type, data):
                            sent_count += 1
                    except Exception as e:
                        self.logger.error(f"Error sending to device {device_id}: {e}")
                return sent_count
            
            return loop.run_until_complete(send_all())
        except Exception as e:
            self.logger.error(f"Error in broadcast: {e}")
            return 0
        finally:
            loop.close()
    
    def get_connected_devices(self, device_type: str = None) -> List[DeviceInfo]:
        """Get a list of connected devices
        
        Args:
            device_type: Optional device type to filter by
            
        Returns:
            List of connected devices
        """
        with self.devices_lock:
            if device_type:
                return [device for device in self.devices.values() 
                        if device.connected and device.device_type == device_type]
            else:
                return [device for device in self.devices.values() if device.connected]
    
    def get_device_by_id(self, device_id: str) -> Optional[DeviceInfo]:
        """Get a device by ID
        
        Args:
            device_id: Device ID
            
        Returns:
            DeviceInfo object or None if not found
        """
        with self.devices_lock:
            return self.devices.get(device_id)
    
    def get_device_by_name(self, device_name: str) -> Optional[DeviceInfo]:
        """Get a device by name
        
        Args:
            device_name: Device name
            
        Returns:
            DeviceInfo object or None if not found
        """
        with self.devices_lock:
            for device in self.devices.values():
                if device.device_name.lower() == device_name.lower():
                    return device
        return None