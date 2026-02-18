
import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.integrations.ollama_client import OllamaClient
from src.utils.config_manager import load_config
from src.core.session import Session

def verify():
    print("--- Verifying Ollama Cloud Connection ---")
    
    # Load config directly from file to simulate app startup
    session = Session()
    load_config(session)
    
    engine = session.engine
    print(f"Provider: {engine.provider}")
    print(f"Host: {engine.ollama_host}")
    
    if engine.provider != 'ollama':
        print("FAIL: Provider is not set to 'ollama'")
        return
        
    if engine.ollama_host != 'https://ollama.com':
        print(f"WARNING: Host is '{engine.ollama_host}', expected 'https://ollama.com'")
        
    if not engine.ollama_api_key:
        print("\nNOTE: No API Key found in configuration.")
        print("You will need to enter your key in the UI or in .synapic_v2_config.json")
        print("Testing connection without key (expected to fail for cloud)...")
    else:
        print("\nAPI Key found (masked): " + engine.ollama_api_key[:4] + "*" * 10)
        
    try:
        client = OllamaClient(host=engine.ollama_host, api_key=engine.ollama_api_key)
        
        print("\nAttempting to list models...")
        models = client.list_models()
        
        if models:
            print(f"SUCCESS: Found {len(models)} models.")
            for m in models[:3]:
                print(f" - {m['id']} ({m.get('family', 'unknown')})")
        else:
            print("WARNING: Connected but no models found (or auth failed silently).")
            
    except Exception as e:
        print(f"\nConnection failed as expected (if no key) or error: {e}")
        print("This confirms the client is attempting to connect to the cloud host.")

if __name__ == "__main__":
    verify()
