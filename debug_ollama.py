
import sys
import logging
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
    from ollamafreeapi import OllamaFreeAPI
except ImportError:
    print("ollamafreeapi package not installed.")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
output_file = r"c:\Users\Dean\source\repos\Synapic\debug_result.txt"

def check_models():
    lines = []
    lines.append("Initializing OllamaFreeAPI Client...")
    
    try:
        client = OllamaFreeAPI()
        
        # Check broader families
        for fam in ['gemma', 'llama']:
            lines.append(f"\n--- Checking {fam} models ---")
            try:
                models = client.list_models(family=fam)
                lines.append(f"Models: {models}")
                
                # Check server count for the first few models
                for model in models[:3]:
                    servers = client.get_model_servers(model)
                    lines.append(f"  {model}: {len(servers)} servers")
            except Exception as e:
                lines.append(f"Error: {e}")

    except Exception as e:
        lines.append(f"Error: {e}")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Debug results written to {output_file}")

if __name__ == "__main__":
    check_models()
