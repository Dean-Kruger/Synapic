from huggingface_hub import list_models, HfApi
import logging

logging.basicConfig(level=logging.INFO)

def check_list_full(query):
    print(f"\nSearching for: {query} with full=True")
    try:
        models = list_models(search=query, limit=5, full=True)
        count = 0
        for m in models:
            count += 1
            print(f"\nModel: {m.id}")
            total_size = 0
            if m.siblings:
                print(f"  Siblings: {len(m.siblings)}")
                for s in m.siblings:
                    size = getattr(s, 'size', None)
                    if size:
                        total_size += size
            print(f"  Total Size: {total_size}")
            
            if hasattr(m, 'safetensors') and m.safetensors:
                print(f"  Safetensors total: {m.safetensors.total}")
        
        if count == 0:
            print("No models found.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_list_full("resnet")
