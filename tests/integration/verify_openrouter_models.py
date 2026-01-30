
import sys
import os
import time
import logging

# Ensure project root is in path
project_root = os.getcwd()
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_openrouter_validation():
    print("Testing OpenRouter Model Validation Logic...")
    
    try:
        from src.core import openrouter_utils
    except ImportError as e:
        print(f"FAILED: Could not import openrouter_utils: {e}")
        return

    # 1. Fetch All Models
    print("\n1. Fetching all models from OpenRouter (live API)...")
    start = time.time()
    models = openrouter_utils.fetch_all_models(force_refresh=True)
    duration = time.time() - start
    
    if not models:
        print("WARNING: No models returned. Check internet connection or API status.")
    else:
        print(f"SUCCESS: Fetched {len(models)} models in {duration:.2f}s.")
        print(f"Sample Model: {models[0].get('id', 'Unknown')}")

    # 2. Test Caching
    print("\n2. Testing Cache...")
    start = time.time()
    models_cached = openrouter_utils.fetch_all_models()
    duration = time.time() - start
    
    if len(models) == len(models_cached) and duration < 0.1:
        print(f"SUCCESS: Cache hit confirmed (returned in {duration:.4f}s).")
    else:
        print(f"FAILED: Cache missing or slow. Duration: {duration:.4f}s, Count: {len(models_cached)}")

    # 3. Test Validation
    print("\n3. Testing validate_model_id...")
    
    # Pick a valid ID if possible
    valid_id = models[0].get('id') if models else "openai/gpt-3.5-turbo"
    is_valid = openrouter_utils.validate_model_id(valid_id)
    print(f"Checking valid ID '{valid_id}': {is_valid}")
    if is_valid:
        print("SUCCESS: Valid model confirmed.")
    else:
        print("FAILED: Valid model rejected.")

    # Check fake ID
    fake_id = "fake/model-12345"
    is_invalid = openrouter_utils.validate_model_id(fake_id)
    print(f"Checking invalid ID '{fake_id}': {is_invalid}")
    if not is_invalid:
        print("SUCCESS: Invalid model correctly rejected.")
    else:
        print("FAILED: Invalid model accepted.")

    # 4. Test filtering with paid flag
    print("\n4. Testing find_models_by_task (paid vs free)...")
    free_models, _ = openrouter_utils.find_models_by_task("image-to-text", include_paid=False, limit=1000)
    paid_models, _ = openrouter_utils.find_models_by_task("image-to-text", include_paid=True, limit=1000)
    
    print(f"Free models found: {len(free_models)}")
    print(f"Total models (inc. paid) found: {len(paid_models)}")
    
    if len(paid_models) >= len(free_models):
        print("SUCCESS: Paid models included when requested.")
    else:
        print("WARNING: Paid count less than free count? (Maybe mostly free models available?)")

if __name__ == "__main__":
    test_openrouter_validation()
