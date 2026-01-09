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


def find_models_by_task(task: str, token: Optional[str] = None, limit: int = 50) -> Tuple[List[str], List[str]]:
    """Return (model_ids, downloaded_models)

    For OpenRouter there is no local download concept here, so downloaded_models is an empty list.
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
        model_ids = [m.get("id") or m.get("model") or m.get("name") for m in image_models]
        # Remove None and take unique
        model_ids = [m for m in model_ids if m]
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
            # Ask for a short JSON object with generated_text
            system_msg = {"role": "system", "content": "Return JSON with key 'generated_text' and the description string as its value."}
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
            "stream": False
        }

        headers_json = headers.copy()
        headers_json["Content-Type"] = "application/json"

        logger.debug(f"OpenRouter Request Body for {model_id}: {json.dumps(body)}")
        
        log_api_request(logger, "POST", chat_url, headers=headers_json, data=body)
        
        resp = requests.post(chat_url, headers=headers_json, json=body, timeout=60)
        elapsed = time.time() - start_time
        
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
                    outputs = json.loads(content)
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
            if isinstance(outputs, list):
                # convert string list or dicts into normalized generated_text list
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

