import pytest
import pytest_asyncio
import asyncio
import json
from datetime import datetime, UTC
from modules.device_manager import DeviceManager, DeviceStatus, DeviceInfo

@pytest_asyncio.fixture
async def device_manager():
    manager = DeviceManager()
    await manager.start_server(host="127.0.0.1", port=8765)
    try:
        yield manager
    finally:
        if manager.server:
            manager.server.close()
            await manager.server.wait_closed()

@pytest.mark.asyncio
async def test_device_registration(device_manager):
    # Create a test device
    device_id = "test_device_1"
    device_info = DeviceInfo(
        id=device_id,
        name="Test Device",
        type="test",
        status=DeviceStatus.ONLINE,
        capabilities={"test": True},
        last_seen=datetime.now(UTC),
        ip_address="127.0.0.1",
        port=12345
    )
    
    # Register the device
    device_manager.devices[device_id] = device_info
    
    # Verify device registration
    assert device_id in device_manager.devices
    assert device_manager.devices[device_id].name == "Test Device"
    assert device_manager.devices[device_id].type == "test"
    assert device_manager.devices[device_id].status == DeviceStatus.ONLINE

@pytest.mark.asyncio
async def test_device_disconnection(device_manager):
    # Create and register a test device
    device_id = "test_device_2"
    device_info = DeviceInfo(
        id=device_id,
        name="Test Device 2",
        type="test",
        status=DeviceStatus.ONLINE,
        capabilities={"test": True},
        last_seen=datetime.now(UTC),
        ip_address="127.0.0.1",
        port=12346
    )
    
    device_manager.devices[device_id] = device_info
    # Add a dummy websocket connection for the device
    class DummyWebSocket:
        async def send(self, message):
            pass
    device_manager.connections[device_id] = DummyWebSocket()
    
    # Simulate disconnection
    await device_manager._handle_device_disconnection(device_id)
    
    # Verify device is marked as offline
    assert device_id in device_manager.devices
    assert device_manager.devices[device_id].status == DeviceStatus.OFFLINE

@pytest.mark.asyncio
async def test_get_device_info(device_manager):
    # Create and register a test device
    device_id = "test_device_3"
    device_info = DeviceInfo(
        id=device_id,
        name="Test Device 3",
        type="test",
        status=DeviceStatus.ONLINE,
        capabilities={"test": True},
        last_seen=datetime.now(UTC),
        ip_address="127.0.0.1",
        port=12347
    )
    
    device_manager.devices[device_id] = device_info
    
    # Test get_device_info
    retrieved_info = device_manager.get_device_info(device_id)
    assert retrieved_info is not None
    assert retrieved_info.name == "Test Device 3"
    assert retrieved_info.type == "test"
    
    # Test get_device_info with non-existent device
    assert device_manager.get_device_info("non_existent") is None

@pytest.mark.asyncio
async def test_get_devices_by_type(device_manager):
    # Create and register test devices of different types
    devices = [
        DeviceInfo(
            id=f"test_device_{i}",
            name=f"Test Device {i}",
            type="type1" if i % 2 == 0 else "type2",
            status=DeviceStatus.ONLINE,
            capabilities={"test": True},
            last_seen=datetime.now(UTC),
            ip_address="127.0.0.1",
            port=12348 + i
        )
        for i in range(4)
    ]
    
    for device in devices:
        device_manager.devices[device.id] = device
    
    # Test get_devices_by_type
    type1_devices = device_manager.get_devices_by_type("type1")
    assert len(type1_devices) == 2
    assert all(device.type == "type1" for device in type1_devices)
    
    type2_devices = device_manager.get_devices_by_type("type2")
    assert len(type2_devices) == 2
    assert all(device.type == "type2" for device in type2_devices)
    
    # Test get_devices_by_type with non-existent type
    assert len(device_manager.get_devices_by_type("non_existent")) == 0 