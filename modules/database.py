from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from core.logger import get_logger
from typing import Optional, List, Dict, Any
import json

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    preferences = Column(JSON)
    devices = relationship("Device", back_populates="user")

class Device(Base):
    __tablename__ = 'devices'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    device_name = Column(String(50), nullable=False)
    device_type = Column(String(50), nullable=False)
    last_connected = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default='offline')
    capabilities = Column(JSON)
    user = relationship("User", back_populates="devices")

class Command(Base):
    __tablename__ = 'commands'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    command_text = Column(String(500), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default='pending')
    response = Column(JSON)

class DatabaseManager:
    def __init__(self, connection_string: str):
        self.engine = create_engine(connection_string)
        self.Session = sessionmaker(bind=self.engine)
        self.logger = get_logger("database")
        Base.metadata.create_all(self.engine)

    def add_user(self, username: str, email: str, password_hash: str, preferences: Optional[Dict] = None) -> User:
        """Add a new user to the database"""
        session = self.Session()
        try:
            user = User(
                username=username,
                email=email,
                password_hash=password_hash,
                preferences=preferences or {}
            )
            session.add(user)
            session.commit()
            return user
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error adding user: {str(e)}")
            raise
        finally:
            session.close()

    def register_device(self, user_id: int, device_name: str, device_type: str, capabilities: Optional[Dict] = None) -> Device:
        """Register a new device for a user"""
        session = self.Session()
        try:
            device = Device(
                user_id=user_id,
                device_name=device_name,
                device_type=device_type,
                capabilities=capabilities or {}
            )
            session.add(device)
            session.commit()
            return device
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error registering device: {str(e)}")
            raise
        finally:
            session.close()

    def log_command(self, user_id: int, command_text: str, response: Optional[Dict] = None) -> Command:
        """Log a command execution"""
        session = self.Session()
        try:
            command = Command(
                user_id=user_id,
                command_text=command_text,
                response=response or {}
            )
            session.add(command)
            session.commit()
            return command
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error logging command: {str(e)}")
            raise
        finally:
            session.close()

    def get_user_devices(self, user_id: int) -> List[Device]:
        """Get all devices for a user"""
        session = self.Session()
        try:
            return session.query(Device).filter(Device.user_id == user_id).all()
        finally:
            session.close()

    def update_device_status(self, device_id: int, status: str) -> None:
        """Update device connection status"""
        session = self.Session()
        try:
            device = session.query(Device).filter(Device.id == device_id).first()
            if device:
                device.status = status
                device.last_connected = datetime.utcnow()
                session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error updating device status: {str(e)}")
            raise
        finally:
            session.close()

    def get_user_preferences(self, user_id: int) -> Dict:
        """Get user preferences"""
        session = self.Session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            return user.preferences if user else {}
        finally:
            session.close()

    def update_user_preferences(self, user_id: int, preferences: Dict) -> None:
        """Update user preferences"""
        session = self.Session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            if user:
                user.preferences = preferences
                session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error updating user preferences: {str(e)}")
            raise
        finally:
            session.close() 