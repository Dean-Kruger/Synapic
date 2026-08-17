# Probability-Based Image Tagging & Scoring

This document provides a technical specification and implementation guide for extracting mathematically calibrated confidence scores (probabilities) from vision models. 

---

## Technical Decision Matrix

Choose the appropriate method based on API capabilities:

```
                  ┌───────────────────────────────┐
                  │ Are token logprobs available? │
                  └───────────────┬───────────────┘
                                  │
                  ┌───────────────┴───────────────┐
                  ▼                               ▼
               [ Yes ]                         [ No ]
         Method 1: Logprobs              Method 2: Text JSON
         (Highly Recommended)                 (Fallback)
```

| Metric / Aspect | Method 1: Logprobs (Recommended) | Method 2: Text JSON (Fallback) |
| :--- | :--- | :--- |
| **Accuracy** | Extremely High (True model logits) | Low-Medium (Textual estimation) |
| **Calibration** | Mathematically Grounded | Subjective Model Bias |
| **Token Cost** | Extremely Low (1 output token) | High (Full JSON generation) |
| **Prerequisites**| API support for `logprobs=True` | Standard Chat Completion |

---

## Method 1: Token Logprobs Classification (Recommended)

Extracts true model confidence by obtaining the log probabilities of a single classification token and applying a softmax normalization.

### 1. Classification Prompt Standard
Configure the model to output **exactly one token** as its very first output.

```text
Analyze the provided image and classify it into one of the following options:
A) Indoor Office
B) Outdoor Nature
C) Urban Street
D) Vehicle Interior

Respond with ONLY the single option letter (A, B, C, or D) corresponding to your choice. Do not include any other text, reasoning, or punctuation.
```

### 2. Implementation Steps
1. Send request with `logprobs=True` and `top_logprobs=5` (or higher depending on candidate count).
2. Limit output length to `max_tokens=1` to save latency and guarantee only the classification character is generated.
3. Extract the first token's top logprobs.
4. Filter for candidate keys, map missing options to `-inf` (0.0 probability), and apply the Softmax function.

### 3. Reference Implementation (Python)
```python
from typing import Dict, List
import numpy as np

def calculate_logprob_probabilities(
    first_token_logprobs, 
    candidates: List[str]
) -> Dict[str, float]:
    """
    Extracts and normalizes probabilities for a set of candidate tokens
    using Softmax over raw log probabilities.
    
    Args:
        first_token_logprobs: The logprobs array from the API response
                             (e.g., response.choices[0].logprobs.content[0].top_logprobs)
        candidates: List of single-character candidate strings (e.g., ["A", "B", "C", "D"])
        
    Returns:
        Dict mapping candidate string to float probability summing to 1.0.
    """
    # 1. Initialize logprob mapping with -inf (0.0 probability)
    logprob_map = {c: float("-inf") for c in candidates}
    
    # 2. Populate mapping with actual returned logprobs (strip whitespace and match case)
    for item in first_token_logprobs:
        token = item.token.strip().upper()
        if token in logprob_map:
            logprob_map[token] = item.logprob
            
    # 3. Apply Softmax for numerical stability (subtract max)
    logprobs_array = np.array([logprob_map[c] for c in candidates])
    max_logprob = np.max(logprobs_array)
    
    # If all candidates have -inf logprob, fallback to uniform distribution
    if max_logprob == float("-inf"):
        uniform_val = 1.0 / len(candidates)
        return {c: uniform_val for c in candidates}
        
    exp_probs = np.exp(logprobs_array - max_logprob)
    normalized_probs = exp_probs / np.sum(exp_probs)
    
    return dict(zip(candidates, normalized_probs.tolist()))
```

---

## Method 2: Text-Only JSON Prompting (Fallback)

Used when the API or model does not support token logprobs. This relies on the model to perform textual calibration and formatting.

### 1. Prompt Standard
Use structured schema requirements to enforce output constraints.

```text
Examine the image carefully. You must assign a probability score to each of the following candidate options based on visual evidence:
- Option A: Cat
- Option B: Dog
- Option C: Fox

Requirements:
1. Return valid JSON only. Do not wrap in markdown codeblocks.
2. Provide a float probability between 0.00 and 1.00 for each option.
3. The sum of all probabilities MUST equal exactly 1.00.

Output format:
{
  "A": 0.0,
  "B": 0.0,
  "C": 0.0
}
```

### 2. Validation & Correction Steps
Since models frequently fail mathematical bounds (e.g., sum is slightly off or values are out of bounds), parse and self-correct the distribution:

```python
import json
from typing import Dict

def parse_and_normalize_json_probs(raw_json: str, candidates: list) -> Dict[str, float]:
    """
    Parses textual JSON probabilities, enforces bounds [0.0, 1.0], 
    and guarantees they sum to exactly 1.0.
    """
    # 1. Parse JSON
    data = json.loads(raw_json)
    
    # 2. Extract values and bound between 0.0 and 1.0
    probs = {}
    total = 0.0
    for c in candidates:
        val = float(data.get(c, 0.0))
        val = max(0.0, min(1.0, val))
        probs[c] = val
        total += val
        
    # 3. Normalize if sum is not exactly 1.0 (or is 0.0)
    if total <= 0.0:
        uniform = 1.0 / len(candidates)
        return {c: uniform for c in candidates}
        
    if abs(total - 1.0) > 1e-9:
        for c in probs:
            probs[c] /= total
            
    return probs
```

---

## Verification & Implementation Checklist

An implementing agent or developer must verify the following criteria:

- [ ] **Method 1 Prompt Constraint**: Prompt strictly requests a single-character response (`A`, `B`, `C`, etc.) as the very first token.
- [ ] **Method 1 Token Limit**: `max_tokens` is set to `1` in the API call config to guarantee fast generation and block runaway token generation.
- [ ] **Method 1 Logprob Extraction**: Response parser handles cases where the model selects a token outside the candidate set (safely mapping candidate keys to `-inf`).
- [ ] **Method 1 Casing Robustness**: Token comparison is case-insensitive and strips whitespace (e.g., `" A "` is normalized to `"A"`).
- [ ] **Numerical Stability**: Softmax subtracts the maximum logprob before performing exponentiation to avoid floating-point overflow/underflow.
- [ ] **Sum-to-One Invariant**: Resulting dictionary values sum to exactly `1.0` (within a tolerance of `1e-9`).

---
## Local Model Implementation (Synapic Application)

The Synapic desktop application implements probability scoring for local HF models via:

### UI Controls
- In Step 2 (Engine selection), under the Local provider tab, expand "Probability Scoring (Local only)"
- Toggle "Enable calibrated probabilities" to activate the feature
- Enter candidate tokens as comma-separated values (e.g., `A,B,C,D`) or one per line
- Optional: Set probability threshold (0.0-1.0) to filter low-confidence candidates

### Processing & Logging
- When enabled, the application logs a line for each processed image:
  `Probabilities: {'A': 0.85, 'B': 0.10, 'C': 0.04, 'D': 0.01}`
- The probability map is also stored in the session result for export
- On failure (model doesn't support logprobs), the feature is hidden and normal caption flow continues

### Configuration Persistence
- Settings are saved to `~/.synapic_v2_config.json` and restored on application restart
