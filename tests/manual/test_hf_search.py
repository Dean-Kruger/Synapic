from huggingface_hub import list_models
import logging

logging.basicConfig(level=logging.INFO)

def test_search(query, task=None):
    print(f"\n--- Searching for '{query}' (Task: {task}) ---")
    try:
        models = list_models(filter=task, search=query, limit=10, sort="downloads", direction=-1)
        found = [m.id for m in models]
        print(f"Found {len(found)} models: {found}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Test restrictive task search (current implementation behavior for multi-modal)
    test_search("resnet", task="image-to-text")
    
    # Test image-classification task
    test_search("resnet", task="image-classification")
    
    # Test no task filter
    test_search("resnet", task=None)
    
    # Test broad search
    test_search("vit", task=None)
