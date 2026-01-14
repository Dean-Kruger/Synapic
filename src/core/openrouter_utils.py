"""Minimal OpenRouter utilities.

Provides model listing (filtered for image-capable models) and a stub for inference.
This implementation attempts to call the OpenRouter public models endpoint and filter
models that declare image/vision modalities. It gracefully handles network errors
and returns an empty list on failure.
"""

import logging
import requests
from typing import List, Tuple, Optional, Any
from src.core import config

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
SITE_URL = "https://github.com/deanable/hugging-juice-face"
SITE_NAME = "Hugging Juice Face"

# Whitelist of known free vision models that support system messages
# These models have been verified to work with developer instructions
FREE_VISION_MODELS_WITH_SYSTEM_SUPPORT = [
    "google/gemini-2.0-flash-exp:free",
    "google/gemini-flash-1.5-exp",
    "nvidia/nemotron-nano-2-vl:free",
    "qwen/qwen-2.5-vl-3b-instruct:free",
]


def _extract_models_from_response(resp_json):
    # Support list, dict with 'models', and dict with 'data'
    if isinstance(resp_json, dict):
        if "data" in resp_json:
            return resp_json.get("data", [])
        if "models" in resp_json:
            return resp_json.get("models", [])
    if isinstance(resp_json, list):
        return resp_json
    return []


def _is_image_model(model_meta: dict) -> bool:
    # Check architecture.modality or architecture.input_modalities (OpenRouter new schema)
    arch = model_meta.get("architecture") or {}
    if isinstance(arch, dict):
        # Check input_modalities list
        input_mods = arch.get("input_modalities")
        if isinstance(input_mods, list) and "image" in input_mods:
            return True
        # Check modality string (e.g. "text+image->text")
        modality_str = arch.get("modality")
        if isinstance(modality_str, str) and ("image" in modality_str or "vision" in modality_str):
            return True

    # Legacy: Look for modalities or tags
    modalities = []
    modalities_raw = model_meta.get("modalities")
    if isinstance(modalities_raw, list):
        modalities = [m.lower() for m in modalities_raw if isinstance(m, str)]
    
    tags_raw = model_meta.get("tags") or []
    tags = [t.lower() for t in tags_raw if isinstance(t, str)]
    
    # Check common indicators
    if "image" in modalities or "vision" in modalities or "multimodal" in modalities:
        return True
    
    joined_tags = " ".join(tags)
    if any(x in joined_tags for x in ("image", "vision", "multimodal", "clip", "vl")):
        return True
    
    return False


def _is_free_model(model_meta: dict) -> bool:
    """Check if a model is free to use (no cost per token)."""
    # Check if model ID is in our known free models list
    model_id = model_meta.get("id") or model_meta.get("model") or model_meta.get("name") or ""
    if any(known in model_id for known in FREE_VISION_MODELS_WITH_SYSTEM_SUPPORT):
        return True
    
    # Check pricing information
    pricing = model_meta.get("pricing") or {}
    if isinstance(pricing, dict):
        # Check if both prompt and completion are free
        prompt_price = pricing.get("prompt")
        completion_price = pricing.get("completion")
        
        # Convert to float and check if zero
        try:
            if prompt_price is not None and completion_price is not None:
                prompt_val = float(prompt_price) if isinstance(prompt_price, (int, float, str)) else None
                completion_val = float(completion_price) if isinstance(completion_price, (int, float, str)) else None
                if prompt_val == 0 and completion_val == 0:
                    return True
        except (ValueError, TypeError):
            pass
    
    # Check if ":free" suffix in model ID
    if ":free" in model_id.lower():
        return True
    
    return False


def _supports_system_messages(model_meta: dict) -> bool:
    """Check if a model supports system messages (developer instructions)."""
    # First check our whitelist of known compatible models
    model_id = model_meta.get("id") or model_meta.get("model") or model_meta.get("name") or ""
    if any(known in model_id for known in FREE_VISION_MODELS_WITH_SYSTEM_SUPPORT):
        return True
    
    # Check if model metadata explicitly states system message support
    if model_meta.get("supports_system_message") is True:
        return True
    
    # Check architecture for system message support indicators
    arch = model_meta.get("architecture") or {}
    if isinstance(arch, dict):
        if arch.get("supports_system_message") is True:
            return True
    
    # Gemma models generally don't support system messages
    if "gemma" in model_id.lower():
        return False
    
    # For safety, if we can't determine support, exclude it
    # (better to show fewer models than to show broken ones)
    return False


def find_models_by_task(task: str, token: Optional[str] = None, limit: int = 50) -> Tuple[List[str], List[str]]:
    """Return (model_ids, downloaded_models)

    For OpenRouter there is no local download concept here, so downloaded_models is an empty list.
    
    Filters models to only include:
    - Image-capable models (vision/multimodal)
    - Free models (no cost per token)
    - Models that support system messages (developer instructions)
    """
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    headers["HTTP-Referer"] = SITE_URL
    headers["X-Title"] = SITE_NAME

    try:
        r = requests.get(OPENROUTER_MODELS_URL, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        models = _extract_models_from_response(data)
        
        # Filter for image-capable models
        image_models = [m for m in models if isinstance(m, dict) and _is_image_model(m)]
        
        # Further filter for free models with system message support
        compatible_models = [
            m for m in image_models 
            if _is_free_model(m) and _supports_system_messages(m)
        ]
        
        model_ids = [m.get("id") or m.get("model") or m.get("name") for m in compatible_models]
        # Remove None and take unique
        model_ids = [m for m in model_ids if m]
        
        # Log the filtering results
        logging.info(f"OpenRouter model discovery: {len(models)} total, {len(image_models)} vision, {len(compatible_models)} free+system-msg")
        
        # Limit
        model_ids = model_ids[:limit]
        return model_ids, []
    except Exception as e:
        logging.warning(f"OpenRouter model discovery failed: {e}")
        return [], []


def find_models_by_name(search_query: Optional[str], task: str, token: Optional[str] = None, limit: int = 50) -> Tuple[List[str], List[str]]:
    # Fallback: get all models and do a simple name filter
    model_ids, _ = find_models_by_task(task, token=token, limit=limit*2)
    if search_query:
        filtered = [m for m in model_ids if search_query.lower() in m.lower()]
        return filtered[:limit], []
    return model_ids[:limit], []


def run_inference_api(model_id: str, image_path: str, task: str, token: Optional[str] = None, parameters: Optional[dict] = None) -> Any:
    """Run inference against OpenRouter for a single image.

    Preferred method: use the chat/completions endpoint and pass the image as a
    base64 `image_url` content part, because this matches the OpenRouter API
    request schema for multimodal models. If that fails or the response shape is
    unexpected, fall back to the older model outputs endpoint (multipart upload).

    Returns a normalized structure similar to the Hugging Face adapter so the
    rest of the application can process it transparently.
    """
    import base64
    import json
    import time
    from pathlib import Path
    from src.utils.logger import log_api_request, log_api_response
    
    logger = logging.getLogger(__name__)
    logger.info(f"[OpenRouter API] Starting inference - Model: {model_id}, Task: {task}")
    start_time = time.time()

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    headers["HTTP-Referer"] = SITE_URL
    headers["X-Title"] = SITE_NAME

    chat_url = "https://openrouter.ai/api/v1/chat/completions"
    fallback_url = f"https://openrouter.ai/api/v1/models/{model_id}/outputs"

    img_path = Path(image_path)
    if not img_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    try:
        b64_image = None
        with open(img_path, "rb") as f:
            b64_image = base64.b64encode(f.read()).decode("utf-8")

        # Build image content part per OpenRouter schema
        image_part = {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64_image}", "detail": "auto"}
        }

        # Construct messages & instructions depending on task
        messages = []
        system_msg = None
        if task == config.MODEL_TASK_IMAGE_TO_TEXT:
            # Ask for a structured JSON object with description, category, and keywords
            system_msg = {
                "role": "system", 
                "content": (
                    "You are an expert media archivist. Analyze the image and return a JSON object with these keys:\n"
                    "- 'description': A detailed caption of the image.\n"
                    "- 'category': A single broad category (e.g., 'Landscape', 'Portrait', 'Event').\n"
                    "- 'keywords': A list of 5-10 descriptive tags.\n"
                    "Do NOT include markdown formatting (like ```json). Return ONLY the raw JSON string."
                )
            }
            user_msg = {"role": "user", "content": [image_part]}
            messages = [system_msg, user_msg]

        elif task == config.MODEL_TASK_IMAGE_CLASSIFICATION:
            # Ask for a JSON array of objects {label, score}
            system_msg = {"role": "system", "content": "Return a JSON array of objects with keys 'label' and 'score' for the top classes."}
            user_msg = {"role": "user", "content": [image_part]}
            messages = [system_msg, user_msg]

        elif task == config.MODEL_TASK_ZERO_SHOT:
            # Include candidate labels in a JSON field if provided
            candidate_labels = None
            if parameters and isinstance(parameters, dict):
                candidate_labels = parameters.get("candidate_labels")
            system_content = "Return JSON with keys 'labels' (list) and 'scores' (list) ranking candidates by relevance."
            if candidate_labels:
                system_content += f" Use these candidate labels: {candidate_labels}"
            system_msg = {"role": "system", "content": system_content}
            user_msg = {"role": "user", "content": [image_part]}
            messages = [system_msg, user_msg]

        else:
            # Generic fallback: ask for plain text
            user_msg = {"role": "user", "content": [image_part]}
            messages = [user_msg]

        body = {
            "model": model_id,
            "messages": messages,
            # Non-streaming for simplicity
            "stream": False,
            "max_tokens": parameters.get("max_new_tokens") if parameters else None
        }

        headers_json = headers.copy()
        headers_json["Content-Type"] = "application/json"

        logger.debug(f"OpenRouter Request Body for {model_id}: {json.dumps(body)}")
        
        log_api_request(logger, "POST", chat_url, headers=headers_json, data=body)
        
        # DEBUG: Check token
        if token:
            logger.debug(f"Using API key: {token[:8]}...{token[-4:]} (Length: {len(token)})")
        else:
            logger.warning("No API key provided!")

        resp = requests.post(chat_url, headers=headers_json, json=body, timeout=60)
        elapsed = time.time() - start_time
        
        # DEBUG: Check redirects
        if resp.history:
            logger.warning(f"Request was redirected. History: {[r.url for r in resp.history]}")
            logger.warning(f"Final URL: {resp.url}")
        
        log_api_response(logger, resp.status_code, elapsed_time=elapsed)
        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as re:
            logger.error(f"OpenRouter Chat API failed: {re}")
            logger.error(f"Response Content: {resp.text}")
            raise re
        
        resp_json = resp.json()

        # Extract the assistant content
        outputs = None
        if isinstance(resp_json, dict) and resp_json.get("choices"):
            choice = resp_json.get("choices")[0]
            # OpenRouter normalizes to a message with content
            message = choice.get("message") or {}
            content = message.get("content")
            # content may be string, dict, or list
            if isinstance(content, str):
                # Try to parse JSON out of the string if present
                try:
                    # Clean potential markdown
                    cleaned_content = content.replace("```json", "").replace("```", "").strip()
                    outputs = json.loads(cleaned_content)
                except Exception:
                    # Treat as plain text
                    if task == config.MODEL_TASK_IMAGE_TO_TEXT:
                        outputs = [{"generated_text": content}]
                    else:
                        outputs = content
            else:
                outputs = content
        else:
            # Fallback: Not the chat format. Use the whole json
            outputs = resp_json

        # If outputs looks empty or unsupported, fall back to file upload endpoint
        if not outputs:
            raise RuntimeError("Empty outputs from chat endpoint, falling back")

        # Normalize similar to prior logic
        if task == config.MODEL_TASK_IMAGE_CLASSIFICATION:
            if isinstance(outputs, list):
                return outputs
            if isinstance(outputs, dict):
                if 'classifications' in outputs and isinstance(outputs['classifications'], list):
                    return outputs['classifications']
                if 'label' in outputs and 'score' in outputs:
                    return [outputs]
            return outputs

        if task == config.MODEL_TASK_ZERO_SHOT:
            if isinstance(outputs, list):
                return outputs
            if isinstance(outputs, dict) and 'labels' in outputs and 'scores' in outputs:
                return outputs
            return outputs

        if task == config.MODEL_TASK_IMAGE_TO_TEXT:
            # If we received the structured JSON we asked for (dict with desc/cat/kw)
            if isinstance(outputs, dict):
                # Check if it has our keys
                if any(k in outputs for k in ['description', 'category', 'keywords']):
                    # Wrap in a list to match expected "generated_text" wrapper structure 
                    # but pass the whole dict as the value so image_processing can parse it
                    return [{'generated_text': outputs}]
                
                # Check for standard generated_text/text keys
                if 'generated_text' in outputs:
                    return [{'generated_text': outputs['generated_text']}]
                if 'text' in outputs:
                    return [{'generated_text': outputs['text']}]

            if isinstance(outputs, list):
                # convert string list or dicts into normalized generated_text list
                normalized = []
                for o in outputs:
                    if isinstance(o, str):
                        normalized.append({'generated_text': o})
                    elif isinstance(o, dict):
                        # It might be a list of structured dicts?
                        if any(k in o for k in ['description', 'category', 'keywords']):
                             normalized.append({'generated_text': o})
                        else:
                            gen = o.get('generated_text') or o.get('text') or o.get('output')
                            if isinstance(gen, str):
                                normalized.append({'generated_text': gen})
                            else:
                                normalized.append({'generated_text': str(o)})
                    else:
                        normalized.append({'generated_text': str(o)})
                return normalized
            return outputs

        logger.info(f"[OpenRouter API] Inference successful - Duration: {elapsed:.3f}s")
        return outputs

    except requests.exceptions.HTTPError as e:
        status = getattr(e.response, 'status_code', None)
        if status in [404, 410]:
            raise ValueError(f"Model {model_id} is not available on the OpenRouter API. Status: {status}")
        raise

    except Exception as first_err:
        logger.warning(f"[OpenRouter API] Chat endpoint failed ({type(first_err).__name__}): {first_err}")
        logger.info(f"[OpenRouter API] Attempting multipart fallback: {fallback_url}")
        # FALLBACK: multipart upload to older outputs endpoint
        try:
            with open(img_path, "rb") as img_f:
                files = {"image": img_f}
                data = {}
                if parameters:
                    data["parameters"] = parameters
                
                logger.info(f"[OpenRouter API] Sending multipart request to fallback endpoint")
                resp = requests.post(fallback_url, headers=headers, files=files, data=data, timeout=60)
                fallback_elapsed = time.time() - start_time
                
                log_api_response(logger, resp.status_code, elapsed_time=fallback_elapsed)
                try:
                    resp.raise_for_status()
                except requests.exceptions.HTTPError as e:
                    status = getattr(e.response, 'status_code', None)
                    if status in [404, 410]:
                        raise ValueError(f"Model {model_id} is not available on the OpenRouter API. Status: {status}")
                    raise

                resp_json = resp.json()

            # try to extract outputs from common wrapper keys
            outputs = None
            if isinstance(resp_json, dict):
                for k in ("outputs", "predictions", "choices", "data"):
                    if k in resp_json:
                        outputs = resp_json[k]
                        break
                if outputs is None:
                    outputs = resp_json
            else:
                outputs = resp_json

            # reuse prior normalization
            if task == config.MODEL_TASK_IMAGE_CLASSIFICATION:
                if isinstance(outputs, list):
                    return outputs
                if isinstance(outputs, dict):
                    if 'classifications' in outputs and isinstance(outputs['classifications'], list):
                        return outputs['classifications']
                    if 'label' in outputs and 'score' in outputs:
                        return [outputs]
                return outputs

            if task == config.MODEL_TASK_ZERO_SHOT:
                if isinstance(outputs, list):
                    return outputs
                if isinstance(outputs, dict) and 'labels' in outputs and 'scores' in outputs:
                    return outputs
                return outputs

            if task == config.MODEL_TASK_IMAGE_TO_TEXT:
                if isinstance(outputs, list):
                    normalized = []
                    for o in outputs:
                        if isinstance(o, str):
                            normalized.append({'generated_text': o})
                        elif isinstance(o, dict):
                            gen = o.get('generated_text') or o.get('text') or o.get('output')
                            if isinstance(gen, str):
                                normalized.append({'generated_text': gen})
                            else:
                                normalized.append({'generated_text': str(o)})
                        else:
                            normalized.append({'generated_text': str(o)})
                    return normalized
                if isinstance(outputs, dict):
                    if 'generated_text' in outputs:
                        return [{'generated_text': outputs['generated_text']}]
                    if 'text' in outputs:
                        return [{'generated_text': outputs['text']}]
                return outputs

            logger.info(f"[OpenRouter API] Fallback inference successful - Duration: {fallback_elapsed:.3f}s")
            return outputs

        except Exception as e:
            total_elapsed = time.time() - start_time
            logger.error(f"[OpenRouter API] All inference attempts failed after {total_elapsed:.3f}s")
            logger.exception(f"OpenRouter API inference failed on fallback: {e}")
            raise ValueError(f"OpenRouter inference failed: {e}")

