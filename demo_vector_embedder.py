"""
Vector Embedder Demo Script
==========================

This script demonstrates the Phase 1 implementation of taxonomy vectorization.
It shows how the system would work when all dependencies are available.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def demo_without_dependencies():
    """Demo the system when vector dependencies are not available."""
    print("=== Vector Embedder Demo (Dependencies Not Available) ===\n")
    
    # Import the dummy version
    from core.vector_embedder import DummySemanticTaxonomy, get_semantic_taxonomy
    
    print("1. Getting semantic taxonomy instance...")
    taxonomy = get_semantic_taxonomy()
    print(f"   Instance type: {type(taxonomy).__name__}")
    
    print("\n2. Checking taxonomy stats...")
    stats = taxonomy.get_taxonomy_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\n3. Adding sample tags...")
    sample_tags = ['nature', 'landscape', 'tree', 'forest', 'mountain', 'sky']
    taxonomy.add_tags(sample_tags)
    print(f"   Added {len(sample_tags)} tags")
    
    print("\n4. Finding similar tags...")
    similar = taxonomy.find_similar_tags('nature')
    print(f"   Similar to 'nature': {similar}")
    
    print("\n5. Testing semantic enhancement...")
    from core.image_processing import extract_tags_with_semantics
    
    # Mock AI result
    mock_result = [
        {'label': 'nature, landscape', 'score': 0.95},
        {'label': 'tree, forest', 'score': 0.87},
        {'label': 'mountain', 'score': 0.75}
    ]
    
    category, keywords, description, semantic_data = extract_tags_with_semantics(
        result=mock_result,
        model_task="image-classification",
        taxonomy=taxonomy
    )
    
    print(f"   Extracted category: '{category}'")
    print(f"   Extracted keywords: {keywords}")
    print(f"   Semantic data: {semantic_data}")
    
    print("\n=== Demo Completed ===")
    print("\nNote: This demo shows the system working without vector dependencies.")
    print("When sentence-transformers and faiss-cpu are installed, the system")
    print("will automatically use real vector embeddings for semantic analysis.")


def demo_with_dependencies():
    """Demo the system when vector dependencies ARE available."""
    try:
        # Check if dependencies are available
        from sentence_transformers import SentenceTransformer
        import faiss
        
        print("=== Vector Embedder Demo (Dependencies Available) ===\n")
        
        from core.vector_embedder import SemanticTaxonomy, setup_vector_system
        
        print("1. Setting up vector system...")
        taxonomy = setup_vector_system()
        
        print("\n2. Initial stats...")
        stats = taxonomy.get_taxonomy_stats()
        for key, value in stats.items():
            print(f"   {key}: {value}")
        
        print("\n3. Adding sample tags...")
        sample_tags = ['nature', 'landscape', 'tree', 'forest', 'mountain', 'sky', 
                       'water', 'river', 'ocean', 'beach', 'sunset', 'sunrise']
        taxonomy.add_tags(sample_tags)
        
        stats = taxonomy.get_taxonomy_stats()
        print(f"   Tags in database: {stats['tag_count']}")
        
        print("\n4. Finding similar tags...")
        test_queries = ['nature', 'water', 'tree']
        for query in test_queries:
            similar = taxonomy.find_similar_tags(query, k=3)
            print(f"   Similar to '{query}':")
            for tag, score in similar:
                print(f"     - {tag} (score: {score:.3f})")
        
        print("\n5. Testing semantic enhancement...")
        from core.image_processing import extract_tags_with_semantics
        
        # Mock AI result
        mock_result = [
            {'label': 'nature, landscape', 'score': 0.95},
            {'label': 'tree, forest', 'score': 0.87},
            {'label': 'mountain', 'score': 0.75}
        ]
        
        category, keywords, description, semantic_data = extract_tags_with_semantics(
            result=mock_result,
            model_task="image-classification",
            taxonomy=taxonomy
        )
        
        print(f"   Extracted category: '{category}'")
        print(f"   Extracted keywords: {keywords}")
        print(f"   Semantic enabled: {semantic_data['semantic_enabled']}")
        
        if semantic_data.get('tag_similarities'):
            print("   Tag similarities found:")
            for keyword, similar_tags in semantic_data['tag_similarities'].items():
                print(f"     {keyword}: {similar_tags}")
        
        print("\n=== Demo Completed ===")
        
    except ImportError:
        print("Vector dependencies not available. Running basic demo instead.")
        demo_without_dependencies()


if __name__ == "__main__":
    print("Vector Embedder Demo Script")
    print("=" * 40)
    
    # Try to run with dependencies first
    demo_with_dependencies()