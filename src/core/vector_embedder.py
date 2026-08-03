"""
Vector Embedding System for Taxonomy
=====================================

This module provides vector embedding capabilities for semantic understanding
of image metadata, tags, and categories. It enables deeper semantic search
and automatic grouping of digital assets.

Key Components:
- TextEmbedder: Generates embeddings for text data (tags, descriptions)
- ImageEmbedder: Generates embeddings for visual data
- VectorDatabase: Manages storage and retrieval of embeddings
- SemanticSearch: Provides similarity search capabilities

Dependencies:
- sentence-transformers: For text embeddings
- torch: PyTorch for model inference
- faiss-cpu: Facebook AI Similarity Search for vector database
- numpy: Numerical operations

Author: Synapic Project
"""

# ============================================================================
# IMPORTS
# ============================================================================

import logging
import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
import json
import time

# Try to import optional dependencies
try:
    from sentence_transformers import SentenceTransformer
    import faiss
    import torch  # noqa: F401
    HAS_VECTOR_DEPS = True
except ImportError:
    HAS_VECTOR_DEPS = False
    logging.warning("Vector embedding dependencies not available. Install with: pip install sentence-transformers faiss-cpu")


logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

# Default embedding model (good balance of quality and performance)
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Vector database paths
VECTOR_DB_DIR = Path("vector_cache")
TAG_EMBEDDINGS_FILE = VECTOR_DB_DIR / "tag_embeddings.faiss"
IMAGE_EMBEDDINGS_FILE = VECTOR_DB_DIR / "image_embeddings.faiss"
METADATA_FILE = VECTOR_DB_DIR / "vector_metadata.json"

# Embedding dimensions
EMBEDDING_DIM = 384  # Dimension for all-MiniLM-L6-v2

# ============================================================================
# VECTOR DATABASE MANAGEMENT
# ============================================================================

class VectorDatabase:
    """
    Manages storage and retrieval of vector embeddings using FAISS.
    """
    
    def __init__(self, db_path: Path, dimension: int = EMBEDDING_DIM):
        """
        Initialize vector database.
        
        Args:
            db_path: Path to FAISS index file
            dimension: Dimension of embeddings
        """
        self.db_path = db_path
        self.dimension = dimension
        self.index = None
        self.metadata = {}
        self._ensure_directory()
        self._load_or_create_index()
        
    def _ensure_directory(self):
        """Ensure database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
    def _load_or_create_index(self):
        """Load existing index or create new one."""
        if self.db_path.exists():
            try:
                self.index = faiss.read_index(str(self.db_path))
                logger.info(f"Loaded FAISS index from {self.db_path}")
                self._load_metadata()
            except Exception as e:
                logger.warning(f"Failed to load FAISS index: {e}. Creating new index.")
                self._create_new_index()
        else:
            self._create_new_index()
            
    def _create_new_index(self):
        """Create a new FAISS index."""
        # Use IndexFlatL2 for exact search (good for smaller collections)
        # For larger collections, consider IndexIVFFlat
        self.index = faiss.IndexFlatL2(self.dimension)
        logger.info(f"Created new FAISS index with dimension {self.dimension}")
        
    def _load_metadata(self):
        """Load metadata from JSON file."""
        metadata_path = self.db_path.with_suffix(".json")
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
                logger.info(f"Loaded metadata from {metadata_path}")
            except Exception as e:
                logger.warning(f"Failed to load metadata: {e}")
                self.metadata = {}
        else:
            self.metadata = {}
            
    def _save_metadata(self):
        """Save metadata to JSON file."""
        metadata_path = self.db_path.with_suffix(".json")
        try:
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved metadata to {metadata_path}")
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")
            
    def add_embeddings(self, texts: List[str], embeddings: np.ndarray):
        """
        Add embeddings to the database.
        
        Args:
            texts: List of text strings corresponding to embeddings
            embeddings: numpy array of shape (n, dimension)
        """
        if not HAS_VECTOR_DEPS:
            logger.warning("Vector dependencies not available. Skipping embedding storage.")
            return
            
        if embeddings.shape[1] != self.dimension:
            raise ValueError(f"Embedding dimension mismatch. Expected {self.dimension}, got {embeddings.shape[1]}")
            
        # Add to FAISS index
        self.index.add(embeddings)
        
        # Store metadata mapping
        start_id = self.index.ntotal - len(texts)
        for i, text in enumerate(texts):
            vector_id = start_id + i
            self.metadata[vector_id] = {
                'text': text,
                'timestamp': time.time(),
                'type': 'text'
            }
            
        # Save index and metadata
        self._save_index()
        self._save_metadata()
        
    def _save_index(self):
        """Save FAISS index to disk."""
        try:
            faiss.write_index(self.index, str(self.db_path))
            logger.debug(f"Saved FAISS index to {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to save FAISS index: {e}")
            
    def search_similar(self, query_embedding: np.ndarray, k: int = 5) -> Tuple[List[int], List[float], List[str]]:
        """
        Find most similar embeddings.
        
        Args:
            query_embedding: Query embedding vector
            k: Number of results to return
            
        Returns:
            Tuple of (vector_ids, distances, texts)
        """
        if not HAS_VECTOR_DEPS or self.index is None:
            return [], [], []
            
        if len(query_embedding.shape) == 1:
            query_embedding = query_embedding.reshape(1, -1)
            
        distances, indices = self.index.search(query_embedding, k)
        
        # Get corresponding texts from metadata
        results = []
        for idx_row in indices:
            row_results = []
            for vector_id in idx_row:
                if vector_id >= 0 and vector_id in self.metadata:
                    row_results.append(self.metadata[vector_id]['text'])
                else:
                    row_results.append("")
            results.append(row_results)
            
        return indices[0].tolist(), distances[0].tolist(), results[0]
        
    def get_embedding_count(self) -> int:
        """Get number of embeddings in database."""
        if self.index is None:
            return 0
        return self.index.ntotal
        
    def clear(self):
        """Clear all embeddings from database."""
        self.index.reset()
        self.metadata = {}
        self._save_index()
        self._save_metadata()

# ============================================================================
# TEXT EMBEDDER
# ============================================================================

class TextEmbedder:
    """
    Generates vector embeddings for text data using sentence transformers.
    """
    
    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL):
        """
        Initialize text embedder.
        
        Args:
            model_name: Name of sentence transformer model to use
        """
        self.model_name = model_name
        self.model = None
        self._load_model()
        
    def _load_model(self):
        """Load the sentence transformer model."""
        if not HAS_VECTOR_DEPS:
            logger.warning("Sentence transformers not available. Text embedding disabled.")
            return
            
        try:
            logger.info(f"Loading sentence transformer model: {self.model_name}")
            start_time = time.time()
            self.model = SentenceTransformer(self.model_name)
            load_time = time.time() - start_time
            logger.info(f"Model loaded in {load_time:.2f} seconds")
            
            # Verify embedding dimension
            test_embedding = self.model.encode(["test"])
            actual_dim = test_embedding.shape[1]
            logger.info(f"Model embedding dimension: {actual_dim}")
            
        except Exception as e:
            logger.error(f"Failed to load sentence transformer model: {e}")
            self.model = None
            
    def embed_texts(self, texts: List[str]) -> Optional[np.ndarray]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            numpy array of shape (n, embedding_dim) or None if failed
        """
        if not self.model:
            logger.warning("Text embedder not initialized. Returning None.")
            return None
            
        try:
            # Filter out empty/None texts
            valid_texts = [text for text in texts if text and str(text).strip()]
            if not valid_texts:
                return np.array([])
                
            embeddings = self.model.encode(valid_texts, convert_to_numpy=True)
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate text embeddings: {e}")
            return None
            
    def embed_single(self, text: str) -> Optional[np.ndarray]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text string to embed
            
        Returns:
            numpy array of shape (embedding_dim,) or None if failed
        """
        if not text or not str(text).strip():
            return None
            
        embeddings = self.embed_texts([text])
        if embeddings is not None and len(embeddings) > 0:
            return embeddings[0]
        return None

# ============================================================================
# SEMANTIC TAXONOMY MANAGER
# ============================================================================

class SemanticTaxonomy:
    """
    Manages semantic relationships between tags and categories.
    """
    
    def __init__(self):
        """Initialize semantic taxonomy manager."""
        self.text_embedder = TextEmbedder()
        self.tag_db = VectorDatabase(VECTOR_DB_DIR / "tag_embeddings.faiss")
        self.image_db = VectorDatabase(VECTOR_DB_DIR / "image_embeddings.faiss")
        self.tag_cache = {}  # text -> embedding cache
        
    def add_tags(self, tags: List[str]):
        """
        Add tags to the semantic taxonomy.
        
        Args:
            tags: List of tag strings to add
        """
        if not HAS_VECTOR_DEPS:
            return
            
        # Filter and deduplicate
        unique_tags = list(set(tag for tag in tags if tag and str(tag).strip()))
        if not unique_tags:
            return
            
        # Generate embeddings
        embeddings = self.text_embedder.embed_texts(unique_tags)
        if embeddings is not None:
            self.tag_db.add_embeddings(unique_tags, embeddings)
            
            # Update cache
            for i, tag in enumerate(unique_tags):
                self.tag_cache[tag] = embeddings[i]
                
    def find_similar_tags(self, query_tag: str, k: int = 5) -> List[Tuple[str, float]]:
        """
        Find tags semantically similar to the query tag.
        
        Args:
            query_tag: Query tag string
            k: Number of similar tags to return
            
        Returns:
            List of (similar_tag, similarity_score) tuples
        """
        if not HAS_VECTOR_DEPS:
            return []
            
        # Check cache first
        if query_tag in self.tag_cache:
            query_embedding = self.tag_cache[query_tag]
        else:
            query_embedding = self.text_embedder.embed_single(query_tag)
            if query_embedding is None:
                return []
                
        # Search database
        vector_ids, distances, similar_texts = self.tag_db.search_similar(query_embedding, k)
        
        # Create results with similarity scores (convert distance to similarity)
        results = []
        for text, distance in zip(similar_texts, distances):
            if text and text != query_tag:  # Exclude self-matches
                similarity = 1.0 / (1.0 + distance)  # Convert distance to similarity score
                results.append((text, similarity))
                
        return results
        
    def get_tag_embedding(self, tag: str) -> Optional[np.ndarray]:
        """
        Get embedding for a specific tag.
        
        Args:
            tag: Tag string
            
        Returns:
            Embedding vector or None
        """
        if tag in self.tag_cache:
            return self.tag_cache[tag]
            
        embedding = self.text_embedder.embed_single(tag)
        if embedding is not None:
            self.tag_cache[tag] = embedding
        return embedding
        
    def get_taxonomy_stats(self) -> Dict[str, Any]:
        """Get statistics about the semantic taxonomy."""
        return {
            'tag_count': self.tag_db.get_embedding_count(),
            'image_count': self.image_db.get_embedding_count(),
            'cache_size': len(self.tag_cache),
            'has_vector_deps': HAS_VECTOR_DEPS
        }

# ============================================================================
# INTEGRATION WITH EXISTING PIPELINE
# ============================================================================

def enhance_metadata_with_semantics(
    category: str,
    keywords: List[str], 
    description: str,
    taxonomy: SemanticTaxonomy
) -> Dict[str, Any]:
    """
    Enhance metadata with semantic information.
    
    Args:
        category: Category string
        keywords: List of keyword strings
        description: Description text
        taxonomy: SemanticTaxonomy instance
        
    Returns:
        Dictionary with semantic enhancement data
    """
    if not HAS_VECTOR_DEPS:
        return {
            'semantic_enabled': False,
            'message': 'Vector dependencies not available'
        }
        
    semantic_data = {
        'semantic_enabled': True,
        'tag_similarities': {},
        'category_similarities': [],
        'description_embedding': None
    }
    
    # Add all keywords to taxonomy
    if keywords:
        taxonomy.add_tags(keywords)
        
        # Find similar tags for each keyword
        for keyword in keywords:
            if keyword:
                similar_tags = taxonomy.find_similar_tags(keyword, k=3)
                if similar_tags:
                    semantic_data['tag_similarities'][keyword] = similar_tags
    
    # Process category
    if category:
        taxonomy.add_tags([category])
        similar_categories = taxonomy.find_similar_tags(category, k=3)
        semantic_data['category_similarities'] = similar_categories
        
    # Process description
    if description:
        description_embedding = taxonomy.text_embedder.embed_single(description)
        if description_embedding is not None:
            semantic_data['description_embedding'] = description_embedding.tolist()
            
    return semantic_data

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def setup_vector_system() -> SemanticTaxonomy:
    """
    Initialize the vector embedding system.
    
    Returns:
        SemanticTaxonomy instance
    """
    logger.info("Setting up vector embedding system...")
    
    if not HAS_VECTOR_DEPS:
        logger.warning("Vector embedding dependencies not available. Install with:")
        logger.warning("pip install sentence-transformers faiss-cpu")
        
    taxonomy = SemanticTaxonomy()
    stats = taxonomy.get_taxonomy_stats()
    logger.info(f"Vector system initialized. Stats: {stats}")
    
    return taxonomy

# ============================================================================
# BACKWARD COMPATIBILITY
# ============================================================================

class DummySemanticTaxonomy:
    """Dummy implementation for when vector deps are not available."""
    
    def add_tags(self, tags: List[str]):
        pass
        
    def find_similar_tags(self, query_tag: str, k: int = 5) -> List[Tuple[str, float]]:
        return []
        
    def get_tag_embedding(self, tag: str) -> Optional[np.ndarray]:
        return None
        
    def get_taxonomy_stats(self) -> Dict[str, Any]:
        return {
            'tag_count': 0,
            'image_count': 0,
            'cache_size': 0,
            'has_vector_deps': False
        }

def get_semantic_taxonomy() -> SemanticTaxonomy:
    """Get semantic taxonomy instance (real or dummy)."""
    if HAS_VECTOR_DEPS:
        return SemanticTaxonomy()
    else:
        return DummySemanticTaxonomy()