# Changelog

All notable changes to the **Synapic** project will be documented in this file.

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

## Status: ✅ Production Ready
**Current Version**: 2.1.0
**Last Updated**: 2026-01-29
