#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Security Manager for Jarvis Assistant

This module handles security features for the Jarvis assistant, including
authentication, encryption, and access control.
"""

import os
import json
import logging
import time
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime
import hashlib
import base64
import uuid
import re

# Import for encryption
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


class SecurityManager:
    """Security Manager for Jarvis Assistant"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the security manager
        
        Args:
            config: Configuration dictionary for security settings
        """
        self.logger = logging.getLogger("jarvis.security")
        self.config = config
        
        # Set up security configuration
        self.enabled = config.get("enable_security", True)
        self.require_auth = config.get("require_authentication", False)
        self.auth_method = config.get("authentication_method", "face")
        self.allowed_users = config.get("allowed_users", ["default"])
        self.log_access = config.get("log_access", True)
        
        # Set up data paths
        self.data_dir = os.path.join("data", "security")
        self.users_file = os.path.join(self.data_dir, "users.json")
        self.access_log_file = os.path.join(self.data_dir, "access.log")
        
        # Create data directory
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Set up encryption
        self.encryption_enabled = CRYPTO_AVAILABLE
        self.encryption_key = None
        if self.encryption_enabled:
            self._setup_encryption()
        
        # Authentication state
        self.authenticated = not self.require_auth  # Default to authenticated if auth not required
        self.current_user = None
        
        # Load users
        self.users = self._load_users()
        
        # Callbacks
        self.on_auth_success = None
        self.on_auth_failure = None
        
        self.logger.info(f"Security manager initialized (enabled: {self.enabled}, auth required: {self.require_auth})")
    
    def _setup_encryption(self):
        """Set up encryption key"""
        try:
            # Get encryption key from config
            key = self.config.get("encryption_key", "")
            
            # If no key is provided, generate one
            if not key:
                key = self._generate_key()
                self.logger.info("Generated new encryption key")
            
            # Ensure key is valid for Fernet
            if len(key) < 32:  # If key is too short, derive a proper key
                salt = b'jarvis_salt'  # Fixed salt for consistency
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                )
                derived_key = base64.urlsafe_b64encode(kdf.derive(key.encode()))
                self.encryption_key = Fernet(derived_key)
            else:
                # Ensure key is properly formatted for Fernet
                if not key.startswith("Fernet:"):
                    # Assume it's a base64 encoded key
                    self.encryption_key = Fernet(key.encode())
                else:
                    # It's already a Fernet key, strip the prefix
                    self.encryption_key = Fernet(key[8:].encode())
            
            self.logger.info("Encryption initialized successfully")
        
        except Exception as e:
            self.logger.error(f"Error setting up encryption: {e}")
            self.encryption_enabled = False
    
    def _generate_key(self) -> str:
        """Generate a new encryption key
        
        Returns:
            Base64 encoded encryption key
        """
        key = Fernet.generate_key()
        return key.decode()
    
    def _load_users(self) -> Dict[str, Dict[str, Any]]:
        """Load users from file
        
        Returns:
            Dictionary of users
        """
        if not os.path.exists(self.users_file):
            # Create default user if file doesn't exist
            default_user = {
                "default": {
                    "id": "default",
                    "name": "Default User",
                    "password_hash": self._hash_password("jarvis"),  # Default password
                    "face_encoding": None,
                    "voice_print": None,
                    "role": "admin",
                    "created_at": datetime.now().isoformat(),
                    "last_login": None,
                    "settings": {}
                }
            }
            
            # Save default user
            self._save_users(default_user)
            
            return default_user
        
        try:
            with open(self.users_file, 'r', encoding='utf-8') as f:
                users_data = json.load(f)
            
            # Decrypt if encryption is enabled
            if self.encryption_enabled and self.encryption_key and users_data.get("encrypted", False):
                try:
                    encrypted_data = users_data.get("data", "")
                    decrypted_data = self.decrypt(encrypted_data)
                    users_data = json.loads(decrypted_data)
                except Exception as e:
                    self.logger.error(f"Error decrypting users data: {e}")
                    return {}
            
            return users_data
        
        except Exception as e:
            self.logger.error(f"Error loading users: {e}")
            return {}
    
    def _save_users(self, users: Dict[str, Dict[str, Any]]):
        """Save users to file
        
        Args:
            users: Dictionary of users to save
        """
        try:
            # Encrypt if encryption is enabled
            if self.encryption_enabled and self.encryption_key:
                try:
                    users_json = json.dumps(users)
                    encrypted_data = self.encrypt(users_json)
                    data_to_save = {
                        "encrypted": True,
                        "data": encrypted_data
                    }
                except Exception as e:
                    self.logger.error(f"Error encrypting users data: {e}")
                    data_to_save = users
            else:
                data_to_save = users
            
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2)
        
        except Exception as e:
            self.logger.error(f"Error saving users: {e}")
    
    def _hash_password(self, password: str) -> str:
        """Hash a password using SHA-256
        
        Args:
            password: Password to hash
            
        Returns:
            Hashed password
        """
        # Add a fixed salt for simplicity (in a real system, use a per-user salt)
        salt = "jarvis_salt"
        salted_password = password + salt
        
        # Hash the salted password
        hashed = hashlib.sha256(salted_password.encode()).hexdigest()
        
        return hashed
    
    def _log_access(self, user_id: str, action: str, success: bool, details: str = ""):
        """Log an access attempt
        
        Args:
            user_id: ID of the user
            action: Action being performed
            success: Whether the action was successful
            details: Additional details
        """
        if not self.log_access:
            return
        
        try:
            # Create log entry
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                "action": action,
                "success": success,
                "details": details,
                "ip": "127.0.0.1",  # Placeholder for local access
            }
            
            # Convert to string
            log_line = json.dumps(log_entry) + "\n"
            
            # Append to log file
            with open(self.access_log_file, 'a', encoding='utf-8') as f:
                f.write(log_line)
        
        except Exception as e:
            self.logger.error(f"Error logging access: {e}")
    
    def encrypt(self, data: str) -> str:
        """Encrypt data
        
        Args:
            data: Data to encrypt
            
        Returns:
            Encrypted data as a base64 string
        """
        if not self.encryption_enabled or not self.encryption_key:
            return data
        
        try:
            encrypted = self.encryption_key.encrypt(data.encode())
            return encrypted.decode()
        
        except Exception as e:
            self.logger.error(f"Error encrypting data: {e}")
            return data
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt data
        
        Args:
            encrypted_data: Encrypted data as a base64 string
            
        Returns:
            Decrypted data
        """
        if not self.encryption_enabled or not self.encryption_key:
            return encrypted_data
        
        try:
            decrypted = self.encryption_key.decrypt(encrypted_data.encode())
            return decrypted.decode()
        
        except Exception as e:
            self.logger.error(f"Error decrypting data: {e}")
            return encrypted_data
    
    def authenticate(self, method: str = None, credentials: Any = None) -> bool:
        """Authenticate a user
        
        Args:
            method: Authentication method (password, face, voice)
            credentials: Authentication credentials
            
        Returns:
            True if authentication is successful, False otherwise
        """
        if not self.enabled or not self.require_auth:
            self.authenticated = True
            return True
        
        # Use default method if none specified
        if method is None:
            method = self.auth_method
        
        # Authenticate based on method
        success = False
        user_id = "unknown"
        details = ""
        
        if method == "password":
            # Password authentication
            if isinstance(credentials, dict) and "user_id" in credentials and "password" in credentials:
                user_id = credentials["user_id"]
                password = credentials["password"]
                
                # Check if user exists
                if user_id in self.users:
                    user = self.users[user_id]
                    
                    # Check password
                    if user["password_hash"] == self._hash_password(password):
                        success = True
                        self.current_user = user
                        details = "Password authentication successful"
                    else:
                        details = "Invalid password"
                else:
                    details = "User not found"
            else:
                details = "Invalid credentials format for password authentication"
        
        elif method == "face":
            # Face authentication
            if credentials is not None:
                # In a real implementation, this would compare face encodings
                # For now, just check if the user exists
                for user_id, user in self.users.items():
                    if user.get("face_encoding") is not None:
                        # Simulate face recognition
                        # In a real implementation, compare face encodings
                        success = True
                        self.current_user = user
                        details = "Face authentication successful"
                        break
                
                if not success:
                    details = "No matching face found"
            else:
                details = "No face data provided"
        
        elif method == "voice":
            # Voice authentication
            if credentials is not None:
                # In a real implementation, this would compare voice prints
                # For now, just check if the user exists
                for user_id, user in self.users.items():
                    if user.get("voice_print") is not None:
                        # Simulate voice recognition
                        # In a real implementation, compare voice prints
                        success = True
                        self.current_user = user
                        details = "Voice authentication successful"
                        break
                
                if not success:
                    details = "No matching voice found"
            else:
                details = "No voice data provided"
        
        else:
            details = f"Unsupported authentication method: {method}"
        
        # Update authentication state
        self.authenticated = success
        
        # Log access attempt
        self._log_access(user_id, f"authenticate_{method}", success, details)
        
        # Call callbacks
        if success and self.on_auth_success:
            self.on_auth_success(self.current_user)
        elif not success and self.on_auth_failure:
            self.on_auth_failure(user_id, method, details)
        
        # Update last login time if successful
        if success and self.current_user:
            self.users[self.current_user["id"]]["last_login"] = datetime.now().isoformat()
            self._save_users(self.users)
        
        return success
    
    def is_authenticated(self) -> bool:
        """Check if the user is authenticated
        
        Returns:
            True if authenticated, False otherwise
        """
        return not self.require_auth or self.authenticated
    
    def logout(self):
        """Log out the current user"""
        if self.current_user:
            self._log_access(self.current_user["id"], "logout", True)
        
        self.authenticated = False
        self.current_user = None
    
    def add_user(self, user_id: str, name: str, password: str = None, role: str = "user") -> bool:
        """Add a new user
        
        Args:
            user_id: User ID
            name: User name
            password: User password (optional)
            role: User role (default: user)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        # Check if user already exists
        if user_id in self.users:
            self.logger.error(f"User {user_id} already exists")
            return False
        
        # Create new user
        new_user = {
            "id": user_id,
            "name": name,
            "password_hash": self._hash_password(password) if password else None,
            "face_encoding": None,
            "voice_print": None,
            "role": role,
            "created_at": datetime.now().isoformat(),
            "last_login": None,
            "settings": {}
        }
        
        # Add user to users dictionary
        self.users[user_id] = new_user
        
        # Save users
        self._save_users(self.users)
        
        # Log access
        self._log_access("system", "add_user", True, f"Added user {user_id}")
        
        return True
    
    def remove_user(self, user_id: str) -> bool:
        """Remove a user
        
        Args:
            user_id: User ID
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        # Check if user exists
        if user_id not in self.users:
            self.logger.error(f"User {user_id} not found")
            return False
        
        # Remove user
        del self.users[user_id]
        
        # Save users
        self._save_users(self.users)
        
        # Log access
        self._log_access("system", "remove_user", True, f"Removed user {user_id}")
        
        return True
    
    def update_user(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """Update a user
        
        Args:
            user_id: User ID
            updates: Dictionary of updates
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        # Check if user exists
        if user_id not in self.users:
            self.logger.error(f"User {user_id} not found")
            return False
        
        # Get user
        user = self.users[user_id]
        
        # Update user
        for key, value in updates.items():
            if key == "password":
                # Hash password
                user["password_hash"] = self._hash_password(value)
            elif key != "id" and key != "password_hash":  # Don't allow changing ID or direct hash updates
                user[key] = value
        
        # Save users
        self._save_users(self.users)
        
        # Log access
        self._log_access("system", "update_user", True, f"Updated user {user_id}")
        
        return True
    
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a user
        
        Args:
            user_id: User ID
            
        Returns:
            User dictionary, or None if not found
        """
        if not self.enabled:
            return None
        
        # Check if user exists
        if user_id not in self.users:
            return None
        
        # Return a copy of the user (without password hash)
        user = self.users[user_id].copy()
        if "password_hash" in user:
            del user["password_hash"]
        
        return user
    
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """Get the current user
        
        Returns:
            Current user dictionary, or None if not authenticated
        """
        if not self.enabled or not self.authenticated or not self.current_user:
            return None
        
        # Return a copy of the current user (without password hash)
        user = self.current_user.copy()
        if "password_hash" in user:
            del user["password_hash"]
        
        return user
    
    def list_users(self) -> List[Dict[str, Any]]:
        """List all users
        
        Returns:
            List of user dictionaries (without password hashes)
        """
        if not self.enabled:
            return []
        
        # Return a list of users (without password hashes)
        users = []
        for user_id, user in self.users.items():
            user_copy = user.copy()
            if "password_hash" in user_copy:
                del user_copy["password_hash"]
            users.append(user_copy)
        
        return users
    
    def set_face_encoding(self, user_id: str, face_encoding: Any) -> bool:
        """Set face encoding for a user
        
        Args:
            user_id: User ID
            face_encoding: Face encoding data
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        # Check if user exists
        if user_id not in self.users:
            self.logger.error(f"User {user_id} not found")
            return False
        
        # Update face encoding
        self.users[user_id]["face_encoding"] = face_encoding
        
        # Save users
        self._save_users(self.users)
        
        # Log access
        self._log_access("system", "set_face_encoding", True, f"Set face encoding for user {user_id}")
        
        return True
    
    def set_voice_print(self, user_id: str, voice_print: Any) -> bool:
        """Set voice print for a user
        
        Args:
            user_id: User ID
            voice_print: Voice print data
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        # Check if user exists
        if user_id not in self.users:
            self.logger.error(f"User {user_id} not found")
            return False
        
        # Update voice print
        self.users[user_id]["voice_print"] = voice_print
        
        # Save users
        self._save_users(self.users)
        
        # Log access
        self._log_access("system", "set_voice_print", True, f"Set voice print for user {user_id}")
        
        return True
    
    def check_permission(self, permission: str) -> bool:
        """Check if the current user has a permission
        
        Args:
            permission: Permission to check
            
        Returns:
            True if the user has the permission, False otherwise
        """
        if not self.enabled or not self.require_auth:
            return True
        
        if not self.authenticated or not self.current_user:
            return False
        
        # Check role-based permissions
        role = self.current_user.get("role", "user")
        
        # Admin has all permissions
        if role == "admin":
            return True
        
        # Simple permission system based on role
        if role == "user":
            # Users have basic permissions
            basic_permissions = [
                "read", "query", "command", "voice", "chat",
                "weather", "time", "search", "knowledge"
            ]
            return permission in basic_permissions
        
        # Guest has limited permissions
        if role == "guest":
            # Guests have very limited permissions
            guest_permissions = ["read", "query", "chat", "time"]
            return permission in guest_permissions
        
        return False
    
    def register_callbacks(self, on_auth_success: Callable[[Dict[str, Any]], None] = None, on_auth_failure: Callable[[str, str, str], None] = None):
        """Register callback functions
        
        Args:
            on_auth_success: Callback for successful authentication
            on_auth_failure: Callback for failed authentication
        """
        self.on_auth_success = on_auth_success
        self.on_auth_failure = on_auth_failure
    
    def shutdown(self):
        """Shutdown the security manager"""
        # Save any pending changes
        self._save_users(self.users)
        
        self.logger.info("Security manager shut down")