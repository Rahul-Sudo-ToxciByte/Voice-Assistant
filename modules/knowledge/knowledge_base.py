#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Knowledge Base for Jarvis Assistant

This module handles the knowledge storage and retrieval capabilities of the Jarvis assistant,
including vector database integration for semantic search and information management.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime
import time

# Import for vector database
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

# Import for embeddings
try:
    import numpy as np
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


class KnowledgeBase:
    """Knowledge base for Jarvis Assistant"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the knowledge base
        
        Args:
            config: Configuration dictionary for knowledge base settings
        """
        self.logger = logging.getLogger("jarvis.knowledge")
        self.config = config
        
        # Set up knowledge base configuration
        self.data_dir = config.get("data_dir", os.path.join("data", "knowledge"))
        self.enable_vector_db = config.get("enable_vector_db", True)
        self.embedding_model = config.get("embedding_model", "all-MiniLM-L6-v2")
        self.collection_name = config.get("collection_name", "jarvis_knowledge")
        
        # Create data directory if it doesn't exist
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Initialize vector database if enabled
        self.vector_db = None
        self.collection = None
        self.embedding_model_instance = None
        
        if self.enable_vector_db:
            self._initialize_vector_db()
        
        # Initialize facts database
        self.facts = {}
        self._load_facts()
        
        self.logger.info(f"Knowledge base initialized (vector DB: {self.enable_vector_db})")
    
    def _initialize_vector_db(self):
        """Initialize the vector database"""
        if not CHROMADB_AVAILABLE:
            self.logger.error("ChromaDB not available. Vector database will be disabled.")
            self.enable_vector_db = False
            return
        
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            self.logger.error("Sentence Transformers not available. Vector database will be disabled.")
            self.enable_vector_db = False
            return
        
        try:
            # Initialize embedding model
            self.embedding_model_instance = SentenceTransformer(self.embedding_model)
            
            # Initialize ChromaDB client
            db_path = os.path.join(self.data_dir, "chroma")
            self.vector_db = chromadb.PersistentClient(
                path=db_path,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection
            try:
                self.collection = self.vector_db.get_collection(name=self.collection_name)
                self.logger.info(f"Loaded existing collection: {self.collection_name}")
            except Exception:
                self.collection = self.vector_db.create_collection(name=self.collection_name)
                self.logger.info(f"Created new collection: {self.collection_name}")
            
            self.logger.info(f"Vector database initialized with model: {self.embedding_model}")
        
        except Exception as e:
            self.logger.error(f"Error initializing vector database: {e}")
            self.enable_vector_db = False
    
    def _load_facts(self):
        """Load facts from the facts database"""
        facts_path = os.path.join(self.data_dir, "facts.json")
        
        if os.path.exists(facts_path):
            try:
                with open(facts_path, 'r', encoding='utf-8') as f:
                    self.facts = json.load(f)
                self.logger.info(f"Loaded {len(self.facts)} facts from database")
            except Exception as e:
                self.logger.error(f"Error loading facts database: {e}")
                self.facts = {}
    
    def _save_facts(self):
        """Save facts to the facts database"""
        facts_path = os.path.join(self.data_dir, "facts.json")
        
        try:
            with open(facts_path, 'w', encoding='utf-8') as f:
                json.dump(self.facts, f, indent=2, ensure_ascii=False)
            self.logger.debug(f"Saved {len(self.facts)} facts to database")
        except Exception as e:
            self.logger.error(f"Error saving facts database: {e}")
    
    def add_document(self, document: str, metadata: Optional[Dict[str, Any]] = None, doc_id: Optional[str] = None) -> Optional[str]:
        """Add a document to the knowledge base
        
        Args:
            document: The document text to add
            metadata: Optional metadata for the document
            doc_id: Optional document ID (generated if not provided)
            
        Returns:
            Document ID if successful, None otherwise
        """
        if not self.enable_vector_db or self.collection is None:
            self.logger.error("Vector database not available")
            return None
        
        try:
            # Generate document ID if not provided
            if doc_id is None:
                doc_id = f"doc_{int(time.time())}_{len(document) % 1000}"
            
            # Create default metadata if not provided
            if metadata is None:
                metadata = {
                    "source": "user_input",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Generate embedding
            embedding = self.embedding_model_instance.encode(document).tolist()
            
            # Add to collection
            self.collection.add(
                documents=[document],
                embeddings=[embedding],
                metadatas=[metadata],
                ids=[doc_id]
            )
            
            self.logger.info(f"Added document with ID: {doc_id}")
            return doc_id
        
        except Exception as e:
            self.logger.error(f"Error adding document: {e}")
            return None
    
    def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Search the knowledge base for relevant documents
        
        Args:
            query: The search query
            n_results: Maximum number of results to return
            
        Returns:
            List of matching documents with their metadata and relevance scores
        """
        if not self.enable_vector_db or self.collection is None:
            self.logger.error("Vector database not available")
            return []
        
        try:
            # Generate query embedding
            query_embedding = self.embedding_model_instance.encode(query).tolist()
            
            # Search collection
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            
            # Format results
            formatted_results = []
            for i, (doc_id, document, metadata, distance) in enumerate(zip(
                results["ids"][0],
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            )):
                # Convert distance to similarity score (0-1)
                similarity = 1.0 - min(1.0, distance)
                
                formatted_results.append({
                    "id": doc_id,
                    "document": document,
                    "metadata": metadata,
                    "similarity": similarity
                })
            
            self.logger.debug(f"Found {len(formatted_results)} results for query: {query[:50]}...")
            return formatted_results
        
        except Exception as e:
            self.logger.error(f"Error searching knowledge base: {e}")
            return []
    
    def add_fact(self, category: str, fact: str, source: Optional[str] = None) -> bool:
        """Add a fact to the facts database
        
        Args:
            category: Category of the fact (e.g., "user_preference", "world_knowledge")
            fact: The fact text
            source: Optional source of the fact
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate fact ID
            fact_id = f"fact_{int(time.time())}_{len(fact) % 1000}"
            
            # Create fact entry
            fact_entry = {
                "text": fact,
                "added": datetime.now().isoformat(),
                "source": source or "user_input"
            }
            
            # Add to facts database
            if category not in self.facts:
                self.facts[category] = {}
            
            self.facts[category][fact_id] = fact_entry
            
            # Save facts database
            self._save_facts()
            
            # Also add to vector database if enabled
            if self.enable_vector_db:
                metadata = {
                    "type": "fact",
                    "category": category,
                    "source": source or "user_input",
                    "timestamp": datetime.now().isoformat()
                }
                self.add_document(fact, metadata, doc_id=fact_id)
            
            self.logger.info(f"Added fact to category '{category}': {fact[:50]}...")
            return True
        
        except Exception as e:
            self.logger.error(f"Error adding fact: {e}")
            return False
    
    def get_facts(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Get facts from the facts database
        
        Args:
            category: Optional category to filter by
            
        Returns:
            Dictionary of facts, filtered by category if specified
        """
        if category is not None:
            return self.facts.get(category, {})
        else:
            return self.facts
    
    def search_facts(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Search facts using semantic search
        
        Args:
            query: The search query
            n_results: Maximum number of results to return
            
        Returns:
            List of matching facts with their metadata and relevance scores
        """
        if not self.enable_vector_db:
            # Fallback to simple text matching
            results = []
            for category, facts in self.facts.items():
                for fact_id, fact_data in facts.items():
                    if query.lower() in fact_data["text"].lower():
                        results.append({
                            "id": fact_id,
                            "text": fact_data["text"],
                            "category": category,
                            "metadata": fact_data,
                            "similarity": 0.5  # Default similarity for text matching
                        })
            
            # Sort by "similarity" and limit results
            results = sorted(results, key=lambda x: x["similarity"], reverse=True)[:n_results]
            return results
        
        # Use vector database for semantic search
        try:
            # Search with filter for facts only
            query_embedding = self.embedding_model_instance.encode(query).tolist()
            
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where={"type": "fact"}
            )
            
            # Format results
            formatted_results = []
            for i, (doc_id, document, metadata, distance) in enumerate(zip(
                results["ids"][0],
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            )):
                # Convert distance to similarity score (0-1)
                similarity = 1.0 - min(1.0, distance)
                
                formatted_results.append({
                    "id": doc_id,
                    "text": document,
                    "category": metadata.get("category", "unknown"),
                    "metadata": metadata,
                    "similarity": similarity
                })
            
            return formatted_results
        
        except Exception as e:
            self.logger.error(f"Error searching facts: {e}")
            return []
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete a document from the knowledge base
        
        Args:
            doc_id: Document ID to delete
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enable_vector_db or self.collection is None:
            self.logger.error("Vector database not available")
            return False
        
        try:
            self.collection.delete(ids=[doc_id])
            
            # Also remove from facts if it's a fact
            for category in self.facts:
                if doc_id in self.facts[category]:
                    del self.facts[category][doc_id]
                    self._save_facts()
                    break
            
            self.logger.info(f"Deleted document with ID: {doc_id}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error deleting document: {e}")
            return False
    
    def get_document_count(self) -> int:
        """Get the number of documents in the knowledge base
        
        Returns:
            Number of documents
        """
        if not self.enable_vector_db or self.collection is None:
            return 0
        
        try:
            return self.collection.count()
        except Exception as e:
            self.logger.error(f"Error getting document count: {e}")
            return 0
    
    def get_fact_count(self) -> int:
        """Get the number of facts in the facts database
        
        Returns:
            Number of facts
        """
        count = 0
        for category in self.facts:
            count += len(self.facts[category])
        return count
    
    def add_user_preference(self, preference_key: str, preference_value: Any) -> bool:
        """Add a user preference
        
        Args:
            preference_key: Key for the preference
            preference_value: Value for the preference
            
        Returns:
            True if successful, False otherwise
        """
        # Convert value to string if it's not a basic type
        if not isinstance(preference_value, (str, int, float, bool, type(None))):
            preference_value = str(preference_value)
        
        # Create fact text
        fact = f"User preference: {preference_key} = {preference_value}"
        
        return self.add_fact("user_preferences", fact, source="user_setting")
    
    def get_user_preferences(self) -> Dict[str, Any]:
        """Get all user preferences
        
        Returns:
            Dictionary of user preferences
        """
        preferences = {}
        pref_facts = self.get_facts("user_preferences")
        
        for fact_id, fact_data in pref_facts.items():
            # Parse preference from fact text
            text = fact_data["text"]
            if text.startswith("User preference: "):
                try:
                    # Extract key and value
                    key_value = text[len("User preference: "):]
                    key, value_str = key_value.split(" = ", 1)
                    
                    # Convert value string to appropriate type
                    if value_str.lower() == "true":
                        value = True
                    elif value_str.lower() == "false":
                        value = False
                    elif value_str.lower() == "none":
                        value = None
                    else:
                        try:
                            # Try to convert to int or float
                            if value_str.isdigit():
                                value = int(value_str)
                            else:
                                value = float(value_str)
                        except ValueError:
                            # Keep as string
                            value = value_str
                    
                    preferences[key] = value
                except Exception:
                    # Skip malformed preference
                    continue
        
        return preferences
    
    def import_knowledge(self, filepath: str) -> Tuple[int, int]:
        """Import knowledge from a JSON file
        
        Args:
            filepath: Path to the JSON file
            
        Returns:
            Tuple of (documents_added, facts_added)
        """
        if not os.path.exists(filepath):
            self.logger.error(f"Import file not found: {filepath}")
            return (0, 0)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            documents_added = 0
            facts_added = 0
            
            # Import documents
            if "documents" in data and isinstance(data["documents"], list):
                for doc in data["documents"]:
                    if isinstance(doc, dict) and "text" in doc:
                        metadata = doc.get("metadata", {})
                        doc_id = doc.get("id")
                        
                        if self.add_document(doc["text"], metadata, doc_id):
                            documents_added += 1
            
            # Import facts
            if "facts" in data and isinstance(data["facts"], dict):
                for category, facts in data["facts"].items():
                    if isinstance(facts, list):
                        for fact in facts:
                            if isinstance(fact, str):
                                if self.add_fact(category, fact):
                                    facts_added += 1
                            elif isinstance(fact, dict) and "text" in fact:
                                source = fact.get("source")
                                if self.add_fact(category, fact["text"], source):
                                    facts_added += 1
            
            self.logger.info(f"Imported {documents_added} documents and {facts_added} facts from {filepath}")
            return (documents_added, facts_added)
        
        except Exception as e:
            self.logger.error(f"Error importing knowledge: {e}")
            return (0, 0)
    
    def export_knowledge(self, filepath: str) -> bool:
        """Export knowledge to a JSON file
        
        Args:
            filepath: Path to the JSON file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Prepare export data
            export_data = {
                "facts": self.facts,
                "documents": []
            }
            
            # Export documents from vector database
            if self.enable_vector_db and self.collection is not None:
                try:
                    # Get all documents (up to 1000)
                    results = self.collection.get(limit=1000)
                    
                    for i, (doc_id, document, metadata) in enumerate(zip(
                        results["ids"],
                        results["documents"],
                        results["metadatas"]
                    )):
                        # Skip facts (they're already in the facts section)
                        if metadata.get("type") == "fact":
                            continue
                        
                        export_data["documents"].append({
                            "id": doc_id,
                            "text": document,
                            "metadata": metadata
                        })
                except Exception as e:
                    self.logger.error(f"Error exporting documents: {e}")
            
            # Write to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Exported {len(export_data['documents'])} documents and {self.get_fact_count()} facts to {filepath}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error exporting knowledge: {e}")
            return False
    
    def shutdown(self):
        """Shutdown the knowledge base"""
        # Save facts database
        self._save_facts()
        
        # Close vector database
        self.vector_db = None
        self.collection = None
        
        self.logger.info("Knowledge base shut down")