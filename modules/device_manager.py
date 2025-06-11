import asyncio
import websockets
import json
from core.logger import get_logger
from typing import Dict, List, Optional, Callable
from datetime import datetime
import uuid
from dataclasses import dataclass
from enum import Enum

class DeviceStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    STANDBY = "standby"

@dataclass
class DeviceInfo:
    id: str
    name: str
    type: str
    status: DeviceStatus
    capabilities: Dict
    last_seen: datetime
    ip_address: str
    port: int

class DeviceManager:
    def __init__(self):
        self.devices: Dict[str, DeviceInfo] = {}
        self.connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.message_handlers: Dict[str, List[Callable]] = {}
        self.logger = get_logger("device_manager")
        self.server = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def start_server(self, host: str = "0.0.0.0", port: int = 8765):
        """Start the WebSocket server for device connections"""
        self.server = await websockets.serve(
            self._handle_device_connection,
            host,
            port
        )
        self.logger.info(f"Device manager server started on {host}:{port}")

    async def _handle_device_connection(self, websocket: websockets.WebSocketServerProtocol, path: str):
        """Handle new device connections"""
        device_id = None
        try:
            # Wait for device registration
            message = await websocket.recv()
            data = json.loads(message)
            
            if data["type"] == "register":
                device_id = data["device_id"]
                device_info = DeviceInfo(
                    id=device_id,
                    name=data["name"],
                    type=data["device_type"],
                    status=DeviceStatus.ONLINE,
                    capabilities=data["capabilities"],
                    last_seen=datetime.utcnow(),
                    ip_address=websocket.remote_address[0],
                    port=websocket.remote_address[1]
                )
                
                self.devices[device_id] = device_info
                self.connections[device_id] = websocket
                
                # Notify all handlers about new device
                await self._notify_handlers("device_connected", device_info)
                
                # Send acknowledgment
                await websocket.send(json.dumps({
                    "type": "registration_ack",
                    "status": "success"
                }))
                
                # Handle device messages
                async for message in websocket:
                    await self._handle_device_message(device_id, message)
                    
        except websockets.exceptions.ConnectionClosed:
            self.logger.info(f"Device {device_id} disconnected")
        except Exception as e:
            self.logger.error(f"Error handling device connection: {str(e)}")
        finally:
            if device_id:
                await self._handle_device_disconnection(device_id)

    async def _handle_device_message(self, device_id: str, message: str):
        """Handle incoming messages from devices"""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type in self.message_handlers:
                for handler in self.message_handlers[message_type]:
                    await handler(device_id, data)
                    
            # Update device status if provided
            if "status" in data:
                self.devices[device_id].status = DeviceStatus(data["status"])
                self.devices[device_id].last_seen = datetime.utcnow()
                
        except json.JSONDecodeError:
            self.logger.error(f"Invalid JSON message from device {device_id}")
        except Exception as e:
            self.logger.error(f"Error handling device message: {str(e)}")

    async def _handle_device_disconnection(self, device_id: str):
        """Handle device disconnection"""
        if device_id in self.devices:
            self.devices[device_id].status = DeviceStatus.OFFLINE
            await self._notify_handlers("device_disconnected", self.devices[device_id])
            del self.connections[device_id]

    async def _notify_handlers(self, event_type: str, data: any):
        """Notify all registered handlers for an event"""
        if event_type in self.message_handlers:
            for handler in self.message_handlers[event_type]:
                try:
                    await handler(data)
                except Exception as e:
                    self.logger.error(f"Error in event handler: {str(e)}")

    def register_handler(self, event_type: str, handler: Callable):
        """Register a new event handler"""
        if event_type not in self.message_handlers:
            self.message_handlers[event_type] = []
        self.message_handlers[event_type].append(handler)

    async def send_command(self, device_id: str, command: str, params: Optional[Dict] = None) -> bool:
        """Send a command to a specific device"""
        if device_id not in self.connections:
            self.logger.error(f"Device {device_id} not connected")
            return False
            
        try:
            message = {
                "type": "command",
                "command": command,
                "params": params or {},
                "timestamp": datetime.utcnow().isoformat()
            }
            await self.connections[device_id].send(json.dumps(message))
            return True
        except Exception as e:
            self.logger.error(f"Error sending command to device {device_id}: {str(e)}")
            return False

    async def broadcast_command(self, command: str, params: Optional[Dict] = None):
        """Broadcast a command to all connected devices"""
        message = {
            "type": "broadcast",
            "command": command,
            "params": params or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        for device_id, connection in self.connections.items():
            try:
                await connection.send(json.dumps(message))
            except Exception as e:
                self.logger.error(f"Error broadcasting to device {device_id}: {str(e)}")

    def get_device_info(self, device_id: str) -> Optional[DeviceInfo]:
        """Get information about a specific device"""
        return self.devices.get(device_id)

    def get_all_devices(self) -> List[DeviceInfo]:
        """Get information about all connected devices"""
        return list(self.devices.values())

    def get_devices_by_type(self, device_type: str) -> List[DeviceInfo]:
        """Get all devices of a specific type"""
        return [device for device in self.devices.values() if device.type == device_type]

    async def sync_device_state(self, device_id: str):
        """Synchronize state with a specific device"""
        if device_id not in self.connections:
            return False
            
        try:
            message = {
                "type": "sync_request",
                "timestamp": datetime.utcnow().isoformat()
            }
            await self.connections[device_id].send(json.dumps(message))
            return True
        except Exception as e:
            self.logger.error(f"Error syncing device {device_id}: {str(e)}")
            return False 