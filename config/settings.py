import os
from pathlib import Path
from typing import Dict, Any
import json
from dotenv import load_dotenv
import yaml

# Load environment variables
load_dotenv()

def get_settings():
    try:
        with open("config/config.yaml", "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        with open("config/config.json", "r") as f:
            return json.load(f)

Settings = get_settings()

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
MODELS_DIR = BASE_DIR / "models"

# Create necessary directories
for directory in [DATA_DIR, LOGS_DIR, MODELS_DIR]:
    directory.mkdir(exist_ok=True)

# Database settings
DATABASE = {
    "default": {
        "engine": "sqlite",
        "name": str(DATA_DIR / "jarvis.db"),
        "user": os.getenv("DB_USER", ""),
        "password": os.getenv("DB_PASSWORD", ""),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
    }
}

# Security settings
SECURITY = {
    "secret_key": os.getenv("SECRET_KEY", "your-secret-key-here"),
    "algorithm": "HS256",
    "access_token_expire_minutes": 30,
    "refresh_token_expire_days": 7,
    "password_hash_algorithm": "pbkdf2_sha256",
    "password_hash_iterations": 100000,
}

# Voice command settings
VOICE = {
    "wake_word": "jarvis",
    "language": "en-US",
    "sample_rate": 16000,
    "chunk_size": 1024,
    "channels": 1,
    "dtype": "int16",
    "whisper_model": "base",
    "voice_id": "en-US-Wavenet-D",
    "speech_rate": 150,
    "volume": 1.0,
}

# Google Services settings
GOOGLE = {
    "credentials_path": str(BASE_DIR / "config" / "google_credentials.json"),
    "scopes": [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/cloud-vision",
        "https://www.googleapis.com/auth/cloud-platform"
    ],
    "project_id": os.getenv("GOOGLE_PROJECT_ID", ""),
    "api_key": os.getenv("GOOGLE_API_KEY", ""),
}

# Device management settings
DEVICE = {
    "host": "0.0.0.0",
    "port": 8765,
    "max_connections": 100,
    "heartbeat_interval": 30,
    "reconnect_attempts": 3,
    "timeout": 60,
}

# Logging settings
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": str(LOGS_DIR / "jarvis.log"),
            "formatter": "verbose",
        },
    },
    "loggers": {
        "": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": True,
        },
    },
}

# API settings
API = {
    "host": "0.0.0.0",
    "port": 8000,
    "debug": os.getenv("DEBUG", "False").lower() == "true",
    "cors_origins": ["*"],
    "rate_limit": "100/minute",
}

# Cache settings
CACHE = {
    "type": "redis",
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": int(os.getenv("REDIS_PORT", 6379)),
    "db": 0,
    "password": os.getenv("REDIS_PASSWORD", ""),
    "ttl": 3600,
}

# Feature flags
FEATURES = {
    "voice_commands": True,
    "google_integration": True,
    "multi_device": True,
    "security": True,
    "database": True,
    "api": True,
}

def get_settings() -> Dict[str, Any]:
    """Get all settings as a dictionary"""
    return {
        "database": DATABASE,
        "security": SECURITY,
        "voice": VOICE,
        "google": GOOGLE,
        "device": DEVICE,
        "logging": LOGGING,
        "api": API,
        "cache": CACHE,
        "features": FEATURES,
    }

def save_settings(settings: Dict[str, Any], filepath: str = None):
    """Save settings to a JSON file"""
    if filepath is None:
        filepath = str(BASE_DIR / "config" / "settings.json")
    
    with open(filepath, 'w') as f:
        json.dump(settings, f, indent=4)

def load_settings(filepath: str = None) -> Dict[str, Any]:
    """Load settings from a JSON file"""
    if filepath is None:
        filepath = str(BASE_DIR / "config" / "settings.json")
    
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return get_settings()

def load_config(path="config/config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)

CONFIG = load_config() 