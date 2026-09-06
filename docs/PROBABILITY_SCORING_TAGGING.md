# Probability-Based Image Tagging & Scoring

This document covers two related but distinct topics:

1. **The API scoring design reference** (Methods 1 and 2 below) — how a
   *cloud LLM/VLM* can be made to emit calibrated confidence scores using
   token logprobs or constrained JSON output.
2. **What the Synapic local implementation actually does today** — which is
   *not* calibrated logprob extraction. The local path reuses an
   `image-classification` pipeline and reports its per-label confidence
   scores.

> **Read this first:** the section titled *Local Model Implementation
> (Synapic Application)* describes shipping behavior. The two "Method"
> sections above it are a design reference for API providers and are
> **not** what the desktop app currently executes for local models.

---

## Scope: what "scoring user keywords" means here

Synapic does not score arbitrary free-form user keywords. The scoring
feature is the **candidate-token probability pass**:

- The user enters a comma-separated list of **candidate tokens** in Step 2
  (Local provider tab).
- For each processed image, every candidate receives a score in `[0.0, 1.0]`.
- In **Probability-only** tagging mode, the top-scoring candidate becomes
  the Category and every candidate passing the threshold becomes a Keyword.
- In **Both** mode, the scores are logged and stored alongside the normal
  LLM/caption flow.

A candidate only produces a meaningful score when it corresponds to one of
the *classification model's* trained labels. This constraint is enforced
loudly (see *Mismatch behavior* below).

---

## Technical Decision Matrix (API design reference)

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

## Verification & Implementation Checklist (API methods)

An implementing agent or developer must verify the following criteria:

- [ ] **Method 1 Prompt Constraint**: Prompt strictly requests a single-character response (`A`, `B`, `C`, etc.) as the very first token.
- [ ] **Method 1 Token Limit**: `max_tokens` is set to `1` in the API call config to guarantee fast generation and block runaway token generation.
- [ ] **Method 1 Logprob Extraction**: Response parser handles cases where the model selects a token outside the candidate set (safely mapping candidate keys to `-inf`).
- [ ] **Method 1 Casing Robustness**: Token comparison is case-insensitive and strips whitespace (e.g., `" A "` is normalized to `"A"`).
- [ ] **Numerical Stability**: Softmax subtracts the maximum logprob before performing exponentiation to avoid floating-point overflow/underflow.
- [ ] **Sum-to-One Invariant**: Resulting dictionary values sum to exactly `1.0` (within a tolerance of `1e-9`).

---

## Local Model Implementation (Synapic Application) — actual behavior

Entry point: `run_local_logprob_inference()` in
`src/core/huggingface_utils.py`. Wired in
`ProcessingManager._process_single_item()` (`src/core/processing.py`),
configured from `EngineConfig.probability_*` (`src/core/session.py`),
and edited in the Local provider tab
(`src/ui/steps/provider_tab_local.py`).

### What the scores actually are — read before trusting them

| Question | Answer |
| :--- | :--- |
| Are these calibrated logprobs from a prompted LLM? | **No.** The local path never extracts token logprobs. |
| Are they softmax over raw classification-head logits? | **No.** The pipeline returns post-processed per-label confidences (usually softmax over the head, but transformers decides; Synapic does not touch raw logits). |
| Are they temperature-scaled or Platt-scaled? | **No.** No calibration is performed or claimed. |
| What are they, precisely? | The `image-classification` pipeline's `score` for the model label that the user's candidate token was **matched to**. |
| Do they sum to 1.0 across the user's candidates? | **No.** Each score is that label's confidence over the *model's full label space*, so the user-visible map does not sum to one and is not a distribution over the candidate set. |
| Can two candidates receive the same score? | **Yes** — when both map to the same model label. |

Treat the scores as **relative confidences over the model's label space,
surfaced through candidate tokens**, not as a calibrated probability
distribution over the user's keywords.

### How a candidate is matched to a model label

For each candidate, in order:

1. **Normalized exact match** — case-insensitive, whitespace-stripped
   lookup against the labels the pipeline returned (`" cat "` → `"Cat"`).
2. **Fuzzy fallback** — `difflib.SequenceMatcher` string similarity
   (`_fuzzy_match_label`), full-match cutoff `0.6`; a substring/prefix
   match qualifies at cutoff `0.45` when the candidate is ≥ 3 characters
   (so placeholders like `"A"` never attach to a label). Example:
   `"indoor"` → `"indoor office"`.
3. **No match** — the candidate scores `0.0`.

**ML caveat:** the fuzzy fallback is *string* similarity, not semantic
similarity. A fuzzy-matched score means "confidence of the nearest
label *string*," which may be a different concept from what the user
typed.

### Pipeline behavior

- An already-loaded `Pipeline` is **reused**; the pipeline factory is
  never invoked per image (rebuilding would reload model weights per
  image and is treated as a test-visible error).
- `top_k` is derived from the model config's `num_labels` (fallback
  `10_000`) so the pipeline's default `top_k=5` truncation never hides a
  label the user asked about.

### Limits

- **Local provider only.** Cloud providers (Groq, OpenRouter, Ollama,
  Nvidia, Google AI, Cerebras, HF Inference API) do not run this pass.
- **`image-classification` models only.** A loaded pipeline with any
  other task raises `ValueError`; captioning/VLM models do not expose
  per-label probabilities.
- **Candidates must correspond to the model's label space.** A
  classification model can only score its own trained labels; arbitrary
  concepts score `0.0` or fail the run (see below).
- **Threshold semantics are separate from the global tag threshold.**
  The *Candidate Probability Threshold* (0.0–1.0, Local tab) filters the
  candidate score map. The *Confidence Threshold* on the main tagging
  step (1–100, `engine.confidence_threshold`) filters extracted
  LLM/classification tags. They are different knobs.
- **Scores are not a distribution over the candidate set** (see table
  above) — do not compare them as if they summed to one.

### Mismatch and failure behavior

| Stage | Behavior |
| :--- | :--- |
| **UI, config time** | The Local tab runs a pre-flight check (`summarize_candidate_compatibility`) comparing the candidate list to the model's cached `id2label` labels, and shows an amber warning when no candidate matches exactly, when some match only fuzzily, or when nothing matches. Exact matches show no warning. |
| **Runtime, all candidates unmatched** | `ValueError` is raised with the model's label sample and the full candidate list — never a silent all-zero map. In the pipeline this is caught and logged as a warning; `prob_dict` becomes `{}` and processing continues. |
| **Runtime, partial mismatch** | Unmatched candidates score `0.0`; matched ones score normally. No error. |
| **Runtime, non-classification pipeline** | `ValueError` ("requires an image-classification pipeline"); treated the same as above — probability pass skipped, flow continues. |
| **Probability-only mode with empty scores** | Falls back to LLM tagging instead of writing zero tags. |
| **Both / LLM mode with empty scores** | Normal LLM flow proceeds; results record `probabilities: {}`. |

### Logging and persistence

- Per image, one line per candidate is logged with PASS/FAIL against the
  threshold: `  A: 0.850 PASS`, `  B: 0.100 FAIL`, …
- A summary line is logged in probability-only mode:
  `Probability tagging: category=<top>, keywords=[…]`.
- The (threshold-filtered) map is stored per result as
  `session.results[i]["probabilities"]` for export.
- Settings persist via the normal engine config path
  (`probability_mode`, `probability_enabled`, `probability_candidates`,
  `probability_threshold`).

---

## Configuring it (UI)

- Step 2 → **Local Inference** tab → **Tagging Mode**: `LLM only`,
  `Probability only`, or `Both`.
- **Candidate Tokens**: comma/semicolon/newline separated; preloaded
  from the model's label set when one exists, with autocomplete over
  those labels.
- **Candidate Probability Threshold**: slider 0–100%; candidates below
  it are dropped from the stored/derived score map (`0.0` disables
  filtering).

## Configuration Persistence

- Settings are saved with the engine config (see `src/utils/config_manager.py`,
  default file `~/.synapic_v2_config.json`) and restored on restart.
  Legacy configs that only set `probability_enabled=True` load as mode
  `"both"`.
