import sys
import os
from pathlib import Path

# Add project root to sys.path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from src.core.huggingface_utils import get_remote_model_size, format_size
import logging

logging.basicConfig(level=logging.INFO)

def verify_models():
    test_models = [
        "timm/resnet18.fb_swsl_iglb_ft_in1k",
        "theadityamittal/resnet50",
        "Qwen/Qwen2-VL-2B-Instruct"
    ]
    
    print("\nVerifying Model Sizes after Fix:")
    print("-" * 50)
    for mid in test_models:
        try:
            size = get_remote_model_size(mid)
            print(f"Model: {mid:<40} | Size: {format_size(size)}")
            if size == 0:
                print(f"  FAILED: Size is still 0 for {mid}")
        except Exception as e:
            print(f"  ERROR for {mid}: {e}")

if __name__ == "__main__":
    verify_models()
