# Changelog

All notable changes to the **Synapic** project will be documented in this file.

---

## [2.5.0] - 2026-08-17

### Added
- **Probability Scoring for Local Models**: Added calibrated per-label probability scores for local image-classification models, with Step 2 Local tab controls (enable toggle, candidate tokens, optional threshold) wired into the engine configuration and persisted to `~/.synapic_v2_config.json` across restarts.
- **Robust Candidate Matching**: Candidates are matched against the model's label set case-insensitively and whitespace-stripped, with a fuzzy fallback for close labels (e.g. `indoor` → `indoor office`); a candidate set that matches nothing now raises a clear error instead of silently reporting all-zero probabilities.
- **Probability Scoring Guide**: Added `docs/PROBABILITY_SCORING_TAGGING.md` documenting calibrated probability extraction from vision models, linked from the README.
- **Test Coverage**: Added unit, integration, and UI tests for the probability pipeline (loaded-pipeline reuse, extraction, candidate matching, config round-trip, and Local tab controls).

### Changed
- **Probability Pipeline Reuse**: Probability scoring now reuses the already-loaded pipeline instead of constructing a new one per image, eliminating per-image model reloads and the associated memory duplication; non-`image-classification` pipelines are rejected with a clear message.

### Fixed
- **Tag Extraction Regression**: `extract_tags_with_semantics` and the processing fallback path now unpack the new 4-value return of `extract_tags_from_result`, fixing a crash that broke tag extraction for all providers.
- **Save Config Persistence**: The Hugging Face and OpenRouter "Save Config" buttons now persist the engine configuration immediately, matching the other providers (previously they only updated the in-memory session and could be lost on close).

---

## [2.4.5] - 2026-08-03

> **Note:** 2.4.5 supersedes the earlier 2.4.0 draft entries for this release. The feature set is unchanged — 2.4.0 was a provisional version number used while the changelog was being assembled and should not be referenced.

### Added
- **Performance Benchmark Scripts**: Added `scripts/bench_dedup_binning.py` (dedup scan throughput) and `scripts/bench_parallel_tagging.py` (parallel vs sequential tagging with mocked API calls) for reproducible performance measurement.
- **New Unit Tests**: Added 31 tests covering the hash-binning dedup engine (verified against a brute-force all-pairs oracle at 95/90/75% thresholds) and `DaemonThreadPoolExecutor` `cancel_futures` semantics.
- **Real Engine Validation**: Implemented `Session.validate_engine` with per-provider checks (model required for all providers, downloaded model for local, API key for each cloud provider, host for Ollama) instead of the always-True stub, plus 7 new unit tests.
- **Paginated Dedup Reload**: The dedup base-query reload now paginates through Daminion instead of silently capping at 500 items, with live per-page progress updates.

### Changed
- **Dedup Engine Speedup**: Replaced the O(N²) pairwise hash comparison with hash binning (~4x fewer comparisons worst case, 100-1,000x+ on realistic collections), precomputed integer hashes with a fast `bit_count` popcount (4.6x faster per comparison), identical-hash collapsing, and an all-pairs fallback for very low thresholds.
- **Parallel Tagging**: Cloud providers (Groq, OpenRouter, Hugging Face, Google AI, NVIDIA, Cerebras, Ollama) now process items concurrently via `DaemonThreadPoolExecutor` (`PROCESSING_MAX_WORKERS`, default 4); local inference stays sequential. Counters and progress reporting are thread-safe and abort behavior is preserved.
- **Daminion API Efficiency**: Cached tag-value ID resolution (eliminating the per-keyword API-call storm) and switched the HTTP transport from `urllib` to a persistent `requests.Session` with a thread-safe rate limiter.
- **HTTP Session Reuse**: Hugging Face and OpenRouter providers now reuse a module-level `requests.Session`.
- **Resource Management**: Fixed a temporary-file disk leak for downloaded originals/previews, bounded per-endpoint latency samples, and moved per-image memory logging to DEBUG level.
- **Logging Refactors**: Replaced scattered debug `print()` calls with structured logger calls across the Daminion client, dedup engine, and Step 2/4 UIs, and narrowed broad `except` clauses.
- **Dependency Pinning**: Pinned previously unpinned dependencies and reconciled `requirements.txt` with `pyproject.toml`.
- **Docs Cleanup**: Removed README duplication and documented cloud API key configuration in `CONFIG.md`.
- **Developer Scripts**: Relocated dev scripts (`read_log.py`, `rewrite_step2.py`) under `scripts/` and removed an empty scratch file.
- **Daminion Check-in Comments**: `checkin_item`/`checkin` accept an optional comment, with graceful fallback when the server rejects check-in comments.

### Fixed
- **Temporary File Cleanup**: Downloaded Daminion originals/previews are now always removed, even when processing fails.
- **Concurrency Utilities**: `DaemonThreadPoolExecutor.shutdown()` is idempotent and honors `cancel_futures`; the Groq single-key path no longer serializes parallel workers; Cerebras SDK client creation is double-checked-locked.
- **Windows Icon & Title**: Replaced the fake PNG icon with a real ICO, corrected the window title, and set the Windows taskbar icon via `iconphoto` so it survives CustomTkinter's delayed default-icon override.
- **Dedup/Upscale Reliability**: Fixed refresh behavior, item limits, and cache cleanup in the dedup and upscale steps, and relabeled the keep-selection controls to "Select to keep".

### Performance
- **Dedup scans** (64-bit pHash, 95% threshold): 66x at 1,000 items, ~190x at 4,000, and ~0.7s for 64,000 items (vs ~17 minutes for the old all-pairs scan).
- **Tagging throughput** (32 items, 300ms API latency): 2.1x / 3.9x / 5.0x wall-clock speedup at 2 / 4 / 8 workers.

---

## [2.3.0] - 2026-03-19

### Added
- **Core AI Tagging Pipeline**: Added and expanded the main processing pipeline for AI-driven asset tagging, including stronger Daminion pagination support and deeper UI integration.
- **Cerebras Integration**: Added Cerebras inference support and updated project dependencies to support the new provider stack.
- **Additional AI Providers**: Added Google AI Studio (Gemini API), NVIDIA, and Ollama Cloud support, broadening available remote and hosted inference options.
- **Session and Workflow Management**: Introduced core session management, richer data source and AI engine configuration, and a new tagging workflow step for processing assets.
- **Persistent Model Filters**: Added persistent image-model filtering to provider model lists so vision-capable selections remain easier to manage across sessions.
- **Expanded Test Coverage**: Added unit tests for `load_image_from_base64`, `get_file_metadata`, `calculate_hamming_distance`, `are_hashes_similar`, `apply_keep_first`, concurrency behavior, UI flows, and pagination-related regressions.

### Changed
- **Engine Configuration UI**: Continued evolving the Step 2 engine configuration experience with better provider support, safer async model loading, and improved tab handling across providers.
- **Responsive Layout and Documentation**: Improved layout responsiveness in key screens and expanded inline code documentation and cleanup across the codebase.
- **Deduplication Workflow**: Enhanced deduplication with threaded progress reporting, metadata-aware behavior, delete-versus-remove controls, inline confirmations, and broader UX refinements.
- **Resource Management**: Optimized memory and CPU usage for local models, added per-image memory logging, and strengthened cleanup paths across API pipelines.

### Fixed
- **Engine Dialog Stability**: Fixed render issues after the Groq tab, prevented tab-navigation crashes between Groq and Ollama, and hardened async model loading across provider tabs.
- **Pagination Reliability**: Fixed early termination during auto-pagination when search results changed and corrected `single_page` handling in the Daminion client.
- **Processing Robustness**: Resolved an `UnboundLocalError` during abort handling and fixed the batch button state by correctly passing the `more_pages` flag.
- **Memory Leaks and Shutdown Issues**: Fixed multiple memory leak paths across processing pipelines, improved `pythonw` compatibility, and resolved lingering background-process and logging shutdown issues.
- **Provider-Specific Issues**: Fixed Groq API quota exhaustion handling, corrected Ollama Cloud authentication for base64 image uploads, filtered provider lists for vision models more accurately, and added the missing `os` import in `logger.py`.
- **Security Hardening**: Replaced unsafe `literal_eval` usage on untrusted model output.

---

## [2.2.0] - 2026-02-07

### Added
- **Groq Integration**: Added full support for the Groq SDK (`groq` python package) enabling high-speed inference with models like Llama 3 and Mixtral.
- **Unified Engine Configuration**: Completely redesigned the "Select Engine" dialog in Step 2 to be the central hub for all AI providers (Local, Hugging Face, OpenRouter, Groq).
- **Confidence Threshold Slider**: Implemented a configurable confidence threshold (1-100%) to filter out low-probability tags and categories from AI results.
- **Deduplication Engine**: Added a complete visual deduplication workflow (`StepDedup`) supporting perceptual hashing (pHash, dHash, etc.) to find and manage duplicate images in Daminion catalogs.
- **Process Management**: Added robust shutdown logic to ensure all background threads and processes are terminated when the application closes.

### Changed
- **Step 2 UI Overhaul**: Removed redundant "Groq Explorer" and standalone settings from the main wizard form, consolidating everything into the configuration dialog.
- **Model List Improvements**: Standardized the layout of model selection lists across all providers with consistent headers (Model ID | Capability | Cost/Size) and styling.
- **Configuration Persistence**: Optimized how API keys and engine settings are saved to `.synapic_v2_config.json`.

### Fixed
- **Daminion Search Limits**: Addressed issues where text-based searches were artificially limited to 500 items.
- **Groq API Compatibility**: Resolved issues with the Groq base URL and simplified the integration to focus on the official SDK.
- **Keyword Creation**: Fixed edge cases where existing keywords in Daminion were duplicates or not correctly identified.

---

## [2.1.0] - 2026-01-29

### Added
- **Comprehensive Documentation**: Implementation of the full documentation plan. Added module-level docstrings, class/method-level Google-style docstrings, and detailed inline comments across all 23 Python modules.
- **Enhanced Progress Tracking**: Integrated `GranularProgress` and `EnhancedProgressTracker` into the tagging engine for real-time, weighted progress reporting in the UI.
- **Improved UI Validation**: Red/Green status indicators for engine configuration to provide immediate feedback on API key or local model availability.

### Fixed
- **Daminion Metadata Write-back**: Added missing `update_item_metadata` method to `DaminionClient`, fixing a critical failure where AI results were not saved to the DAM.
- **Keyword Creation Logic**: Fixed issues in Daminion keyword creation where existing keywords were sometimes not correctly identified, leading to duplicate creation attempts or association failures.
- **Daminion Filter Counts**: Corrected the `get_filtered_item_count` logic to ensure accurate record counts are returned when complex filters (Keywords, Status, Date) are applied.
- **Model Download UI**: Fixed progress bar inaccuracies and added a cancel (Abort) capability during model downloads to prevent UI locks.

---

## [2.0.0] - 2026-01-18

### Added
- **Complete API Rewrite**: Replaced the legacy monolithic `daminion_client.py` with a modular, official-spec `DaminionAPI` wrapper.
- **New Sub-API Modules**:
  - `MediaItemsAPI`, `TagsAPI`, `CollectionsAPI`, `ItemDataAPI`, `SettingsAPI`, `ThumbnailsAPI`, `DownloadsAPI`, `ImportsAPI`, `UserManagerAPI`.
- **Type Safety**: 100% type hint coverage across core and utility modules.
- **Daminion Integration Guides**: Created comprehensive developer guides, quick reference sheets, and migration documentation.
- **Automated Testing**: Added a suite of 11 automated tests for the Daminion integration layer.
- **Working Examples**: Added `daminion_api_example.py` with 9 production-ready usage patterns.

### Changed
- **Log Location**: Moved log output from the user home directory (`~/.synapic/logs`) to the project root (`./logs/`) for easier developer access.
- **Architecture**: Moved from a monolithic client to a modular, sub-API based architecture.

### Fixed
- **Zero Results Bug**: Fixed a filtering issue that caused search results to be incorrectly dropped during processing.
- **Excessive Error Logging**: Reduced redundant Daminion connection errors from 20+ to 0-2 per session.
- **Endpoint Accuracy**: Re-based all network calls on official Daminion Server Web API specifications (fixing multiple 404 errors).

---

## [1.x] - Legacy Implementation

### Overview
- Original reverse-engineered integration with Daminion.
- Supported basic folder-based tagging.

### Known Limitations (Fixed in v2.0)
- Monolithic `daminion_client.py` (2,300+ lines).
- Frequent 404/500 errors due to unofficial endpoint usage.
- Lack of type safety and documentation.

---

## Status: Production Ready
**Current Version**: 2.5.0
**Last Updated**: 2026-08-17
