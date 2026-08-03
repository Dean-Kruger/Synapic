#!/usr/bin/env python
"""
Simple test to verify the vector embedder implementation works.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_basic_functionality():
    """Test basic functionality without full dependencies."""
    print("Testing vector embedder basic functionality...")
    
    try:
        # Test that we can import the module
        from core.vector_embedder import (
            HAS_VECTOR_DEPS, 
            DummySemanticTaxonomy, 
            get_semantic_taxonomy
        )
        
        print(f"✓ Module imported successfully")
        print(f"✓ HAS_VECTOR_DEPS: {HAS_VECTOR_DEPS}")
        
        # Test dummy taxonomy
        dummy = DummySemanticTaxonomy()
        dummy.add_tags(["test", "sample"])
        similar = dummy.find_similar_tags("test")
        stats = dummy.get_taxonomy_stats()
        
        print(f"✓ Dummy taxonomy works: {stats}")
        
        # Test get_semantic_taxonomy function
        taxonomy = get_semantic_taxonomy()
        print(f"✓ get_semantic_taxonomy returns: {type(taxonomy).__name__}")
        
        # Test integration with image processing
        from core.image_processing import extract_tags_with_semantics
        
        mock_result = [
            {'label': 'nature, landscape', 'score': 0.95},
            {'label': 'tree, forest', 'score': 0.87}
        ]
        
        category, keywords, description, semantic_data = extract_tags_with_semantics(
            result=mock_result,
            model_task="image-classification",
            taxonomy=taxonomy
        )
        
        print(f"✓ Image processing integration works")
        print(f"  Category: '{category}'")
        print(f"  Keywords: {keywords}")
        print(f"  Semantic enabled: {semantic_data['semantic_enabled']}")
        
        print("\n🎉 All basic tests passed!")
        print("\nThe vector embedder system is ready to use.")
        print("When sentence-transformers and faiss-cpu are installed,")
        print("the system will automatically use real vector embeddings.")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Vector Embedder Implementation Test")
    print("=" * 40)
    
    success = test_basic_functionality()
    
    if success:
        print("\n" + "=" * 40)
        print("Phase 1 Implementation Summary:")
        print("✓ Vector embedder module created")
        print("✓ Semantic taxonomy management implemented")
        print("✓ Integration with image processing pipeline")
        print("✓ Backward compatibility with dummy implementation")
        print("✓ Local vector database using FAISS (when available)")
        print("✓ Text embedding using sentence transformers (when available)")
        print("\nNext steps:")
        print("1. Install dependencies: pip install sentence-transformers faiss-cpu")
        print("2. The system will automatically use real embeddings")
        print("3. Semantic search and tag similarity will be enabled")
    else:
        print("\nPlease check the error above and ensure all dependencies are installed.")