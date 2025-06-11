#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Memory Module for Jarvis Assistant

This module handles the memory and context management for the Jarvis assistant,
allowing it to remember past interactions and maintain context during conversations.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import threading

# For vector storage
try:
    import chromadb
    from chromadb.config import Settings
    VECTOR_DB_AVAILABLE = True
except ImportError:
    VECTOR_DB_AVAILABLE = False


class Memory:
    """Memory management for Jarvis Assistant"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the memory system
        
        Args:
            config: Configuration dictionary for memory settings
        """
        self.logger = logging.getLogger("jarvis.memory")
        self.config = config
        
        # Set up memory storage paths
        self.data_dir = config.get("data_dir", "data/memory")
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.memory_file = os.path.join(self.data_dir, "memory.json")
        self.conversation_history_file = os.path.join(self.data_dir, "conversation_history.json")
        
        # Initialize memory structures
        self.short_term_memory = []
        self.long_term_memory = self._load_long_term_memory()
        self.conversation_history = self._load_conversation_history()
        self.user_preferences = self.long_term_memory.get("user_preferences", {})
        
        # Thread lock for memory access
        self.memory_lock = threading.RLock()
        
        # Initialize vector database if available
        self.vector_db = None
        if VECTOR_DB_AVAILABLE and config.get("use_vector_db", True):
            self._initialize_vector_db()
        
        self.logger.info("Memory system initialized")
    
    def _initialize_vector_db(self):
        """Initialize the vector database for semantic memory storage"""
        try:
            vector_db_path = os.path.join(self.data_dir, "vector_db")
            os.makedirs(vector_db_path, exist_ok=True)
            
            self.vector_db = chromadb.Client(Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=vector_db_path
            ))
            
            # Create collections if they don't exist
            try:
                self.memory_collection = self.vector_db.get_collection("memory")
                self.logger.debug("Loaded existing memory collection")
            except ValueError:
                self.memory_collection = self.vector_db.create_collection("memory")
                self.logger.debug("Created new memory collection")
                
            self.logger.info("Vector database initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize vector database: {e}")
            self.vector_db = None
    
    def _load_long_term_memory(self) -> Dict[str, Any]:
        """Load long-term memory from disk"""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading memory file: {e}")
                return {}
        else:
            return {}
    
    def _load_conversation_history(self) -> List[Dict[str, Any]]:
        """Load conversation history from disk"""
        if os.path.exists(self.conversation_history_file):
            try:
                with open(self.conversation_history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading conversation history: {e}")
                return []
        else:
            return []
    
    def save(self):
        """Save memory to disk"""
        with self.memory_lock:
            # Save long-term memory
            try:
                with open(self.memory_file, 'w', encoding='utf-8') as f:
                    json.dump(self.long_term_memory, f, ensure_ascii=False, indent=2)
            except Exception as e:
                self.logger.error(f"Error saving memory file: {e}")
            
            # Save conversation history
            try:
                # Limit conversation history size
                max_history = self.config.get("max_conversation_history", 1000)
                history_to_save = self.conversation_history[-max_history:] if len(self.conversation_history) > max_history else self.conversation_history
                
                with open(self.conversation_history_file, 'w', encoding='utf-8') as f:
                    json.dump(history_to_save, f, ensure_ascii=False, indent=2)
            except Exception as e:
                self.logger.error(f"Error saving conversation history: {e}")
            
            # Persist vector database if available
            if self.vector_db is not None:
                try:
                    self.vector_db.persist()
                    self.logger.debug("Vector database persisted")
                except Exception as e:
                    self.logger.error(f"Error persisting vector database: {e}")
    
    def add_to_short_term_memory(self, item: Dict[str, Any]):
        """Add an item to short-term memory
        
        Args:
            item: The memory item to add
        """
        with self.memory_lock:
            # Add timestamp if not present
            if "timestamp" not in item:
                item["timestamp"] = datetime.now().isoformat()
            
            # Add to short-term memory
            self.short_term_memory.append(item)
            
            # Limit short-term memory size
            max_short_term = self.config.get("max_short_term_memory", 50)
            if len(self.short_term_memory) > max_short_term:
                self.short_term_memory = self.short_term_memory[-max_short_term:]
    
    def add_to_long_term_memory(self, category: str, key: str, value: Any):
        """Add an item to long-term memory
        
        Args:
            category: The category of the memory (e.g., "user_info", "preferences")
            key: The key for the memory item
            value: The value to store
        """
        with self.memory_lock:
            # Initialize category if it doesn't exist
            if category not in self.long_term_memory:
                self.long_term_memory[category] = {}
            
            # Add the item
            self.long_term_memory[category][key] = value
            
            # If it's a user preference, update the user_preferences dict too
            if category == "user_preferences":
                self.user_preferences[key] = value
            
            # Add to vector database if available
            if self.vector_db is not None and category != "system":
                try:
                    memory_text = f"{category}: {key} - {value}"
                    self.memory_collection.add(
                        documents=[memory_text],
                        metadatas=[{"category": category, "key": key, "timestamp": datetime.now().isoformat()}],
                        ids=[f"{category}_{key}_{datetime.now().timestamp()}"],
                    )
                except Exception as e:
                    self.logger.error(f"Error adding to vector database: {e}")
    
    def get_from_long_term_memory(self, category: str, key: str, default: Any = None) -> Any:
        """Get an item from long-term memory
        
        Args:
            category: The category of the memory
            key: The key for the memory item
            default: Default value if not found
            
        Returns:
            The stored value or default if not found
        """
        with self.memory_lock:
            if category in self.long_term_memory and key in self.long_term_memory[category]:
                return self.long_term_memory[category][key]
            return default
    
    def add_conversation(self, user_input: str, assistant_response: str):
        """Add a conversation exchange to history
        
        Args:
            user_input: The user's input
            assistant_response: The assistant's response
        """
        with self.memory_lock:
            conversation_item = {
                "timestamp": datetime.now().isoformat(),
                "user_input": user_input,
                "assistant_response": assistant_response
            }
            
            self.conversation_history.append(conversation_item)
            
            # Add to short-term memory for context
            self.add_to_short_term_memory({
                "type": "conversation",
                "user_input": user_input,
                "assistant_response": assistant_response
            })
            
            # Add to vector database if available
            if self.vector_db is not None:
                try:
                    conversation_text = f"User: {user_input}\nAssistant: {assistant_response}"
                    self.memory_collection.add(
                        documents=[conversation_text],
                        metadatas=[{"type": "conversation", "timestamp": conversation_item["timestamp"]}],
                        ids=[f"conversation_{datetime.now().timestamp()}"],
                    )
                except Exception as e:
                    self.logger.error(f"Error adding conversation to vector database: {e}")
    
    def get_recent_conversations(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversations
        
        Args:
            count: Number of recent conversations to retrieve
            
        Returns:
            List of recent conversation items
        """
        with self.memory_lock:
            return self.conversation_history[-count:] if len(self.conversation_history) > count else self.conversation_history
    
    def search_memory(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search memory using semantic search
        
        Args:
            query: The search query
            limit: Maximum number of results to return
            
        Returns:
            List of matching memory items
        """
        results = []
        
        # Search vector database if available
        if self.vector_db is not None:
            try:
                query_results = self.memory_collection.query(
                    query_texts=[query],
                    n_results=limit
                )
                
                if query_results and len(query_results["documents"]) > 0:
                    for i, doc in enumerate(query_results["documents"][0]):
                        metadata = query_results["metadatas"][0][i] if i < len(query_results["metadatas"][0]) else {}
                        results.append({
                            "text": doc,
                            "metadata": metadata,
                            "score": query_results["distances"][0][i] if "distances" in query_results and i < len(query_results["distances"][0]) else None
                        })
            except Exception as e:
                self.logger.error(f"Error searching vector database: {e}")
        
        # If no vector database or no results, fall back to simple keyword search
        if not results:
            # Search conversation history
            for conv in reversed(self.conversation_history):
                if query.lower() in conv["user_input"].lower() or query.lower() in conv["assistant_response"].lower():
                    results.append({
                        "text": f"User: {conv['user_input']}\nAssistant: {conv['assistant_response']}",
                        "metadata": {"type": "conversation", "timestamp": conv["timestamp"]},
                        "score": 1.0  # Simple match score
                    })
                    if len(results) >= limit:
                        break
            
            # Search long-term memory if still need more results
            if len(results) < limit:
                for category, items in self.long_term_memory.items():
                    for key, value in items.items():
                        if query.lower() in str(key).lower() or query.lower() in str(value).lower():
                            results.append({
                                "text": f"{category}: {key} - {value}",
                                "metadata": {"category": category, "key": key},
                                "score": 1.0  # Simple match score
                            })
                            if len(results) >= limit:
                                break
                    if len(results) >= limit:
                        break
        
        return results
    
    def get_context_for_query(self, query: str) -> Dict[str, Any]:
        """Get relevant context for a query
        
        Args:
            query: The user's query
            
        Returns:
            Dictionary with relevant context information
        """
        context = {
            "short_term_memory": self.short_term_memory,
            "recent_conversations": self.get_recent_conversations(5),
            "user_preferences": self.user_preferences,
            "relevant_memories": self.search_memory(query, 3)
        }
        
        return context
    
    def clear_short_term_memory(self):
        """Clear short-term memory"""
        with self.memory_lock:
            self.short_term_memory = []
            self.logger.info("Short-term memory cleared")