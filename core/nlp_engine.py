#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Natural Language Processing Engine for Jarvis Assistant

This module handles the natural language processing capabilities of the Jarvis assistant,
including understanding user queries and generating responses using language models.
"""

import os
import logging
import json
from typing import Dict, List, Any, Optional, Tuple, Union
import threading
from datetime import datetime

# Import for OpenAI API
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Import for local language models
try:
    from langchain.llms import HuggingFacePipeline
    LOCAL_LLM_AVAILABLE = True
except ImportError:
    LOCAL_LLM_AVAILABLE = False


class NLPEngine:
    """Natural Language Processing Engine for Jarvis Assistant"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the NLP engine
        
        Args:
            config: Configuration dictionary for NLP settings
        """
        self.logger = logging.getLogger("jarvis.nlp")
        self.config = config
        
        # Set up NLP engine configuration
        self.model_type = config.get("model_type", "openai")
        self.model_name = config.get("model_name", "gpt-3.5-turbo")
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 150)
        
        # Thread lock for API calls
        self.api_lock = threading.RLock()
        
        # Initialize the appropriate language model
        self._initialize_language_model()
        
        # Load or create the system prompt
        self.system_prompt = self._load_system_prompt()
        
        self.logger.info(f"NLP Engine initialized with model: {self.model_type}/{self.model_name}")
    
    def _initialize_language_model(self):
        """Initialize the appropriate language model based on configuration"""
        if self.model_type == "openai":
            if not OPENAI_AVAILABLE:
                self.logger.error("OpenAI package not available. Please install with 'pip install openai'")
                raise ImportError("OpenAI package not available")
            
            # Set up OpenAI API
            openai_api_key = self.config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
            if not openai_api_key:
                self.logger.error("OpenAI API key not found. Please set OPENAI_API_KEY environment variable")
                raise ValueError("OpenAI API key not found")
            
            openai.api_key = openai_api_key
            self.logger.info("OpenAI API initialized")
        
        elif self.model_type == "local":
            if not LOCAL_LLM_AVAILABLE:
                self.logger.error("LangChain and HuggingFace packages not available for local LLM")
                raise ImportError("Required packages for local LLM not available")
            
            # Set up local language model
            model_path = self.config.get("model_path")
            if not model_path:
                self.logger.error("Local model path not specified in config")
                raise ValueError("Local model path not specified")
            
            try:
                # Initialize the local model (implementation depends on specific model)
                self.local_model = self._setup_local_model(model_path)
                self.logger.info(f"Local language model initialized from {model_path}")
            except Exception as e:
                self.logger.error(f"Failed to initialize local language model: {e}")
                raise
        
        else:
            self.logger.error(f"Unsupported model type: {self.model_type}")
            raise ValueError(f"Unsupported model type: {self.model_type}")
    
    def _setup_local_model(self, model_path: str):
        """Set up a local language model
        
        Args:
            model_path: Path to the model files
            
        Returns:
            Initialized local language model
        """
        # This is a placeholder implementation
        # The actual implementation depends on the specific model being used
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
            
            tokenizer = AutoTokenizer.from_pretrained(model_path)
            model = AutoModelForCausalLM.from_pretrained(model_path)
            
            pipe = pipeline(
                "text-generation",
                model=model,
                tokenizer=tokenizer,
                max_new_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=0.95,
                repetition_penalty=1.1
            )
            
            local_llm = HuggingFacePipeline(pipeline=pipe)
            return local_llm
        
        except Exception as e:
            self.logger.error(f"Error setting up local model: {e}")
            raise
    
    def _load_system_prompt(self) -> str:
        """Load or create the system prompt for the assistant
        
        Returns:
            The system prompt string
        """
        # Check if a custom system prompt is provided in the config
        if "system_prompt" in self.config:
            return self.config["system_prompt"]
        
        # Default system prompt
        return (
            "You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), a personal AI assistant. "
            "You have a British accent and personality inspired by the AI assistant from Iron Man. "
            "You are helpful, witty, and slightly sarcastic at times. "
            "You assist with information, tasks, and provide intelligent insights. "
            "You should address the user respectfully but with a touch of familiarity. "
            "When you don't know something, admit it rather than making up information. "
            "Keep responses concise and relevant to the user's needs."
        )
    
    def process_query(self, query: str, context: Dict[str, Any] = None) -> str:
        """Process a natural language query and generate a response
        
        Args:
            query: The user's query
            context: Additional context for the query
            
        Returns:
            The generated response
        """
        if not query:
            return "I didn't catch that. Could you please repeat?"
        
        self.logger.debug(f"Processing query: {query}")
        
        # Prepare context for the model
        context = context or {}
        
        # Process based on model type
        if self.model_type == "openai":
            return self._process_with_openai(query, context)
        elif self.model_type == "local":
            return self._process_with_local_model(query, context)
        else:
            self.logger.error(f"Unsupported model type for processing: {self.model_type}")
            return "I'm sorry, but I'm having trouble processing your request right now."
    
    def _process_with_openai(self, query: str, context: Dict[str, Any]) -> str:
        """Process a query using the OpenAI API
        
        Args:
            query: The user's query
            context: Additional context for the query
            
        Returns:
            The generated response
        """
        try:
            with self.api_lock:
                # Prepare messages for the API
                messages = self._prepare_messages(query, context)
                
                # Call the OpenAI API
                response = openai.ChatCompletion.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    top_p=0.95,
                    frequency_penalty=0.5,
                    presence_penalty=0.5,
                )
                
                # Extract the response text
                if response and "choices" in response and len(response["choices"]) > 0:
                    return response["choices"][0]["message"]["content"].strip()
                else:
                    self.logger.warning("Received empty or invalid response from OpenAI API")
                    return "I'm sorry, but I couldn't generate a proper response."
        
        except Exception as e:
            self.logger.error(f"Error processing with OpenAI: {e}")
            return f"I'm sorry, but I encountered an error while processing your request. {str(e)}"
    
    def _process_with_local_model(self, query: str, context: Dict[str, Any]) -> str:
        """Process a query using a local language model
        
        Args:
            query: The user's query
            context: Additional context for the query
            
        Returns:
            The generated response
        """
        try:
            # Prepare prompt for the local model
            prompt = self._prepare_local_prompt(query, context)
            
            # Generate response with the local model
            response = self.local_model(prompt)
            
            # Process and clean up the response
            processed_response = self._process_local_model_response(response, prompt)
            
            return processed_response
        
        except Exception as e:
            self.logger.error(f"Error processing with local model: {e}")
            return f"I'm sorry, but I encountered an error while processing your request. {str(e)}"
    
    def _prepare_messages(self, query: str, context: Dict[str, Any]) -> List[Dict[str, str]]:
        """Prepare messages for the OpenAI API
        
        Args:
            query: The user's query
            context: Additional context for the query
            
        Returns:
            List of message dictionaries for the API
        """
        messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        
        # Add context information if available
        if context:
            # Add recent conversations for context
            if "recent_conversations" in context and context["recent_conversations"]:
                for conv in context["recent_conversations"][-3:]:  # Last 3 conversations
                    messages.append({"role": "user", "content": conv["user_input"]})
                    messages.append({"role": "assistant", "content": conv["assistant_response"]})
            
            # Add relevant memories as context
            if "relevant_memories" in context and context["relevant_memories"]:
                memory_context = "Here is some relevant information that might help with the response:\n"
                for memory in context["relevant_memories"]:
                    memory_context += f"- {memory['text']}\n"
                
                messages.append({"role": "system", "content": memory_context})
            
            # Add user preferences if available
            if "user_preferences" in context and context["user_preferences"]:
                pref_context = "User preferences:\n"
                for key, value in context["user_preferences"].items():
                    pref_context += f"- {key}: {value}\n"
                
                messages.append({"role": "system", "content": pref_context})
        
        # Add the current query
        messages.append({"role": "user", "content": query})
        
        return messages
    
    def _prepare_local_prompt(self, query: str, context: Dict[str, Any]) -> str:
        """Prepare a prompt for a local language model
        
        Args:
            query: The user's query
            context: Additional context for the query
            
        Returns:
            Formatted prompt string for the local model
        """
        prompt = f"{self.system_prompt}\n\n"
        
        # Add context information if available
        if context:
            # Add recent conversations for context
            if "recent_conversations" in context and context["recent_conversations"]:
                prompt += "Recent conversations:\n"
                for conv in context["recent_conversations"][-3:]:  # Last 3 conversations
                    prompt += f"User: {conv['user_input']}\n"
                    prompt += f"Assistant: {conv['assistant_response']}\n"
                prompt += "\n"
            
            # Add relevant memories as context
            if "relevant_memories" in context and context["relevant_memories"]:
                prompt += "Relevant information:\n"
                for memory in context["relevant_memories"]:
                    prompt += f"- {memory['text']}\n"
                prompt += "\n"
            
            # Add user preferences if available
            if "user_preferences" in context and context["user_preferences"]:
                prompt += "User preferences:\n"
                for key, value in context["user_preferences"].items():
                    prompt += f"- {key}: {value}\n"
                prompt += "\n"
        
        # Add the current query
        prompt += f"User: {query}\n"
        prompt += "Assistant: "
        
        return prompt
    
    def _process_local_model_response(self, response: str, prompt: str) -> str:
        """Process and clean up the response from a local language model
        
        Args:
            response: The raw response from the model
            prompt: The prompt that was sent to the model
            
        Returns:
            Cleaned up response string
        """
        # Remove the prompt from the beginning of the response if present
        if response.startswith(prompt):
            response = response[len(prompt):]
        
        # Extract just the assistant's response
        if "\nUser:" in response:
            response = response.split("\nUser:")[0]
        
        # Clean up any remaining artifacts
        response = response.strip()
        
        return response
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze the sentiment of a text
        
        Args:
            text: The text to analyze
            
        Returns:
            Dictionary with sentiment analysis results
        """
        # This is a placeholder implementation
        # In a real implementation, this would use a sentiment analysis model
        
        # For now, just use a simple keyword-based approach
        positive_words = ["good", "great", "excellent", "happy", "love", "like", "thanks", "thank", "appreciate"]
        negative_words = ["bad", "terrible", "awful", "sad", "hate", "dislike", "sorry", "problem", "issue", "wrong"]
        
        text_lower = text.lower()
        
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        # Calculate sentiment score (-1 to 1)
        total = positive_count + negative_count
        if total == 0:
            sentiment_score = 0  # Neutral
        else:
            sentiment_score = (positive_count - negative_count) / total
        
        # Determine sentiment category
        if sentiment_score > 0.25:
            sentiment = "positive"
        elif sentiment_score < -0.25:
            sentiment = "negative"
        else:
            sentiment = "neutral"
        
        return {
            "sentiment": sentiment,
            "score": sentiment_score,
            "positive_count": positive_count,
            "negative_count": negative_count
        }
    
    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities from text
        
        Args:
            text: The text to analyze
            
        Returns:
            List of extracted entities with their types
        """
        # This is a placeholder implementation
        # In a real implementation, this would use an NER model
        
        entities = []
        
        # Simple rule-based entity extraction for demonstration
        # In a real implementation, use a proper NER model or API
        
        # Check for time-related entities
        time_indicators = ["today", "tomorrow", "yesterday", "next week", "last week", 
                          "morning", "afternoon", "evening", "night"]
        
        for indicator in time_indicators:
            if indicator in text.lower():
                entities.append({
                    "text": indicator,
                    "type": "time",
                    "start": text.lower().find(indicator),
                    "end": text.lower().find(indicator) + len(indicator)
                })
        
        return entities
    
    def detect_intent(self, text: str) -> Dict[str, Any]:
        """Detect the intent of a user query
        
        Args:
            text: The user's query
            
        Returns:
            Dictionary with intent information
        """
        # This is a placeholder implementation
        # In a real implementation, this would use an intent classification model
        
        text_lower = text.lower()
        
        # Simple rule-based intent detection
        intents = [
            {"name": "greeting", "keywords": ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]},
            {"name": "farewell", "keywords": ["bye", "goodbye", "see you", "later", "good night"]},
            {"name": "gratitude", "keywords": ["thanks", "thank you", "appreciate"]},
            {"name": "weather", "keywords": ["weather", "temperature", "forecast", "rain", "sunny"]},
            {"name": "time", "keywords": ["time", "date", "day", "today", "clock"]},
            {"name": "music", "keywords": ["play", "music", "song", "track", "artist", "album"]},
            {"name": "search", "keywords": ["search", "find", "look up", "google", "information"]},
            {"name": "home_control", "keywords": ["turn on", "turn off", "lights", "temperature", "thermostat"]},
            {"name": "help", "keywords": ["help", "assist", "support", "how to", "how do"]},
        ]
        
        # Find matching intents
        matches = []
        for intent in intents:
            for keyword in intent["keywords"]:
                if keyword in text_lower:
                    matches.append({
                        "intent": intent["name"],
                        "confidence": 0.7,  # Placeholder confidence score
                        "matched_keyword": keyword
                    })
                    break
        
        # If no matches, return a default intent
        if not matches:
            return {
                "intent": "unknown",
                "confidence": 0.0,
                "matched_keyword": None
            }
        
        # Return the match with the highest confidence
        # In this simple implementation, just return the first match
        return matches[0]