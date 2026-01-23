from huggingface_hub import HfApi
import logging

logging.basicConfig(level=logging.INFO)

def check_model(model_id):
    api = HfApi()
    print(f"\nChecking model: {model_id}")
    try:
        # Try with files_metadata=True
        info = api.model_info(repo_id=model_id, files_metadata=True)
        print(f"ID: {info.id}")
        
        total_size = 0
        if info.siblings:
            print(f"Siblings count: {len(info.siblings)}")
            for s in info.siblings:
                size = getattr(s, 'size', None)
                if size:
                    total_size += size
                else:
                    print(f"  {s.rfilename}: No size attribute")
        
        print(f"Calculated Total Size: {total_size} bytes")
        
        if hasattr(info, 'safetensors') and info.safetensors:
            print(f"Safetensors total: {info.safetensors.total}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_model("timm/resnet18.fb_swsl_iglb_ft_in1k")
    check_model("timm/inception_resnet_v2.tf_in1k")
    check_model("theadityamittal/resnet50")
