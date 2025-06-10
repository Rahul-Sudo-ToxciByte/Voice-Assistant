#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Configuration Loader for Jarvis Assistant

This module handles loading and parsing configuration files for the Jarvis assistant.
"""

import os
import logging
import json
from typing import Dict, Any, Optional

# Import for YAML support
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from a file
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Configuration dictionary
    """
    logger = logging.getLogger("jarvis.config")
    
    # Check if file exists
    if not os.path.exists(config_path):
        logger.warning(f"Configuration file not found: {config_path}")
        logger.info("Creating default configuration")
        return create_default_config(config_path)
    
    # Determine file type from extension
    file_ext = os.path.splitext(config_path)[1].lower()
    
    try:
        if file_ext == ".json":
            # Load JSON configuration
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"Loaded JSON configuration from {config_path}")
        
        elif file_ext in [".yaml", ".yml"]:
            # Load YAML configuration
            if not YAML_AVAILABLE:
                logger.error("YAML package not available. Please install with 'pip install pyyaml'")
                raise ImportError("YAML package not available")
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded YAML configuration from {config_path}")
        
        else:
            logger.error(f"Unsupported configuration file format: {file_ext}")
            logger.info("Creating default configuration")
            return create_default_config(config_path)
        
        # Validate configuration
        validate_config(config)
        
        return config
    
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        logger.info("Creating default configuration")
        return create_default_config(config_path)


def create_default_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Create a default configuration
    
    Args:
        config_path: Path to save the default configuration (optional)
        
    Returns:
        Default configuration dictionary
    """
    logger = logging.getLogger("jarvis.config")
    
    # Create default configuration
    default_config = {
        "assistant": {
            "name": "Jarvis",
            "version": "1.0.0",
            "debug_mode": False
        },
        "voice": {
            "stt_engine": "google",
            "tts_engine": "pyttsx3",
            "wake_word": "jarvis",
            "use_wake_word": True,
            "speaking_rate": 175,
            "speaking_volume": 1.0,
            "energy_threshold": 300,
            "pause_threshold": 0.8,
            "dynamic_energy_threshold": True,
            "adjust_for_ambient_noise": True,
            "listen_timeout": 5.0,
            "phrase_time_limit": 10.0
        },
        "nlp": {
            "model_type": "openai",
            "model_name": "gpt-3.5-turbo",
            "temperature": 0.7,
            "max_tokens": 150,
            "system_prompt": (
                "You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), a personal AI assistant. "
                "You have a British accent and personality inspired by the AI assistant from Iron Man. "
                "You are helpful, witty, and slightly sarcastic at times. "
                "You assist with information, tasks, and provide intelligent insights. "
                "You should address the user respectfully but with a touch of familiarity. "
                "When you don't know something, admit it rather than making up information. "
                "Keep responses concise and relevant to the user's needs."
            )
        },
        "memory": {
            "data_dir": "data/memory",
            "use_vector_db": True,
            "max_conversation_history": 1000,
            "max_short_term_memory": 50
        },
        "vision": {
            "enable_camera": False,
            "camera_index": 0,
            "face_recognition": False,
            "object_detection": False,
            "detection_model": "yolov8n.pt",
            "detection_confidence": 0.5
        },
        "knowledge": {
            "data_dir": "data/knowledge",
            "use_web_search": True,
            "search_engine": "google",
            "max_search_results": 5
        },
        "home_control": {
            "enable": False,
            "mqtt_broker": "localhost",
            "mqtt_port": 1883,
            "mqtt_username": "",
            "mqtt_password": "",
            "devices": []
        },
        "web_services": {
            "weather_api_key": "",
            "news_api_key": "",
            "enable_email": False,
            "email_address": "",
            "email_password": ""
        },
        "ui": {
            "enable_gui": True,
            "theme": "dark",
            "window_width": 800,
            "window_height": 600,
            "font_size": 12,
            "show_system_tray": True
        }
    }
    
    # Save default configuration if path provided
    if config_path:
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            # Determine file type from extension
            file_ext = os.path.splitext(config_path)[1].lower()
            
            if file_ext == ".json":
                # Save as JSON
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved default configuration to {config_path}")
            
            elif file_ext in [".yaml", ".yml"]:
                # Save as YAML
                if not YAML_AVAILABLE:
                    logger.error("YAML package not available. Saving as JSON instead.")
                    json_path = os.path.splitext(config_path)[0] + ".json"
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(default_config, f, indent=2, ensure_ascii=False)
                    logger.info(f"Saved default configuration to {json_path}")
                else:
                    with open(config_path, 'w', encoding='utf-8') as f:
                        yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)
                    logger.info(f"Saved default configuration to {config_path}")
            
            else:
                # Default to JSON for unsupported extensions
                logger.warning(f"Unsupported file extension: {file_ext}. Saving as JSON.")
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved default configuration to {config_path}")
        
        except Exception as e:
            logger.error(f"Error saving default configuration: {e}")
    
    return default_config


def validate_config(config: Dict[str, Any]) -> bool:
    """Validate the configuration
    
    Args:
        config: Configuration dictionary to validate
        
    Returns:
        True if valid, False otherwise
    """
    logger = logging.getLogger("jarvis.config")
    
    # Check for required sections
    required_sections = ["assistant", "voice", "nlp", "memory"]
    for section in required_sections:
        if section not in config:
            logger.warning(f"Missing required configuration section: {section}")
            config[section] = create_default_config()[section]
    
    # Validate specific settings
    # This is a basic validation, can be expanded as needed
    
    # Check voice settings
    if "voice" in config:
        voice_config = config["voice"]
        
        # Validate STT engine
        valid_stt_engines = ["google", "whisper"]
        if "stt_engine" in voice_config and voice_config["stt_engine"] not in valid_stt_engines:
            logger.warning(f"Invalid STT engine: {voice_config['stt_engine']}. Using default.")
            voice_config["stt_engine"] = "google"
        
        # Validate TTS engine
        valid_tts_engines = ["pyttsx3"]
        if "tts_engine" in voice_config and voice_config["tts_engine"] not in valid_tts_engines:
            logger.warning(f"Invalid TTS engine: {voice_config['tts_engine']}. Using default.")
            voice_config["tts_engine"] = "pyttsx3"
    
    # Check NLP settings
    if "nlp" in config:
        nlp_config = config["nlp"]
        
        # Validate model type
        valid_model_types = ["openai", "local"]
        if "model_type" in nlp_config and nlp_config["model_type"] not in valid_model_types:
            logger.warning(f"Invalid model type: {nlp_config['model_type']}. Using default.")
            nlp_config["model_type"] = "openai"
        
        # Check for API key if using OpenAI
        if nlp_config.get("model_type") == "openai" and not (nlp_config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")):
            logger.warning("OpenAI API key not found. Please set in config or as environment variable.")
    
    return True


def update_config(config_path: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update configuration with new values
    
    Args:
        config_path: Path to the configuration file
        updates: Dictionary of updates to apply
        
    Returns:
        Updated configuration dictionary
    """
    logger = logging.getLogger("jarvis.config")
    
    # Load current configuration
    current_config = load_config(config_path)
    
    # Apply updates (recursive update)
    updated_config = deep_update(current_config, updates)
    
    # Save updated configuration
    try:
        # Determine file type from extension
        file_ext = os.path.splitext(config_path)[1].lower()
        
        if file_ext == ".json":
            # Save as JSON
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(updated_config, f, indent=2, ensure_ascii=False)
            logger.info(f"Updated configuration saved to {config_path}")
        
        elif file_ext in [".yaml", ".yml"]:
            # Save as YAML
            if not YAML_AVAILABLE:
                logger.error("YAML package not available. Saving as JSON instead.")
                json_path = os.path.splitext(config_path)[0] + ".json"
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(updated_config, f, indent=2, ensure_ascii=False)
                logger.info(f"Updated configuration saved to {json_path}")
            else:
                with open(config_path, 'w', encoding='utf-8') as f:
                    yaml.dump(updated_config, f, default_flow_style=False, sort_keys=False)
                logger.info(f"Updated configuration saved to {config_path}")
        
        else:
            # Default to JSON for unsupported extensions
            logger.warning(f"Unsupported file extension: {file_ext}. Saving as JSON.")
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(updated_config, f, indent=2, ensure_ascii=False)
            logger.info(f"Updated configuration saved to {config_path}")
    
    except Exception as e:
        logger.error(f"Error saving updated configuration: {e}")
    
    return updated_config


def deep_update(original: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively update a dictionary
    
    Args:
        original: Original dictionary
        updates: Dictionary of updates
        
    Returns:
        Updated dictionary
    """
    for key, value in updates.items():
        if key in original and isinstance(original[key], dict) and isinstance(value, dict):
            original[key] = deep_update(original[key], value)
        else:
            original[key] = value
    
    return original