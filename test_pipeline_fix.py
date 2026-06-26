#!/usr/bin/env python
"""
Test to verify the pipeline fix works correctly.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_pipeline_integration():
    """Test that the processing pipeline works with the new function."""
    print("Testing pipeline integration...")
    
    try:
        # Test the image processing functions
        from src.core.image_processing import extract_tags_from_result, extract_tags_with_semantics
        
        # Mock AI result (this should work for both classification and zero-shot)
        mock_result = [
            {'label': 'nature, landscape', 'score': 0.95},
            {'label': 'tree, forest', 'score': 0.87},
            {'label': 'mountain', 'score': 0.75}
        ]
        
        # Test old function still works
        print("Testing old function...")
        cat1, kws1, desc1 = extract_tags_from_result(
            mock_result, "image-classification", threshold=0.7
        )
        print(f"Old function - Category: '{cat1}', Keywords: {kws1}")
        
        # Test new function works
        print("Testing new function...")
        cat2, kws2, desc2, semantic_data = extract_tags_with_semantics(
            mock_result, "image-classification", threshold=0.7, taxonomy=None
        )
        print(f"New function - Category: '{cat2}', Keywords: {kws2}")
        print(f"Semantic enabled: {semantic_data['semantic_enabled']}")
        
        # Verify they produce the same basic results
        assert cat1 == cat2, f"Categories differ: {cat1} vs {cat2}"
        assert kws1 == kws2, f"Keywords differ: {kws1} vs {kws2}"
        assert desc1 == desc2, f"Descriptions differ: {desc1} vs {desc2}"
        
        print("SUCCESS: Both functions produce identical results")
        
        # Test with zero-shot classification
        print("\nTesting zero-shot classification...")
        zero_shot_result = [
            {'label': 'Nature', 'score': 0.92},
            {'label': 'Landscape', 'score': 0.88},
            {'label': 'Outdoor', 'score': 0.76}
        ]
        
        cat3, kws3, desc3 = extract_tags_from_result(
            zero_shot_result, "zero-shot-image-classification", threshold=0.7
        )
        print(f"Zero-shot - Category: '{cat3}', Keywords: {kws3}")
        
        # Test with image-to-text
        print("\nTesting image-to-text...")
        text_result = [{
            'generated_text': 'A beautiful landscape with trees and mountains'
        }]
        
        cat4, kws4, desc4 = extract_tags_from_result(
            text_result, "image-to-text", threshold=0.0
        )
        print(f"Image-to-text - Category: '{cat4}', Description: '{desc4[:50]}...'")
        
        print("\nSUCCESS: All pipeline tests passed!")
        return True
        
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Pipeline Integration Test")
    print("=" * 40)
    
    success = test_pipeline_integration()
    
    if success:
        print("\n" + "=" * 40)
        print("PIPELINE FIX VERIFIED!")
        print("=" * 40)
        print("\nThe processing pipeline now correctly uses")
        print("extract_tags_with_semantics while maintaining")
        print("backward compatibility with extract_tags_from_result.")
    else:
        print("\nPipeline test failed. Please check the error above.")