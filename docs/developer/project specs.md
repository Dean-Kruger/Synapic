# Project Specification: Synapic (v2)

## 1. Project Overview

**Goal:** Synapic is a high-performance desktop application for automated image tagging and metadata enrichment. It provides a bridge between Digital Asset Management (DAM) systems (specifically Daminion) and state-of-the-art AI models (Local VLMs, Hugging Face, OpenRouter).

**Core Philosophy:**
*   **Linear Workflow:** A 4-step "Wizard" interface that guides users from source selection to execution and result review.
*   **Deep Daminion Integration:** Beyond simple fetching, Synapic utilizes Daminion's internal schema for advanced filtering (flags, status) and provides high-speed metadata write-back via the Web API.
*   **Engine Versatility:** Supports local inference for privacy/speed and cloud inference for cutting-edge model access (GPT-4o, Gemini, Qwen2-VL).

---

## 2. Technical Architecture

### 2.1 Tech Stack
*   **Language:** Python 3.10+
*   **GUI Framework:** `CustomTkinter` for a modern, responsive, dark-mode first aesthetic.
*   **Concurrency:** Multi-threaded backend using `threading` and `queue`. A dedicated `ProcessingManager` handles the execution loop while keeping the UI responsive.
*   **API Interactions:** Native `urllib` and `requests` for robust network operations with custom retry logic and rate limiting.

### 2.2 Core Modules
*   `src/core/daminion_client.py`: Advanced Daminion Web API client with tag mapping (GUID/ID) and batch update capabilities.
*   `src/core/processing.py`: Orchestrates the movement of data from source to engine and back to destination.
*   `src/core/huggingface_utils.py`: Manages local model lifecycle (download, cache scanning, inference pipelines).
*   `src/core/session.py`: Persistent session state and configuration using `dataclasses`.
*   `src/ui/steps/`: Self-contained UI frames for each stage of the workflow.

---

## 3. UI/UX Workflow: The 4 Steps

### Step 1: Datasource
**Objective:** Define the scope of assets to be processed.
*   **Source Types:**
    *   **Local Folder:** Recursive or shallow scans of image directories.
    *   **Daminion Server:** Interactive connection manager with credential persistence.
*   **Advanced Daminion Filters:**
    *   **Tabbed Scopes:** "All Items", "Saved Searches" (Dynamic ID/Name mapping), "Shared Collections".
    *   **Status Filtering:** Filter by Daminion flags (Flagged, Rejected, Unflagged).
    *   **Metadata Check (Untagged):** Precision targets for files missing specific fields (**Category**, **Keywords**, or **Description**).
    *   **Record Limits:** Configurable "Max Items to Process" (0 for unlimited catalog scan).

### Step 2: Tagging Engine
**Objective:** Configure the AI analysis pipeline.
*   **Engine Options:**
    *   **Local Inference:** Uses Hugging Face `transformers` pipelines. Supports standard classifiers and modern Vision-Language Models (VLMs).
    *   **Hugging Face API:** Cloud inference for lighter hardware.
    *   **OpenRouter API:** Access to diverse LLM/VLM backends with custom system prompts.
*   **Specialized Handling:**
    *   **VLM Mode:** Automatic detection of `image-text-to-text` capabilities (e.g., Qwen2-VL) for descriptive captioning.
    *   **Zero-Shot Classification:** Custom candidate labels for broad categorization.

### Step 3: Process (Execution)
**Objective:** Real-time visibility into the tagging job.
*   **Controls:** Start/Start and Abort buttons with immediate state locking of previous steps to prevent configuration drift during runs.
*   **Feedback Loop:**
    *   **Live Console:** Detailed operation log showing API responses and file paths.
    *   **Progress Dashboard:** Cumulative counters (Success/Fail/Total) and a dynamic progress bar fueled by `EnhancedProgress` calculations.

### Step 4: Results & Review
**Objective:** Post-job analysis and reporting.
*   **Outcome Dashboard:** Final tally of successful tagging operations vs. failures.
*   **Result Table:** Persistent view of generated tags (Category, Keywords, Description) for the current session.
*   **System Integration:** "Open Log Folder" for deep-dive debugging.

---

## 4. Functional Requirements

### A. Daminion Sync Logic
*   **Tag Mapping:** The client MUST fetch the Daminion Layout at session start to map human-readable tags to internal GUIDs/Integer IDs.
*   **Persistent Fetching:** The system scans the catalog in batches, filtering locally until the user-defined `max_items` quota is met.
*   **Write-back:** Tags are committed back to Daminion via specialized batch update endpoints to minimize network overhead.

### B. Metadata Standards
*   **Local Files:** Supports writing IPTC (Object Name, Keywords, Caption) and EXIF (XPSubject, XPKeywords, ImageDescription/XPTitle) to ensure compatibility across Windows and DAM software.
*   **Format Support:** Optimized for JPG, PNG, and TIFF.

### C. Resource Management
*   **Memory Safety:** Thumbnails are downloaded to a temporary cache and cleaned up immediately after processing.
*   **Model Caching:** Local models are stored in a central cache; the app calculates model sizes and provides management tools (Clear Cache).

---

## 5. Directory Structure
```
/
├── main.py                 # Application launcher
├── project specs.md        # This document
├── requirements.txt        # Runtime dependencies
├── schema.sql              # Daminion DB reference
└── src/
    ├── core/               # Business logic & clients
    ├── ui/                 # View components
    └── utils/              # Config, Logging, UI Helpers
```