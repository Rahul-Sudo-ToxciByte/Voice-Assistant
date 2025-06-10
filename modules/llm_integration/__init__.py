#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LLM Integration Module for Jarvis Assistant

This module provides integration with various Large Language Models (LLMs) including:
- OpenAI's GPT models
- Anthropic's Claude models
- Local LLMs via Ollama
- Hugging Face models

It handles API communication, prompt management, and response processing to enable
advanced AI capabilities for the Jarvis assistant.
"""

import os
import json
import logging
import threading
import time
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime
import requests

# Try to import specific LLM libraries
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from transformers import pipeline
    HUGGINGFACE_AVAILABLE = True
except ImportError:
    HUGGINGFACE_AVAILABLE = False


class LLMManager:
    """Manager for LLM integration"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the LLM manager
        
        Args:
            config: Configuration dictionary
        """
        self.logger = logging.getLogger("jarvis.llm_integration")
        self.config = config
        
        # Configuration
        self.default_provider = config.get("default_provider", "openai")
        self.providers_config = config.get("providers", {})
        
        # Initialize providers
        self.providers = {}
        self._initialize_providers()
        
        # Prompt templates
        self.prompt_templates_dir = os.path.join(
            config.get("data_dir", "data"),
            "llm_integration",
            "prompt_templates"
        )
        os.makedirs(self.prompt_templates_dir, exist_ok=True)
        self.prompt_templates = self._load_prompt_templates()
        
        # Conversation history
        self.conversation_history = {}
        self.history_lock = threading.RLock()
        
        self.logger.info(f"LLM manager initialized with providers: {', '.join(self.providers.keys())}")
    
    def _initialize_providers(self):
        """Initialize LLM providers"""
        # Initialize OpenAI
        if "openai" in self.providers_config and OPENAI_AVAILABLE:
            try:
                openai_config = self.providers_config["openai"]
                openai.api_key = openai_config.get("api_key", os.environ.get("OPENAI_API_KEY", ""))
                
                if openai.api_key:
                    self.providers["openai"] = OpenAIProvider(openai_config)
                    self.logger.info("Initialized OpenAI provider")
                else:
                    self.logger.warning("OpenAI API key not found")
            except Exception as e:
                self.logger.error(f"Error initializing OpenAI provider: {e}")
        
        # Initialize Anthropic
        if "anthropic" in self.providers_config and ANTHROPIC_AVAILABLE:
            try:
                anthropic_config = self.providers_config["anthropic"]
                api_key = anthropic_config.get("api_key", os.environ.get("ANTHROPIC_API_KEY", ""))
                
                if api_key:
                    self.providers["anthropic"] = AnthropicProvider(anthropic_config)
                    self.logger.info("Initialized Anthropic provider")
                else:
                    self.logger.warning("Anthropic API key not found")
            except Exception as e:
                self.logger.error(f"Error initializing Anthropic provider: {e}")
        
        # Initialize Ollama
        if "ollama" in self.providers_config:
            try:
                ollama_config = self.providers_config["ollama"]
                self.providers["ollama"] = OllamaProvider(ollama_config)
                self.logger.info("Initialized Ollama provider")
            except Exception as e:
                self.logger.error(f"Error initializing Ollama provider: {e}")
        
        # Initialize Hugging Face
        if "huggingface" in self.providers_config and HUGGINGFACE_AVAILABLE:
            try:
                huggingface_config = self.providers_config["huggingface"]
                self.providers["huggingface"] = HuggingFaceProvider(huggingface_config)
                self.logger.info("Initialized Hugging Face provider")
            except Exception as e:
                self.logger.error(f"Error initializing Hugging Face provider: {e}")
        
        # Set default provider
        if self.default_provider not in self.providers:
            if len(self.providers) > 0:
                self.default_provider = list(self.providers.keys())[0]
                self.logger.warning(f"Default provider not available, using {self.default_provider} instead")
            else:
                self.logger.error("No LLM providers available")
    
    def _load_prompt_templates(self) -> Dict[str, str]:
        """Load prompt templates from files
        
        Returns:
            Dictionary of prompt templates
        """
        templates = {}
        
        try:
            # Create default templates if they don't exist
            default_templates = {
                "general_query": "You are Jarvis, an AI assistant. Answer the following question:\n\n{query}\n\nProvide a helpful and accurate response.",
                "summarize": "Summarize the following text in a concise manner:\n\n{text}\n\nSummary:",
                "code_generation": "Write code to solve the following problem:\n\n{problem}\n\nProvide the solution in {language}.",
                "creative_writing": "Write a {type} about {topic} in the style of {style}.",
                "system_command": "You are Jarvis, an AI assistant with system access. Execute the following command and explain the result:\n\n{command}"
            }
            
            for name, template in default_templates.items():
                template_path = os.path.join(self.prompt_templates_dir, f"{name}.txt")
                if not os.path.exists(template_path):
                    with open(template_path, "w") as f:
                        f.write(template)
            
            # Load all templates
            for filename in os.listdir(self.prompt_templates_dir):
                if filename.endswith(".txt"):
                    template_name = os.path.splitext(filename)[0]
                    template_path = os.path.join(self.prompt_templates_dir, filename)
                    
                    with open(template_path, "r") as f:
                        templates[template_name] = f.read()
        
        except Exception as e:
            self.logger.error(f"Error loading prompt templates: {e}")
        
        return templates
    
    def get_provider(self, provider_name: str = None) -> Optional[Any]:
        """Get an LLM provider
        
        Args:
            provider_name: Name of the provider (uses default if None)
            
        Returns:
            Provider instance or None if not available
        """
        if not provider_name:
            provider_name = self.default_provider
        
        if provider_name not in self.providers:
            self.logger.warning(f"Provider {provider_name} not available")
            return None
        
        return self.providers[provider_name]
    
    def get_available_providers(self) -> List[str]:
        """Get a list of available providers
        
        Returns:
            List of provider names
        """
        return list(self.providers.keys())
    
    def get_prompt_template(self, template_name: str) -> Optional[str]:
        """Get a prompt template
        
        Args:
            template_name: Name of the template
            
        Returns:
            Template string or None if not found
        """
        return self.prompt_templates.get(template_name)
    
    def format_prompt(self, template_name: str, **kwargs) -> Optional[str]:
        """Format a prompt template with variables
        
        Args:
            template_name: Name of the template
            **kwargs: Variables to format the template with
            
        Returns:
            Formatted prompt string or None if template not found
        """
        template = self.get_prompt_template(template_name)
        if not template:
            return None
        
        try:
            return template.format(**kwargs)
        except KeyError as e:
            self.logger.error(f"Missing variable in prompt template: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error formatting prompt template: {e}")
            return None
    
    def generate_response(self, prompt: str, provider_name: str = None, 
                          conversation_id: str = None, **kwargs) -> Optional[str]:
        """Generate a response from an LLM
        
        Args:
            prompt: Prompt string
            provider_name: Name of the provider (uses default if None)
            conversation_id: ID for conversation history
            **kwargs: Additional parameters for the provider
            
        Returns:
            Response string or None if generation failed
        """
        provider = self.get_provider(provider_name)
        if not provider:
            return None
        
        # Add to conversation history if conversation_id is provided
        if conversation_id:
            with self.history_lock:
                if conversation_id not in self.conversation_history:
                    self.conversation_history[conversation_id] = []
                
                self.conversation_history[conversation_id].append({"role": "user", "content": prompt})
                
                # Use conversation history for context
                kwargs["conversation_history"] = self.conversation_history[conversation_id]
        
        # Generate response
        response = provider.generate(prompt, **kwargs)
        
        # Add response to conversation history
        if conversation_id and response:
            with self.history_lock:
                self.conversation_history[conversation_id].append({"role": "assistant", "content": response})
        
        return response
    
    def clear_conversation_history(self, conversation_id: str) -> bool:
        """Clear conversation history for a specific ID
        
        Args:
            conversation_id: ID of the conversation to clear
            
        Returns:
            True if history was cleared, False if ID not found
        """
        with self.history_lock:
            if conversation_id in self.conversation_history:
                self.conversation_history[conversation_id] = []
                return True
            return False


class OpenAIProvider:
    """Provider for OpenAI's GPT models"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the OpenAI provider
        
        Args:
            config: Configuration dictionary
        """
        self.logger = logging.getLogger("jarvis.llm_integration.openai")
        self.config = config
        
        # Configuration
        self.api_key = config.get("api_key", os.environ.get("OPENAI_API_KEY", ""))
        self.default_model = config.get("default_model", "gpt-3.5-turbo")
        self.default_temperature = config.get("temperature", 0.7)
        self.default_max_tokens = config.get("max_tokens", 1000)
        
        # Set API key
        openai.api_key = self.api_key
        
        self.logger.info(f"OpenAI provider initialized with model: {self.default_model}")
    
    def generate(self, prompt: str, **kwargs) -> Optional[str]:
        """Generate a response using OpenAI
        
        Args:
            prompt: Prompt string
            **kwargs: Additional parameters
            
        Returns:
            Response string or None if generation failed
        """
        try:
            # Get parameters
            model = kwargs.get("model", self.default_model)
            temperature = kwargs.get("temperature", self.default_temperature)
            max_tokens = kwargs.get("max_tokens", self.default_max_tokens)
            conversation_history = kwargs.get("conversation_history", [])
            
            # Prepare messages
            if conversation_history:
                messages = conversation_history.copy()
                # If the last message is not the current prompt, add it
                if not (messages and messages[-1]["role"] == "user" and messages[-1]["content"] == prompt):
                    messages.append({"role": "user", "content": prompt})
            else:
                messages = [{"role": "user", "content": prompt}]
            
            # Add system message if provided
            system_message = kwargs.get("system_message")
            if system_message:
                messages.insert(0, {"role": "system", "content": system_message})
            
            # Generate response
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Extract response text
            response_text = response.choices[0].message.content.strip()
            
            return response_text
        
        except Exception as e:
            self.logger.error(f"Error generating response with OpenAI: {e}")
            return None


class AnthropicProvider:
    """Provider for Anthropic's Claude models"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the Anthropic provider
        
        Args:
            config: Configuration dictionary
        """
        self.logger = logging.getLogger("jarvis.llm_integration.anthropic")
        self.config = config
        
        # Configuration
        self.api_key = config.get("api_key", os.environ.get("ANTHROPIC_API_KEY", ""))
        self.default_model = config.get("default_model", "claude-2")
        self.default_temperature = config.get("temperature", 0.7)
        self.default_max_tokens = config.get("max_tokens", 1000)
        
        # Initialize client
        self.client = anthropic.Anthropic(api_key=self.api_key)
        
        self.logger.info(f"Anthropic provider initialized with model: {self.default_model}")
    
    def generate(self, prompt: str, **kwargs) -> Optional[str]:
        """Generate a response using Anthropic
        
        Args:
            prompt: Prompt string
            **kwargs: Additional parameters
            
        Returns:
            Response string or None if generation failed
        """
        try:
            # Get parameters
            model = kwargs.get("model", self.default_model)
            temperature = kwargs.get("temperature", self.default_temperature)
            max_tokens = kwargs.get("max_tokens", self.default_max_tokens)
            conversation_history = kwargs.get("conversation_history", [])
            
            # Prepare messages
            if conversation_history:
                messages = []
                for msg in conversation_history:
                    role = "user" if msg["role"] == "user" else "assistant"
                    messages.append({"role": role, "content": msg["content"]})
                
                # If the last message is not the current prompt, add it
                if not (messages and messages[-1]["role"] == "user" and messages[-1]["content"] == prompt):
                    messages.append({"role": "user", "content": prompt})
            else:
                messages = [{"role": "user", "content": prompt}]
            
            # Add system message if provided
            system_message = kwargs.get("system_message", "")
            
            # Generate response
            response = self.client.messages.create(
                model=model,
                messages=messages,
                system=system_message,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Extract response text
            response_text = response.content[0].text
            
            return response_text
        
        except Exception as e:
            self.logger.error(f"Error generating response with Anthropic: {e}")
            return None


class OllamaProvider:
    """Provider for local LLMs via Ollama"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the Ollama provider
        
        Args:
            config: Configuration dictionary
        """
        self.logger = logging.getLogger("jarvis.llm_integration.ollama")
        self.config = config
        
        # Configuration
        self.api_url = config.get("api_url", "http://localhost:11434/api")
        self.default_model = config.get("default_model", "llama2")
        self.default_temperature = config.get("temperature", 0.7)
        self.default_max_tokens = config.get("max_tokens", 1000)
        
        self.logger.info(f"Ollama provider initialized with model: {self.default_model}")
    
    def generate(self, prompt: str, **kwargs) -> Optional[str]:
        """Generate a response using Ollama
        
        Args:
            prompt: Prompt string
            **kwargs: Additional parameters
            
        Returns:
            Response string or None if generation failed
        """
        try:
            # Get parameters
            model = kwargs.get("model", self.default_model)
            temperature = kwargs.get("temperature", self.default_temperature)
            max_tokens = kwargs.get("max_tokens", self.default_max_tokens)
            conversation_history = kwargs.get("conversation_history", [])
            
            # Prepare prompt with conversation history
            if conversation_history:
                full_prompt = ""
                for msg in conversation_history:
                    role_prefix = "User: " if msg["role"] == "user" else "Assistant: "
                    full_prompt += f"{role_prefix}{msg['content']}\n\n"
                
                # Add current prompt if not already included
                if not (conversation_history and 
                        conversation_history[-1]["role"] == "user" and 
                        conversation_history[-1]["content"] == prompt):
                    full_prompt += f"User: {prompt}\n\nAssistant: "
            else:
                full_prompt = f"User: {prompt}\n\nAssistant: "
            
            # Add system message if provided
            system_message = kwargs.get("system_message")
            if system_message:
                full_prompt = f"System: {system_message}\n\n{full_prompt}"
            
            # Generate response
            response = requests.post(
                f"{self.api_url}/generate",
                json={
                    "model": model,
                    "prompt": full_prompt,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": False
                }
            )
            
            if response.status_code != 200:
                self.logger.error(f"Error from Ollama API: {response.text}")
                return None
            
            # Extract response text
            response_data = response.json()
            response_text = response_data.get("response", "").strip()
            
            return response_text
        
        except Exception as e:
            self.logger.error(f"Error generating response with Ollama: {e}")
            return None


class HuggingFaceProvider:
    """Provider for Hugging Face models"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the Hugging Face provider
        
        Args:
            config: Configuration dictionary
        """
        self.logger = logging.getLogger("jarvis.llm_integration.huggingface")
        self.config = config
        
        # Configuration
        self.api_key = config.get("api_key", os.environ.get("HUGGINGFACE_API_KEY", ""))
        self.default_model = config.get("default_model", "gpt2")
        self.use_api = config.get("use_api", True)
        self.api_url = config.get("api_url", "https://api-inference.huggingface.co/models/")
        
        # Initialize pipeline if not using API
        self.pipeline = None
        if not self.use_api and HUGGINGFACE_AVAILABLE:
            try:
                self.pipeline = pipeline(
                    "text-generation",
                    model=self.default_model,
                    device=config.get("device", -1)  # -1 for CPU, 0+ for GPU
                )
            except Exception as e:
                self.logger.error(f"Error initializing Hugging Face pipeline: {e}")
        
        self.logger.info(f"Hugging Face provider initialized with model: {self.default_model}")
    
    def generate(self, prompt: str, **kwargs) -> Optional[str]:
        """Generate a response using Hugging Face
        
        Args:
            prompt: Prompt string
            **kwargs: Additional parameters
            
        Returns:
            Response string or None if generation failed
        """
        try:
            # Get parameters
            model = kwargs.get("model", self.default_model)
            max_length = kwargs.get("max_length", 100)
            temperature = kwargs.get("temperature", 0.7)
            
            # Use API if configured
            if self.use_api:
                headers = {"Authorization": f"Bearer {self.api_key}"}
                payload = {
                    "inputs": prompt,
                    "parameters": {
                        "max_length": max_length,
                        "temperature": temperature,
                        "return_full_text": False
                    }
                }
                
                response = requests.post(
                    f"{self.api_url}{model}",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code != 200:
                    self.logger.error(f"Error from Hugging Face API: {response.text}")
                    return None
                
                # Extract response text
                response_data = response.json()
                if isinstance(response_data, list) and len(response_data) > 0:
                    response_text = response_data[0].get("generated_text", "").strip()
                    # Remove the prompt from the response if it's included
                    if response_text.startswith(prompt):
                        response_text = response_text[len(prompt):].strip()
                    return response_text
                return None
            
            # Use local pipeline if available
            elif self.pipeline:
                # Generate response
                result = self.pipeline(
                    prompt,
                    max_length=max_length,
                    temperature=temperature,
                    num_return_sequences=1
                )
                
                # Extract response text
                response_text = result[0]["generated_text"].strip()
                
                # Remove the prompt from the response if it's included
                if response_text.startswith(prompt):
                    response_text = response_text[len(prompt):].strip()
                
                return response_text
            
            else:
                self.logger.error("Hugging Face pipeline not available and API not configured")
                return None
        
        except Exception as e:
            self.logger.error(f"Error generating response with Hugging Face: {e}")
            return None