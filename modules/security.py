from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os
import jwt
from datetime import datetime, timedelta
import hashlib
from core.logger import get_logger
import hmac

class SecurityManager:
    def __init__(self, secret_key=None):
        self.secret_key = secret_key or os.urandom(32)
        self.fernet = self._initialize_encryption()
        self.logger = get_logger("security")

    def _initialize_encryption(self):
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'jarvis_salt',
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.secret_key))
        return Fernet(key)

    def encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data"""
        try:
            return self.fernet.encrypt(data.encode()).decode()
        except Exception as e:
            self.logger.error(f"Encryption error: {str(e)}")
            raise

    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        try:
            return self.fernet.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            self.logger.error(f"Decryption error: {str(e)}")
            raise

    def generate_token(self, user_id: str, expires_delta: timedelta = timedelta(hours=24)) -> str:
        """Generate JWT token for authentication"""
        expire = datetime.utcnow() + expires_delta
        to_encode = {"exp": expire, "sub": user_id}
        return jwt.encode(to_encode, self.secret_key, algorithm="HS256")

    def verify_token(self, token: str) -> dict:
        """Verify JWT token"""
        try:
            return jwt.decode(token, self.secret_key, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise Exception("Token has expired")
        except jwt.JWTError:
            raise Exception("Invalid token")

    def hash_password(self, password: str) -> str:
        """Hash password using SHA-256"""
        salt = os.urandom(32)
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000
        )
        return base64.b64encode(salt + key).decode('utf-8')

    def verify_password(self, stored_password: str, provided_password: str) -> bool:
        """Verify password against stored hash"""
        try:
            stored = base64.b64decode(stored_password)
            salt = stored[:32]
            stored_key = stored[32:]
            key = hashlib.pbkdf2_hmac(
                'sha256',
                provided_password.encode('utf-8'),
                salt,
                100000
            )
            return stored_key == key
        except Exception as e:
            self.logger.error(f"Password verification error: {str(e)}")
            return False

    def secure_communication(self, data: dict) -> dict:
        """Add security headers and encrypt sensitive data"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "signature": self._generate_signature(data),
            "encrypted_data": self.encrypt_data(str(data))
        }

    def _generate_signature(self, data: dict) -> str:
        """Generate HMAC signature for data integrity"""
        message = str(data).encode()
        signature = hmac.new(
            self.secret_key,
            message,
            hashlib.sha256
        ).hexdigest()
        return signature 