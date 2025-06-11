#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Device Client Module for Jarvis Assistant

This module provides client functionality for connecting remote devices to the Jarvis assistant.
It handles device registration, command sending, and notification management.
"""

import os
import json
import logging
import threading
import time
import uuid
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime
import asyncio
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


class DeviceClient:
    """Client for connecting to Jarvis assistant from remote devices"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the device client
        
        Args:
            config: Configuration dictionary
        """
        self.logger = logging.getLogger("jarvis.connectivity.device_client")
        self.config = config
        
        # Check if required libraries are available
        if not WEBSOCKETS_AVAILABLE:
            self.logger.error("WebSockets library not available. Please install with 'pip install websockets'")
            raise ImportError("WebSockets library not available")
        
        # Configuration
        self.server_host = config.get("server_host", "localhost")
        self.server_port = config.get("server_port", 8765)
        self.use_ssl = config.get("use_ssl", False)
        self.verify_ssl = config.get("verify_ssl", True)
        self.reconnect_interval = config.get("reconnect_interval", 5)  # seconds
        self.ping_interval = config.get("ping_interval", 30)  # seconds
        
        # Device information
        self.device_id = config.get("device_id", str(uuid.uuid4()))
        self.device_name = config.get("device_name", "Jarvis Client")
        self.device_type = config.get("device_type", "client")
        self.capabilities = config.get("capabilities", ["command", "notification"])
        
        # Encryption
        self.encryption_key = config.get("encryption_key", None)
        self._initialize_encryption()
        
        # Connection state
        self.websocket = None
        self.connected = False
        self.running = False
        self.connection_thread = None
        self.ping_thread = None
        
        # Message handlers
        self.message_handlers: Dict[str, Callable] = {}
        self._register_default_handlers()
        
        # Event callbacks
        self.on_connected = None
        self.on_disconnected = None
        self.on_message_received = None
        
        # Message queue for sending when reconnected
        self.message_queue = []
        self.message_queue_lock = threading.RLock()
        
        self.logger.info("Device client initialized")
    
    def _initialize_encryption(self):
        """Initialize encryption for secure communication"""
        if not ENCRYPTION_AVAILABLE:
            self.logger.warning("Cryptography library not available. Communication will not be encrypted.")
            self.encryption = None
            return
        
        try:
            if self.encryption_key:
                self.encryption = Fernet(self.encryption_key)
                self.logger.info("Encryption initialized with provided key")
            else:
                self.encryption = None
                self.logger.info("No encryption key provided. Communication will not be encrypted.")
        except Exception as e:
            self.logger.error(f"Error initializing encryption: {e}")
            self.encryption = None
    
    def _register_default_handlers(self):
        """Register default message handlers"""
        self.message_handlers["command"] = self._handle_command
        self.message_handlers["notification"] = self._handle_notification
    
    def register_handler(self, message_type: str, handler: Callable):
        """Register a message handler
        
        Args:
            message_type: Type of message to handle
            handler: Handler function
        """
        self.message_handlers[message_type] = handler
    
    async def _handle_command(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle command message from server
        
        Args:
            message: Command message
            
        Returns:
            Command response
        """
        command = message.get("command", "")
        args = message.get("args", {})
        
        self.logger.info(f"Received command from server: {command}")
        
        # Call callback if registered
        if self.on_message_received:
            response = await self.on_message_received("command", {
                "command": command,
                "args": args
            })
            return response
        
        return {
            "status": "error",
            "message": "Command handler not registered"
        }
    
    async def _handle_notification(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle notification message from server
        
        Args:
            message: Notification message
            
        Returns:
            Notification response
        """
        notification_type = message.get("type", "")
        notification_data = message.get("data", {})
        
        self.logger.info(f"Received notification from server: {notification_type}")
        
        # Call callback if registered
        if self.on_message_received:
            response = await self.on_message_received("notification", {
                "type": notification_type,
                "data": notification_data
            })
            return response
        
        return {
            "status": "success",
            "message": "Notification received"
        }
    
    async def connect(self):
        """Connect to the Jarvis server"""
        if not WEBSOCKETS_AVAILABLE:
            self.logger.error("Cannot connect: WebSockets library not available")
            return False
        
        if self.connected:
            self.logger.warning("Already connected to server")
            return True
        
        try:
            # Set up SSL if enabled
            ssl_context = None
            if self.use_ssl:
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                if self.verify_ssl:
                    ssl_context.verify_mode = ssl.CERT_REQUIRED
                    ssl_context.check_hostname = True
                    ssl_context.load_default_certs()
                else:
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
            
            # Connect to server
            uri = f"{'wss' if self.use_ssl else 'ws'}://{self.server_host}:{self.server_port}"
            self.websocket = await websockets.connect(uri, ssl=ssl_context)
            
            # Register device
            registration_message = {
                "type": "register",
                "device_id": self.device_id,
                "device_name": self.device_name,
                "device_type": self.device_type,
                "capabilities": self.capabilities
            }
            
            # Encrypt message if encryption is enabled
            if self.encryption:
                encrypted_data = self.encryption.encrypt(json.dumps(registration_message).encode()).decode()
                registration_message = {
                    "encrypted": True,
                    "data": encrypted_data
                }
            
            await self.websocket.send(json.dumps(registration_message))
            response = await self.websocket.recv()
            response_data = json.loads(response)
            
            # Decrypt response if encrypted
            if self.encryption and "encrypted" in response_data and response_data["encrypted"]:
                encrypted_data = response_data.get("data", "")
                decrypted_data = self.encryption.decrypt(encrypted_data.encode()).decode()
                response_data = json.loads(decrypted_data)
            
            if response_data.get("status") != "success":
                self.logger.error(f"Registration failed: {response_data.get('message', 'Unknown error')}")
                await self.websocket.close()
                self.websocket = None
                return False
            
            self.connected = True
            self.logger.info(f"Connected to Jarvis server at {uri}")
            
            # Call callback if registered
            if self.on_connected:
                self.on_connected()
            
            # Send queued messages
            await self._send_queued_messages()
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error connecting to server: {e}")
            if self.websocket:
                await self.websocket.close()
                self.websocket = None
            return False
    
    async def _send_queued_messages(self):
        """Send queued messages after reconnecting"""
        with self.message_queue_lock:
            if not self.message_queue:
                return
            
            self.logger.info(f"Sending {len(self.message_queue)} queued messages")
            
            for message_type, data in self.message_queue:
                await self.send_message(message_type, data)
            
            self.message_queue.clear()
    
    async def disconnect(self):
        """Disconnect from the Jarvis server"""
        if not self.connected or not self.websocket:
            return
        
        try:
            await self.websocket.close()
        except Exception as e:
            self.logger.error(f"Error disconnecting from server: {e}")
        finally:
            self.websocket = None
            self.connected = False
            
            # Call callback if registered
            if self.on_disconnected:
                self.on_disconnected()
            
            self.logger.info("Disconnected from Jarvis server")
    
    def start(self):
        """Start the device client in a separate thread"""
        if self.connection_thread and self.connection_thread.is_alive():
            self.logger.warning("Client thread is already running")
            return
        
        self.running = True
        
        # Start connection thread
        self.connection_thread = threading.Thread(target=self._run_client)
        self.connection_thread.daemon = True
        self.connection_thread.start()
        
        # Start ping thread
        self.ping_thread = threading.Thread(target=self._ping_server)
        self.ping_thread.daemon = True
        self.ping_thread.start()
        
        self.logger.info("Device client started")
    
    def stop(self):
        """Stop the device client"""
        if not self.running:
            return
        
        self.running = False
        
        # Disconnect from server
        if self.connected:
            # Try to use the existing loop if available
            if hasattr(self, 'loop') and self.loop and not self.loop.is_closed():
                try:
                    asyncio.run_coroutine_threadsafe(self.disconnect(), self.loop)
                except Exception as e:
                    self.logger.error(f"Error disconnecting with main loop: {e}")
                    # Fallback to a new loop
                    loop = asyncio.new_event_loop()
                    try:
                        loop.run_until_complete(self.disconnect())
                    finally:
                        loop.close()
            else:
                # Create a new loop as fallback
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(self.disconnect())
                finally:
                    loop.close()
        
        # Clean up the main loop
        if hasattr(self, 'loop') and self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.loop.stop)
        
        self.logger.info("Device client stopped")
    
    def _run_client(self):
        """Run the client connection in a separate thread"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            while self.running:
                if not self.connected:
                    # Try to connect
                    if self.loop.run_until_complete(self.connect()):
                        # Start message handling loop
                        try:
                            self.loop.run_until_complete(self._handle_messages())
                        except Exception as e:
                            self.logger.error(f"Error in message handling: {e}")
                    
                    # Wait before reconnecting
                    if self.running and not self.connected:
                        time.sleep(self.reconnect_interval)
                else:
                    # Already connected, just wait
                    time.sleep(1)
        
        except Exception as e:
            self.logger.error(f"Error in client thread: {e}")
        finally:
            # Ensure we're disconnected
            if self.connected:
                try:
                    loop.run_until_complete(self.disconnect())
                except Exception:
                    pass
            loop.close()
    
    async def _handle_messages(self):
        """Handle incoming messages from the server"""
        if not self.connected or not self.websocket:
            return
        
        try:
            while self.connected and self.running:
                # Wait for message
                message = await self.websocket.recv()
                await self._process_message(message)
        
        except websockets.exceptions.ConnectionClosed:
            self.logger.info("Connection closed by server")
        except Exception as e:
            self.logger.error(f"Error handling messages: {e}")
        finally:
            # Mark as disconnected
            self.connected = False
            self.websocket = None
            
            # Call callback if registered
            if self.on_disconnected:
                self.on_disconnected()
    
    async def _process_message(self, message: str):
        """Process a message from the server
        
        Args:
            message: Message string
        """
        try:
            data = json.loads(message)
            
            # Decrypt message if encryption is enabled
            if self.encryption and "encrypted" in data and data["encrypted"]:
                encrypted_data = data.get("data", "")
                decrypted_data = self.encryption.decrypt(encrypted_data.encode()).decode()
                data = json.loads(decrypted_data)
            
            # Process message based on type
            message_type = data.get("type", "")
            if message_type in self.message_handlers:
                response = await self.message_handlers[message_type](data)
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
            await self.websocket.send(json.dumps(response))
        
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON from server")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
    
    def _ping_server(self):
        """Periodically ping the server to keep the connection alive"""
        while self.running:
            try:
                if self.connected:
                    # Use the main event loop if available, otherwise create a new one
                    if hasattr(self, 'loop') and self.loop and not self.loop.is_closed():
                        asyncio.run_coroutine_threadsafe(self.send_message("ping", {
                            "timestamp": time.time()
                        }), self.loop)
                    else:
                        # Create a new event loop for ping as fallback
                        loop = asyncio.new_event_loop()
                        try:
                            loop.run_until_complete(self.send_message("ping", {
                                "timestamp": time.time()
                            }))
                        finally:
                            loop.close()
            
            except Exception as e:
                self.logger.error(f"Error in ping thread: {e}")
            
            # Sleep for ping interval
            time.sleep(self.ping_interval)
    
    async def send_message(self, message_type: str, data: Dict[str, Any]) -> bool:
        """Send a message to the server
        
        Args:
            message_type: Message type
            data: Message data
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self.connected or not self.websocket:
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            self.logger.debug(f"Queued message of type {message_type} for later sending")
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
            await self.websocket.send(json.dumps(message))
            return True
        
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            # Mark as disconnected on error
            self.connected = False
            self.websocket = None
            
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            
            return False
    
    def send_command(self, command: str, args: Dict[str, Any] = None) -> bool:
        """Send a command to the server
        
        Args:
            command: Command name
            args: Command arguments
            
        Returns:
            True if command was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("command", {
                        "command": command,
                        "args": args or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("command", {
                "command": command,
                "args": args or {}
            }))
        except Exception as e:
            self.logger.error(f"Error sending command: {e}")
            return False
        finally:
            loop.close()
    
    def send_notification(self, notification_type: str, data: Dict[str, Any] = None) -> bool:
        """Send a notification to the server
        
        Args:
            notification_type: Notification type
            data: Notification data
            
        Returns:
            True if notification was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("notification", {
                        "type": notification_type,
                        "data": data or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("notification", {
                "type": notification_type,
                "data": data or {}
            }))
        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")
            return False
        finally:
            loop.close()
    
    async def _handle_messages(self):
        """Handle incoming messages from the server"""
        if not self.connected or not self.websocket:
            return
        
        try:
            while self.connected and self.running:
                # Wait for message
                message = await self.websocket.recv()
                await self._process_message(message)
        
        except websockets.exceptions.ConnectionClosed:
            self.logger.info("Connection closed by server")
        except Exception as e:
            self.logger.error(f"Error handling messages: {e}")
        finally:
            # Mark as disconnected
            self.connected = False
            self.websocket = None
            
            # Call callback if registered
            if self.on_disconnected:
                self.on_disconnected()
    
    async def _process_message(self, message: str):
        """Process a message from the server
        
        Args:
            message: Message string
        """
        try:
            data = json.loads(message)
            
            # Decrypt message if encryption is enabled
            if self.encryption and "encrypted" in data and data["encrypted"]:
                encrypted_data = data.get("data", "")
                decrypted_data = self.encryption.decrypt(encrypted_data.encode()).decode()
                data = json.loads(decrypted_data)
            
            # Process message based on type
            message_type = data.get("type", "")
            if message_type in self.message_handlers:
                response = await self.message_handlers[message_type](data)
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
            await self.websocket.send(json.dumps(response))
        
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON from server")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
    
    async def send_message(self, message_type: str, data: Dict[str, Any]) -> bool:
        """Send a message to the server
        
        Args:
            message_type: Message type
            data: Message data
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self.connected or not self.websocket:
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            self.logger.debug(f"Queued message of type {message_type} for later sending")
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
            await self.websocket.send(json.dumps(message))
            return True
        
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            # Mark as disconnected on error
            self.connected = False
            self.websocket = None
            
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            
            return False
    
    def send_command(self, command: str, args: Dict[str, Any] = None) -> bool:
        """Send a command to the server
        
        Args:
            command: Command name
            args: Command arguments
            
        Returns:
            True if command was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("command", {
                        "command": command,
                        "args": args or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("command", {
                "command": command,
                "args": args or {}
            }))
        except Exception as e:
            self.logger.error(f"Error sending command: {e}")
            return False
        finally:
            loop.close()
    
    def send_notification(self, notification_type: str, data: Dict[str, Any] = None) -> bool:
        """Send a notification to the server
        
        Args:
            notification_type: Notification type
            data: Notification data
            
        Returns:
            True if notification was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("notification", {
                        "type": notification_type,
                        "data": data or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("notification", {
                "type": notification_type,
                "data": data or {}
            }))
        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")
            return False
        finally:
            loop.close()
    
    async def _handle_messages(self):
        """Handle incoming messages from the server"""
        if not self.connected or not self.websocket:
            return
        
        try:
            while self.connected and self.running:
                # Wait for message
                message = await self.websocket.recv()
                await self._process_message(message)
        
        except websockets.exceptions.ConnectionClosed:
            self.logger.info("Connection closed by server")
        except Exception as e:
            self.logger.error(f"Error handling messages: {e}")
        finally:
            # Mark as disconnected
            self.connected = False
            self.websocket = None
            
            # Call callback if registered
            if self.on_disconnected:
                self.on_disconnected()
    
    async def _process_message(self, message: str):
        """Process a message from the server
        
        Args:
            message: Message string
        """
        try:
            data = json.loads(message)
            
            # Decrypt message if encryption is enabled
            if self.encryption and "encrypted" in data and data["encrypted"]:
                encrypted_data = data.get("data", "")
                decrypted_data = self.encryption.decrypt(encrypted_data.encode()).decode()
                data = json.loads(decrypted_data)
            
            # Process message based on type
            message_type = data.get("type", "")
            if message_type in self.message_handlers:
                response = await self.message_handlers[message_type](data)
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
            await self.websocket.send(json.dumps(response))
        
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON from server")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
    
    async def send_message(self, message_type: str, data: Dict[str, Any]) -> bool:
        """Send a message to the server
        
        Args:
            message_type: Message type
            data: Message data
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self.connected or not self.websocket:
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            self.logger.debug(f"Queued message of type {message_type} for later sending")
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
            await self.websocket.send(json.dumps(message))
            return True
        
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            # Mark as disconnected on error
            self.connected = False
            self.websocket = None
            
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            
            return False
    
    def send_command(self, command: str, args: Dict[str, Any] = None) -> bool:
        """Send a command to the server
        
        Args:
            command: Command name
            args: Command arguments
            
        Returns:
            True if command was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("command", {
                        "command": command,
                        "args": args or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("command", {
                "command": command,
                "args": args or {}
            }))
        except Exception as e:
            self.logger.error(f"Error sending command: {e}")
            return False
        finally:
            loop.close()
    
    def send_notification(self, notification_type: str, data: Dict[str, Any] = None) -> bool:
        """Send a notification to the server
        
        Args:
            notification_type: Notification type
            data: Notification data
            
        Returns:
            True if notification was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("notification", {
                        "type": notification_type,
                        "data": data or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("notification", {
                "type": notification_type,
                "data": data or {}
            }))
        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")
            return False
        finally:
            loop.close()
    
    async def _handle_messages(self):
        """Handle incoming messages from the server"""
        if not self.connected or not self.websocket:
            return
        
        try:
            while self.connected and self.running:
                # Wait for message
                message = await self.websocket.recv()
                await self._process_message(message)
        
        except websockets.exceptions.ConnectionClosed:
            self.logger.info("Connection closed by server")
        except Exception as e:
            self.logger.error(f"Error handling messages: {e}")
        finally:
            # Mark as disconnected
            self.connected = False
            self.websocket = None
            
            # Call callback if registered
            if self.on_disconnected:
                self.on_disconnected()
    
    async def _process_message(self, message: str):
        """Process a message from the server
        
        Args:
            message: Message string
        """
        try:
            data = json.loads(message)
            
            # Decrypt message if encryption is enabled
            if self.encryption and "encrypted" in data and data["encrypted"]:
                encrypted_data = data.get("data", "")
                decrypted_data = self.encryption.decrypt(encrypted_data.encode()).decode()
                data = json.loads(decrypted_data)
            
            # Process message based on type
            message_type = data.get("type", "")
            if message_type in self.message_handlers:
                response = await self.message_handlers[message_type](data)
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
            await self.websocket.send(json.dumps(response))
        
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON from server")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
    
    async def send_message(self, message_type: str, data: Dict[str, Any]) -> bool:
        """Send a message to the server
        
        Args:
            message_type: Message type
            data: Message data
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self.connected or not self.websocket:
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            self.logger.debug(f"Queued message of type {message_type} for later sending")
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
            await self.websocket.send(json.dumps(message))
            return True
        
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            # Mark as disconnected on error
            self.connected = False
            self.websocket = None
            
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            
            return False
    
    def send_command(self, command: str, args: Dict[str, Any] = None) -> bool:
        """Send a command to the server
        
        Args:
            command: Command name
            args: Command arguments
            
        Returns:
            True if command was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("command", {
                        "command": command,
                        "args": args or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("command", {
                "command": command,
                "args": args or {}
            }))
        except Exception as e:
            self.logger.error(f"Error sending command: {e}")
            return False
        finally:
            loop.close()
    
    def send_notification(self, notification_type: str, data: Dict[str, Any] = None) -> bool:
        """Send a notification to the server
        
        Args:
            notification_type: Notification type
            data: Notification data
            
        Returns:
            True if notification was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("notification", {
                        "type": notification_type,
                        "data": data or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("notification", {
                "type": notification_type,
                "data": data or {}
            }))
        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")
            return False
        finally:
            loop.close()
    
    async def _handle_messages(self):
        """Handle incoming messages from the server"""
        if not self.connected or not self.websocket:
            return
        
        try:
            while self.connected and self.running:
                # Wait for message
                message = await self.websocket.recv()
                await self._process_message(message)
        
        except websockets.exceptions.ConnectionClosed:
            self.logger.info("Connection closed by server")
        except Exception as e:
            self.logger.error(f"Error handling messages: {e}")
        finally:
            # Mark as disconnected
            self.connected = False
            self.websocket = None
            
            # Call callback if registered
            if self.on_disconnected:
                self.on_disconnected()
    
    async def _process_message(self, message: str):
        """Process a message from the server
        
        Args:
            message: Message string
        """
        try:
            data = json.loads(message)
            
            # Decrypt message if encryption is enabled
            if self.encryption and "encrypted" in data and data["encrypted"]:
                encrypted_data = data.get("data", "")
                decrypted_data = self.encryption.decrypt(encrypted_data.encode()).decode()
                data = json.loads(decrypted_data)
            
            # Process message based on type
            message_type = data.get("type", "")
            if message_type in self.message_handlers:
                response = await self.message_handlers[message_type](data)
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
            await self.websocket.send(json.dumps(response))
        
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON from server")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
    
    async def send_message(self, message_type: str, data: Dict[str, Any]) -> bool:
        """Send a message to the server
        
        Args:
            message_type: Message type
            data: Message data
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self.connected or not self.websocket:
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            self.logger.debug(f"Queued message of type {message_type} for later sending")
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
            await self.websocket.send(json.dumps(message))
            return True
        
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            # Mark as disconnected on error
            self.connected = False
            self.websocket = None
            
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            
            return False
    
    def send_command(self, command: str, args: Dict[str, Any] = None) -> bool:
        """Send a command to the server
        
        Args:
            command: Command name
            args: Command arguments
            
        Returns:
            True if command was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("command", {
                        "command": command,
                        "args": args or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("command", {
                "command": command,
                "args": args or {}
            }))
        except Exception as e:
            self.logger.error(f"Error sending command: {e}")
            return False
        finally:
            loop.close()
    
    def send_notification(self, notification_type: str, data: Dict[str, Any] = None) -> bool:
        """Send a notification to the server
        
        Args:
            notification_type: Notification type
            data: Notification data
            
        Returns:
            True if notification was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("notification", {
                        "type": notification_type,
                        "data": data or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("notification", {
                "type": notification_type,
                "data": data or {}
            }))
        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")
            return False
        finally:
            loop.close()
    
    async def _handle_messages(self):
        """Handle incoming messages from the server"""
        if not self.connected or not self.websocket:
            return
        
        try:
            while self.connected and self.running:
                # Wait for message
                message = await self.websocket.recv()
                await self._process_message(message)
        
        except websockets.exceptions.ConnectionClosed:
            self.logger.info("Connection closed by server")
        except Exception as e:
            self.logger.error(f"Error handling messages: {e}")
        finally:
            # Mark as disconnected
            self.connected = False
            self.websocket = None
            
            # Call callback if registered
            if self.on_disconnected:
                self.on_disconnected()
    
    async def _process_message(self, message: str):
        """Process a message from the server
        
        Args:
            message: Message string
        """
        try:
            data = json.loads(message)
            
            # Decrypt message if encryption is enabled
            if self.encryption and "encrypted" in data and data["encrypted"]:
                encrypted_data = data.get("data", "")
                decrypted_data = self.encryption.decrypt(encrypted_data.encode()).decode()
                data = json.loads(decrypted_data)
            
            # Process message based on type
            message_type = data.get("type", "")
            if message_type in self.message_handlers:
                response = await self.message_handlers[message_type](data)
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
            await self.websocket.send(json.dumps(response))
        
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON from server")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
    
    async def send_message(self, message_type: str, data: Dict[str, Any]) -> bool:
        """Send a message to the server
        
        Args:
            message_type: Message type
            data: Message data
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self.connected or not self.websocket:
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            self.logger.debug(f"Queued message of type {message_type} for later sending")
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
            await self.websocket.send(json.dumps(message))
            return True
        
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            # Mark as disconnected on error
            self.connected = False
            self.websocket = None
            
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            
            return False
    
    def send_command(self, command: str, args: Dict[str, Any] = None) -> bool:
        """Send a command to the server
        
        Args:
            command: Command name
            args: Command arguments
            
        Returns:
            True if command was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("command", {
                        "command": command,
                        "args": args or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("command", {
                "command": command,
                "args": args or {}
            }))
        except Exception as e:
            self.logger.error(f"Error sending command: {e}")
            return False
        finally:
            loop.close()
    
    def send_notification(self, notification_type: str, data: Dict[str, Any] = None) -> bool:
        """Send a notification to the server
        
        Args:
            notification_type: Notification type
            data: Notification data
            
        Returns:
            True if notification was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("notification", {
                        "type": notification_type,
                        "data": data or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("notification", {
                "type": notification_type,
                "data": data or {}
            }))
        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")
            return False
        finally:
            loop.close()
    
    async def _handle_messages(self):
        """Handle incoming messages from the server"""
        if not self.connected or not self.websocket:
            return
        
        try:
            while self.connected and self.running:
                # Wait for message
                message = await self.websocket.recv()
                await self._process_message(message)
        
        except websockets.exceptions.ConnectionClosed:
            self.logger.info("Connection closed by server")
        except Exception as e:
            self.logger.error(f"Error handling messages: {e}")
        finally:
            # Mark as disconnected
            self.connected = False
            self.websocket = None
            
            # Call callback if registered
            if self.on_disconnected:
                self.on_disconnected()
    
    async def _process_message(self, message: str):
        """Process a message from the server
        
        Args:
            message: Message string
        """
        try:
            data = json.loads(message)
            
            # Decrypt message if encryption is enabled
            if self.encryption and "encrypted" in data and data["encrypted"]:
                encrypted_data = data.get("data", "")
                decrypted_data = self.encryption.decrypt(encrypted_data.encode()).decode()
                data = json.loads(decrypted_data)
            
            # Process message based on type
            message_type = data.get("type", "")
            if message_type in self.message_handlers:
                response = await self.message_handlers[message_type](data)
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
            await self.websocket.send(json.dumps(response))
        
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON from server")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
    
    async def send_message(self, message_type: str, data: Dict[str, Any]) -> bool:
        """Send a message to the server
        
        Args:
            message_type: Message type
            data: Message data
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self.connected or not self.websocket:
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            self.logger.debug(f"Queued message of type {message_type} for later sending")
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
            await self.websocket.send(json.dumps(message))
            return True
        
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            # Mark as disconnected on error
            self.connected = False
            self.websocket = None
            
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            
            return False
    
    def send_command(self, command: str, args: Dict[str, Any] = None) -> bool:
        """Send a command to the server
        
        Args:
            command: Command name
            args: Command arguments
            
        Returns:
            True if command was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("command", {
                        "command": command,
                        "args": args or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("command", {
                "command": command,
                "args": args or {}
            }))
        except Exception as e:
            self.logger.error(f"Error sending command: {e}")
            return False
        finally:
            loop.close()
    
    def send_notification(self, notification_type: str, data: Dict[str, Any] = None) -> bool:
        """Send a notification to the server
        
        Args:
            notification_type: Notification type
            data: Notification data
            
        Returns:
            True if notification was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("notification", {
                        "type": notification_type,
                        "data": data or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("notification", {
                "type": notification_type,
                "data": data or {}
            }))
        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")
            return False
        finally:
            loop.close()
    
    async def _handle_messages(self):
        """Handle incoming messages from the server"""
        if not self.connected or not self.websocket:
            return
        
        try:
            while self.connected and self.running:
                # Wait for message
                message = await self.websocket.recv()
                await self._process_message(message)
        
        except websockets.exceptions.ConnectionClosed:
            self.logger.info("Connection closed by server")
        except Exception as e:
            self.logger.error(f"Error handling messages: {e}")
        finally:
            # Mark as disconnected
            self.connected = False
            self.websocket = None
            
            # Call callback if registered
            if self.on_disconnected:
                self.on_disconnected()
    
    async def _process_message(self, message: str):
        """Process a message from the server
        
        Args:
            message: Message string
        """
        try:
            data = json.loads(message)
            
            # Decrypt message if encryption is enabled
            if self.encryption and "encrypted" in data and data["encrypted"]:
                encrypted_data = data.get("data", "")
                decrypted_data = self.encryption.decrypt(encrypted_data.encode()).decode()
                data = json.loads(decrypted_data)
            
            # Process message based on type
            message_type = data.get("type", "")
            if message_type in self.message_handlers:
                response = await self.message_handlers[message_type](data)
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
            await self.websocket.send(json.dumps(response))
        
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON from server")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
    
    async def send_message(self, message_type: str, data: Dict[str, Any]) -> bool:
        """Send a message to the server
        
        Args:
            message_type: Message type
            data: Message data
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self.connected or not self.websocket:
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            self.logger.debug(f"Queued message of type {message_type} for later sending")
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
            await self.websocket.send(json.dumps(message))
            return True
        
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            # Mark as disconnected on error
            self.connected = False
            self.websocket = None
            
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            
            return False
    
    def send_command(self, command: str, args: Dict[str, Any] = None) -> bool:
        """Send a command to the server
        
        Args:
            command: Command name
            args: Command arguments
            
        Returns:
            True if command was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("command", {
                        "command": command,
                        "args": args or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("command", {
                "command": command,
                "args": args or {}
            }))
        except Exception as e:
            self.logger.error(f"Error sending command: {e}")
            return False
        finally:
            loop.close()
    
    def send_notification(self, notification_type: str, data: Dict[str, Any] = None) -> bool:
        """Send a notification to the server
        
        Args:
            notification_type: Notification type
            data: Notification data
            
        Returns:
            True if notification was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("notification", {
                        "type": notification_type,
                        "data": data or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("notification", {
                "type": notification_type,
                "data": data or {}
            }))
        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")
            return False
        finally:
            loop.close()
    
    async def _handle_messages(self):
        """Handle incoming messages from the server"""
        if not self.connected or not self.websocket:
            return
        
        try:
            while self.connected and self.running:
                # Wait for message
                message = await self.websocket.recv()
                await self._process_message(message)
        
        except websockets.exceptions.ConnectionClosed:
            self.logger.info("Connection closed by server")
        except Exception as e:
            self.logger.error(f"Error handling messages: {e}")
        finally:
            # Mark as disconnected
            self.connected = False
            self.websocket = None
            
            # Call callback if registered
            if self.on_disconnected:
                self.on_disconnected()
    
    async def _process_message(self, message: str):
        """Process a message from the server
        
        Args:
            message: Message string
        """
        try:
            data = json.loads(message)
            
            # Decrypt message if encryption is enabled
            if self.encryption and "encrypted" in data and data["encrypted"]:
                encrypted_data = data.get("data", "")
                decrypted_data = self.encryption.decrypt(encrypted_data.encode()).decode()
                data = json.loads(decrypted_data)
            
            # Process message based on type
            message_type = data.get("type", "")
            if message_type in self.message_handlers:
                response = await self.message_handlers[message_type](data)
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
            await self.websocket.send(json.dumps(response))
        
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON from server")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
    
    async def send_message(self, message_type: str, data: Dict[str, Any]) -> bool:
        """Send a message to the server
        
        Args:
            message_type: Message type
            data: Message data
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self.connected or not self.websocket:
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            self.logger.debug(f"Queued message of type {message_type} for later sending")
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
            await self.websocket.send(json.dumps(message))
            return True
        
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            # Mark as disconnected on error
            self.connected = False
            self.websocket = None
            
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            
            return False
    
    def send_command(self, command: str, args: Dict[str, Any] = None) -> bool:
        """Send a command to the server
        
        Args:
            command: Command name
            args: Command arguments
            
        Returns:
            True if command was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("command", {
                        "command": command,
                        "args": args or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("command", {
                "command": command,
                "args": args or {}
            }))
        except Exception as e:
            self.logger.error(f"Error sending command: {e}")
            return False
        finally:
            loop.close()
    
    def send_notification(self, notification_type: str, data: Dict[str, Any] = None) -> bool:
        """Send a notification to the server
        
        Args:
            notification_type: Notification type
            data: Notification data
            
        Returns:
            True if notification was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("notification", {
                        "type": notification_type,
                        "data": data or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("notification", {
                "type": notification_type,
                "data": data or {}
            }))
        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")
            return False
        finally:
            loop.close()
    
    async def _handle_messages(self):
        """Handle incoming messages from the server"""
        if not self.connected or not self.websocket:
            return
        
        try:
            while self.connected and self.running:
                # Wait for message
                message = await self.websocket.recv()
                await self._process_message(message)
        
        except websockets.exceptions.ConnectionClosed:
            self.logger.info("Connection closed by server")
        except Exception as e:
            self.logger.error(f"Error handling messages: {e}")
        finally:
            # Mark as disconnected
            self.connected = False
            self.websocket = None
            
            # Call callback if registered
            if self.on_disconnected:
                self.on_disconnected()
    
    async def _process_message(self, message: str):
        """Process a message from the server
        
        Args:
            message: Message string
        """
        try:
            data = json.loads(message)
            
            # Decrypt message if encryption is enabled
            if self.encryption and "encrypted" in data and data["encrypted"]:
                encrypted_data = data.get("data", "")
                decrypted_data = self.encryption.decrypt(encrypted_data.encode()).decode()
                data = json.loads(decrypted_data)
            
            # Process message based on type
            message_type = data.get("type", "")
            if message_type in self.message_handlers:
                response = await self.message_handlers[message_type](data)
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
            await self.websocket.send(json.dumps(response))
        
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON from server")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
    
    async def send_message(self, message_type: str, data: Dict[str, Any]) -> bool:
        """Send a message to the server
        
        Args:
            message_type: Message type
            data: Message data
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self.connected or not self.websocket:
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            self.logger.debug(f"Queued message of type {message_type} for later sending")
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
            await self.websocket.send(json.dumps(message))
            return True
        
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            # Mark as disconnected on error
            self.connected = False
            self.websocket = None
            
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            
            return False
    
    def send_command(self, command: str, args: Dict[str, Any] = None) -> bool:
        """Send a command to the server
        
        Args:
            command: Command name
            args: Command arguments
            
        Returns:
            True if command was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("command", {
                        "command": command,
                        "args": args or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("command", {
                "command": command,
                "args": args or {}
            }))
        except Exception as e:
            self.logger.error(f"Error sending command: {e}")
            return False
        finally:
            loop.close()
    
    def send_notification(self, notification_type: str, data: Dict[str, Any] = None) -> bool:
        """Send a notification to the server
        
        Args:
            notification_type: Notification type
            data: Notification data
            
        Returns:
            True if notification was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("notification", {
                        "type": notification_type,
                        "data": data or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("notification", {
                "type": notification_type,
                "data": data or {}
            }))
        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")
            return False
        finally:
            loop.close()
    
    async def _handle_messages(self):
        """Handle incoming messages from the server"""
        if not self.connected or not self.websocket:
            return
        
        try:
            while self.connected and self.running:
                # Wait for message
                message = await self.websocket.recv()
                await self._process_message(message)
        
        except websockets.exceptions.ConnectionClosed:
            self.logger.info("Connection closed by server")
        except Exception as e:
            self.logger.error(f"Error handling messages: {e}")
        finally:
            # Mark as disconnected
            self.connected = False
            self.websocket = None
            
            # Call callback if registered
            if self.on_disconnected:
                self.on_disconnected()
    
    async def _process_message(self, message: str):
        """Process a message from the server
        
        Args:
            message: Message string
        """
        try:
            data = json.loads(message)
            
            # Decrypt message if encryption is enabled
            if self.encryption and "encrypted" in data and data["encrypted"]:
                encrypted_data = data.get("data", "")
                decrypted_data = self.encryption.decrypt(encrypted_data.encode()).decode()
                data = json.loads(decrypted_data)
            
            # Process message based on type
            message_type = data.get("type", "")
            if message_type in self.message_handlers:
                response = await self.message_handlers[message_type](data)
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
            await self.websocket.send(json.dumps(response))
        
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON from server")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
    
    async def send_message(self, message_type: str, data: Dict[str, Any]) -> bool:
        """Send a message to the server
        
        Args:
            message_type: Message type
            data: Message data
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self.connected or not self.websocket:
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            self.logger.debug(f"Queued message of type {message_type} for later sending")
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
            await self.websocket.send(json.dumps(message))
            return True
        
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            # Mark as disconnected on error
            self.connected = False
            self.websocket = None
            
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            
            return False
    
    def send_command(self, command: str, args: Dict[str, Any] = None) -> bool:
        """Send a command to the server
        
        Args:
            command: Command name
            args: Command arguments
            
        Returns:
            True if command was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("command", {
                        "command": command,
                        "args": args or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("command", {
                "command": command,
                "args": args or {}
            }))
        except Exception as e:
            self.logger.error(f"Error sending command: {e}")
            return False
        finally:
            loop.close()
    
    def send_notification(self, notification_type: str, data: Dict[str, Any] = None) -> bool:
        """Send a notification to the server
        
        Args:
            notification_type: Notification type
            data: Notification data
            
        Returns:
            True if notification was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("notification", {
                        "type": notification_type,
                        "data": data or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("notification", {
                "type": notification_type,
                "data": data or {}
            }))
        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")
            return False
        finally:
            loop.close()
    
    async def _handle_messages(self):
        """Handle incoming messages from the server"""
        if not self.connected or not self.websocket:
            return
        
        try:
            while self.connected and self.running:
                # Wait for message
                message = await self.websocket.recv()
                await self._process_message(message)
        
        except websockets.exceptions.ConnectionClosed:
            self.logger.info("Connection closed by server")
        except Exception as e:
            self.logger.error(f"Error handling messages: {e}")
        finally:
            # Mark as disconnected
            self.connected = False
            self.websocket = None
            
            # Call callback if registered
            if self.on_disconnected:
                self.on_disconnected()
    
    async def _process_message(self, message: str):
        """Process a message from the server
        
        Args:
            message: Message string
        """
        try:
            data = json.loads(message)
            
            # Decrypt message if encryption is enabled
            if self.encryption and "encrypted" in data and data["encrypted"]:
                encrypted_data = data.get("data", "")
                decrypted_data = self.encryption.decrypt(encrypted_data.encode()).decode()
                data = json.loads(decrypted_data)
            
            # Process message based on type
            message_type = data.get("type", "")
            if message_type in self.message_handlers:
                response = await self.message_handlers[message_type](data)
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
            await self.websocket.send(json.dumps(response))
        
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON from server")
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
    
    async def send_message(self, message_type: str, data: Dict[str, Any]) -> bool:
        """Send a message to the server
        
        Args:
            message_type: Message type
            data: Message data
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self.connected or not self.websocket:
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            self.logger.debug(f"Queued message of type {message_type} for later sending")
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
            await self.websocket.send(json.dumps(message))
            return True
        
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            # Mark as disconnected on error
            self.connected = False
            self.websocket = None
            
            # Queue message for later
            with self.message_queue_lock:
                self.message_queue.append((message_type, data))
            
            return False
    
    def send_command(self, command: str, args: Dict[str, Any] = None) -> bool:
        """Send a command to the server
        
        Args:
            command: Command name
            args: Command arguments
            
        Returns:
            True if command was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("command", {
                        "command": command,
                        "args": args or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("command", {
                "command": command,
                "args": args or {}
            }))
        except Exception as e:
            self.logger.error(f"Error sending command: {e}")
            return False
        finally:
            loop.close()
    
    def send_notification(self, notification_type: str, data: Dict[str, Any] = None) -> bool:
        """Send a notification to the server
        
        Args:
            notification_type: Notification type
            data: Notification data
            
        Returns:
            True if notification was queued or sent, False on error
        """
        # Try to use the main event loop if available
        if hasattr(asyncio, 'get_event_loop_policy') and hasattr(threading, 'current_thread'):
            try:
                current_loop = asyncio.get_event_loop()
                if not current_loop.is_closed():
                    return current_loop.run_until_complete(self.send_message("notification", {
                        "type": notification_type,
                        "data": data or {}
                    }))
            except RuntimeError:
                # No event loop in this thread, create a new one
                pass
        
        # Fallback to creating a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message("notification", {
                "type": notification_type,
                "data": data or {}
            }))