# Arbitrary-User-Keyword Scoring — Design

**Status:** core implemented (`src/core/keyword_scoring.py`); tier adapters
implemented (`src/core/keyword_scoring_adapters.py`), including tier 2.5
(CLIP-style embedding); tier-1 cloud clients (chat endpoints returning token
logprobs) remain the integration work.

This is the design for scoring an **arbitrary user-supplied keyword list**
against each image — a genuinely harder problem than the existing candidate
pass, which only works when the user's tokens happen to match a local
classification model's trained labels (`docs/PROBABILITY_SCORING_TAGGING.md`).

The governing rule:

> **Every score carries an explicit tier. Downstream code must be able to tell
> calibrated evidence from approximations without guessing.**

---

## 1. Tier ladder

At inference time the scorer picks the highest available tier. The tier is
recorded on every result (`ScoreResult.tier`, `ScoreResult.calibrated`).

| Tier | Mechanism | When available | Calibration | Candidates may be arbitrary? |
| :--- | :--- | :--- | :--- | :--- |
| **1 — `logprob`** | Prompted VLM/LLM classifies the image against the candidates in one call; the first output token's top logprobs are softmaxed over the candidate set. | Provider returns token logprobs. **Wired**: Groq (`GroqPackageClient.chat_with_image_logprobs`) and OpenRouter (`OpenRouterClient.chat_with_image_logprobs`) send `max_tokens=1` with `logprobs=True` and return the first token's top alternatives; a `None` response (SDK/model without logprob support) degrades to tier 3. | **Calibrated** — a true probability distribution over the candidate set (sums to 1.0). | Yes — any user keywords. |
| **2 — `label_confidence`** | Existing local path: `image-classification` pipeline's per-label confidence for the model label each candidate matched (exact or fuzzy). | Local provider + classification model whose label space overlaps the candidates. | **Not calibrated** — relative confidences over the *model's* label space; the user-visible map does not sum to 1.0. | No — must correspond to model labels. |
| **2.5 — `embedding`** | CLIP-style cosine similarity between the image embedding and each candidate *text prompt* embedding (`TransformersCLIPScorer`, `openai/clip-vit-base-patch32`, lazy-loaded and reused), softmaxed over the candidate set with temperature 0.01. | Local provider with a classification model when tier 2 fails (candidates outside the label space) — the semantic rescue for arbitrary keywords without loading a chat model. **Opt-in** via `embedding_rescue_enabled` (Local tab checkbox). | **Not calibrated** — see the dedicated caveats section below; sums to 1.0 but is relative to the candidate set. | Yes — any user keywords, as free-form prompts. |
| **3 — `semantic_json`** | Prompted VLM returns JSON probabilities for each candidate; payload is clamped to [0,1] and renormalized to sum to 1.0 (`normalize_json_probabilities`). | Any provider that can caption the image (all cloud providers in this app) and logprobs are unavailable. | **Not calibrated** — model self-reported; normalized but reflects subjective confidence. | Yes — any user keywords. |
| **0 — `unavailable`** | Scoring could not run (no provider, inference failure). Explicit result with all candidates unmatched at 0.0 (`unavailable_result`), never a silent empty map. | — | No | — |

Tier selection order: **1 → 2 → 3 → 0**, gated by provider:

```
local + image-classification pipeline
    └─ tier 2 (current behavior; tier 1 only if the local VLM path is used)
cloud VLM/LLM provider (groq_package, openrouter, ollama, nvidia, google_ai, cerebras, huggingface)
    ├─ provider supports token logprobs  → tier 1 (groq_package and openrouter
    │   are wired via chat_with_image_logprobs; the rest degrade to tier 3
    │   until they grow logprob support)
    └─ otherwise                          → tier 3 (JSON fallback)
any provider, scoring call fails          → tier 0, pipeline continues
```

Note: tier 3 requires a *vision* model. For local classification-only setups,
tier 2 was historically the ceiling; tier 2.5 now rescues arbitrary
candidates when tier 2's label-space check fails, without requiring a chat
model on the local path.

---

## 2. Prompt standards (tier 1 and tier 3)

### Tier 1 — single-token classification with logprobs

Reuse the Method 1 prompt standard verbatim from
`docs/PROBABILITY_SCORING_TAGGING.md`:

- One option per candidate, lettered or keyed by the candidate string itself.
- "Respond with ONLY the single option token. Do not include any other text."
- API call: `logprobs=True`, `top_logprobs=max(len(candidates), 20)`,
  `max_tokens=1`.
- Parsing rules (all checklist items from the existing doc apply):
  case-insensitive, whitespace-stripped token comparison; candidates missing
  from `top_logprobs` map to `-inf`; `softmax_from_logprobs()` then produces
  the calibrated distribution, including the uniform fallback when the model
  picked a token outside the candidate set.

**Long-candidate caveat:** tokenization may split a multi-word candidate
("indoor office") across several tokens. When a candidate is not a single
token, tier 1 must fall back to first-token *letter* keys (`A`, `B`, `C`) and
the score attaches to the letter→candidate mapping. The core module is
agnostic to this — the adapter supplies `logprob_map` keyed by whatever the
prompt used.

### Tier 3 — JSON probability fallback

Reuse the Method 2 prompt standard: per-candidate float in [0, 1], sum must
equal 1.0, JSON only, no markdown. Parse with the project's existing
`src/utils/json_utils.extract_dict_from_text` (fenced-block and truncated-JSON
repair already handled there), then pass through
`normalize_json_probabilities()`, which clamps and renormalizes whatever the
model actually returned.

Prompt must include the full candidate list verbatim; adapter matches JSON
keys back to candidates case-insensitively and marks unreturned candidates
unmatched (`match_type="none"`, score 0.0) — a missing key is *not* the same
as a score of zero claimed by the model.

---

## 3. Score semantics and calibration rules

The result contract makes calibration non-negotiable and explicit:

- `ScoreResult.calibrated is True` **only** for tier 1. Only that tier's
  scores form a probability distribution over the candidate set.
- Tiers 2 and 3 report `calibrated=False`. Tier 3 values sum to 1.0 after
  normalization, but sum-to-one is a *formatting* property, not calibration.
- **Cross-tier comparison is forbidden.** A 0.85 from tier 1 and a 0.85 from
  tier 2 are different quantities. Anything that displays or stores scores
  (results table, CSV export, Daminion write) must include the tier string
  (`to_plain_dict()` already emits it).
- **Thresholds are tier-scoped** (next section) precisely because of this.
- No temperature scaling, Platt scaling, or per-class reliability calibration
  is claimed anywhere. If true calibration is ever wanted, it is a measured,
  validation-set-driven project on top of tier 1 — not a flag to flip.

Derived-tag rules (probability-only tagging mode), by tier:

- **Tier 1:** top-scoring candidate → category; all candidates passing the
  threshold → keywords. Safe: scores are comparable within the set.
- **Tier 2:** unchanged from current behavior (top candidate → category;
  threshold-passing → keywords), with the standing caveat that scores are
  label confidences, not a distribution.
- **Tier 3:** same derivation as tier 1, but the summary log line and results
  entry must carry the `semantic_json` tier label so a reviewer knows the
  category came from self-reported scores.
- **Tier 0:** no derived tags; item falls through to the normal LLM flow
  (existing "falling back to LLM tagging" behavior).

---

### Tier 2.5 calibration caveats (CLIP-style similarity)

Tier 2.5 deserves its own warnings because it *looks* more principled than
tier 3 while being less trustworthy in absolute terms:

- **Candidate-set dependence (the big one).** The softmax distribution is
  computed over the candidate set actually supplied. Adding a nonsense
  distractor like "wallpaper" absorbs probability mass and shifts every
  remaining score for the *same image*. Two runs that differ only in the
  candidate list are not comparable. This is tested explicitly
  (`test_similarity_candidate_set_dependence_is_real`).
- **Narrow raw-similarity band.** CLIP image-text cosine similarities for
  real images concentrate roughly in [0.2, 0.35]; raw values are a poor
  absolute signal. The fixed temperature (0.01) amplifies within-set
  differences into a decisive distribution, but it does not make the
  absolute values meaningful across sets.
- **Raw cosine values are the cross-run signal.** ``TransformersCLIPScorer``
  computes genuine cosine similarities from L2-normalized raw image and
  text embeddings (not the pipeline's logit-scale-folded scores), and the
  adapter records them per candidate in the result notes. Unlike the
  softmax distribution, these values are independent of the other
  candidates and are the comparable measurement across runs.
- **Prompt phrasing matters.** CLIP scores text prompts, not concepts:
  "a photo of a cat" vs "cat" vs "feline" can shift scores materially, and
  candidates are used verbatim as prompts.
- **Known CLIP biases.** CLIP has documented weaknesses on counting,
  negation, fine-grained texture/colour distinctions, and rare-domain
  images; scores for such content can be confidently wrong.
- **`calibrated=False` is deliberate** even though the values sum to 1.0:
  sum-to-one is a formatting property of the softmax, not evidence of
  calibration. Only rank ordering within a single candidate set is a
  defensible signal, so absolute thresholds tuned on other tiers must not
  be applied to embedding scores.

## 4. Thresholding

Two existing thresholds keep their distinct meanings; the design adds no new
slider.

| Threshold | Scope | Scale | Applies to |
| :--- | :--- | :--- | :--- |
| `engine.confidence_threshold` | Global tag filter (main Step 2 slider) | 1–100 | LLM/caption-extracted tags. **Not** the keyword-scoring map. |
| `engine.probability_threshold` | Candidate Probability Threshold (Local tab) | 0.0–1.0 | The keyword score map, via `apply_threshold()` (inclusive; 0.0 disables). |

Tier-specific threshold guidance:

- **Tier 1:** the slider is meaningful as-is. A candidate passing the
  threshold is genuinely "≥ X% of the posterior mass".
- **Tier 2:** scores are label confidences under the model's softmax; they
  are heavily mass-concentrated. The current default (0.0, no filter) is
  correct; values above ~0.5 will usually pass only the top label.
- **Tier 3:** models' self-reported numbers cluster badly (all-near-1.0 or
  all-near-0.0). Renormalization fixes the sum but not the *spread*. The
  default should stay 0.0, and the UI should note that thresholding
  self-reported scores is weak evidence.

`apply_threshold` is deterministic and shared by all tiers, so the stored map
in `session.results[i]["probabilities"]` is always the post-threshold map —
same contract as today.

---

## 5. Mismatch and failure behavior

The existing local path's hard-won rules generalize unchanged:

| Situation | Behavior |
| :--- | :--- |
| Candidate set empty | `{}` immediately; no inference call. |
| Tier 1: model's first token outside the candidate set | Uniform distribution over candidates + a note on the result; **never** a silent all-zero map. |
| Tier 2: no candidate matches any model label | `ValueError` with the model's label sample and the candidate list (current behavior, preserved). Pipeline catches it → tier 0 result → flow continues. |
| Tier 2: partial mismatch | Unmatched candidates: 0.0, `matched=False`, `match_type="none"`. Matched ones score normally. |
| Tier 3: JSON keys missing for some candidates | Missing keys → unmatched (0.0). Returned keys → clamped + renormalized. A parse failure of the whole payload → tier 0. |
| Tier 3: model claims values outside [0,1] or sum ≠ 1.0 | Clamped and renormalized (`normalize_json_probabilities`); a note is appended. |
| Any tier: inference raises | Tier 0 result (`unavailable_result` with the reason); item continues through the normal tagging flow. This is the existing "hide on failure" requirement. |
| Probability-only mode ends up tier 0 | Fall back to LLM tagging (existing behavior). |

**UI-time mismatch early warning (already shipped for tier 2):** the Local
tab's `summarize_candidate_compatibility` check flags candidate sets that
don't match the model's label space before any batch runs. Cloud providers
accept arbitrary candidates by construction (tiers 1/3), so they need no such
gate — but the UI should still render the tier badge next to the results so
users know which kind of number they are looking at.

---

## 6. Integration plan

Wire order keeps each step shippable and testable in isolation:

1. **Adapters** (`src/core/keyword_scoring_adapters.py`):
   - `score_keywords_local_label_confidence(pipe, image_path, candidates)` —
     thin wrapper delegating to the existing `run_local_logprob_inference`,
     reusing its reuse-pipeline guarantee and `_fuzzy_match_label`, then
     packaging into `build_score_result(..., SCORING_TIER.LABEL_CONFIDENCE)`
     with exact/fuzzy/none match types.
   - `score_keywords_logprob(provider_client, image_path, candidates)` —
     Method 1 prompt + logprob extraction + `softmax_from_logprobs`.
   - `score_keywords_semantic_json(provider_client, image_path, candidates)` —
     Method 2 prompt + `extract_dict_from_text` + `normalize_json_probabilities`.
2. **Selector:** `pick_scoring_tier(engine) -> tier or None`, implementing the
   ladder in §1. `None`/unavailable → tier 0 result, never an exception.
3. **ProcessingManager wiring:** replace the current `prob_dict` block in
   `_process_single_item` with a call that produces a `ScoreResult`, then:
   - keep the PASS/FAIL log lines (formatting unchanged),
   - store `result.to_plain_dict()` under a new `scoring` key in the session
     result entry while **keeping** the legacy `probabilities` key (score map
     after threshold) so the Step 4 export and existing tests stay valid,
   - in probability-only mode, derive `cat`/`kws` per the §3 rules.
4. **UI:** the Local tab keeps its existing controls (tier 2 is its only
   option today); cloud provider tabs surface a read-only tier badge in the
   results view rather than new controls.
5. **Config:** no new persisted fields. `probability_mode` /
   `probability_enabled` / `probability_candidates` / `probability_threshold`
   keep their meanings; the tier is runtime state, not config.

---

## 7. What this design deliberately does *not* do

- **No claim of calibrated scores outside tier 1.** No temperature/Platt
  scaling, no calibration curves, no "confidence %" relabeling of tier 2/3
  numbers.
- **No semantic embedding fallback in v1.** ~~A "score my arbitrary word
  against this image" embedding path (CLIP-style text/image similarity) is a
  plausible tier 2.5, but it introduces a second model and its own
  calibration problem; this design leaves it as future work rather than
  smuggling it in behind the JSON fallback.~~ **Implemented as tier 2.5**
  (`score_keywords_embedding` + `TransformersCLIPScorer`), strictly scoped:
  it rescues failed tier-2 runs on the local path (candidates outside the
  classification label space), never replaces tier 2 when it succeeds, and
  carries its own calibration caveats above. Cloud engines never use it
  (they have tier 1/3). The rescue is **user opt-in** via the Local tab's
  "Rescue unmatched candidates with CLIP similarity" checkbox,
  persisted as ``EngineConfig.embedding_rescue_enabled``; engines whose
  configs predate the flag are treated as opted-out, so existing setups
  never gain a surprise ~600MB download.
- **No silent degradation.** Every downgrade (tier 1 → 3 → 0) is recorded on
  the result and visible in logs/export.
- **No cross-tier score reuse.** Cached scores from one tier are never mixed
  into another tier's distribution.
