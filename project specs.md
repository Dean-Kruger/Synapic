The following project specification details the requirements for **Hugging Juice Face v2**, a desktop application for automated image tagging using various AI backends. This specification is designed to be a "blueprint" for a developer to build the application from scratch, utilizing the logic from the existing `deanable/hugging-juice-face` repository as a boilerplate for the backend functionality.

---

# Project Specification: Hugging Juice Face v2

## 1. Project Overview

**Goal:** Create a v2 iteration of the Hugging Juice Face application, rewriting the codebase from scratch to ensure modularity and maintainability. The core business logic (Daminion integration, AI tagging pipelines) remains consistent with the v1 repository, but the User Interface (UI) will be completely redesigned into a linear, 4-step workflow.

**Core Philosophy:**

* **Backend:** Reuse logic from `daminion_client.py`, `huggingface_utils.py`, `openrouter_utils.py`, and `image_processing.py`.
* **Frontend:** A clean, modern UI separated into 4 distinct, self-contained steps.
* **User Experience:** "Wizard" style or Tab-based navigation where the user configures the job sequentially before execution.

## 2. Technical Architecture

### 2.1 Tech Stack

* **Language:** Python 3.10+
* **GUI Framework:** `CustomTkinter` (recommended) or `PyQt6` for a modern, dark-mode friendly aesthetic, replacing the standard `tkinter` look.
* **Concurrency:** `asyncio` and `threading` for non-blocking UI during the "Process" step (referencing `daminion_async.py` and `gui_workers.py`).
* **Data Management:** `dataclasses` or `pydantic` for strict typing of configuration objects.

### 2.2 Application Structure

The code should follow a Model-View-Controller (MVC) or robust modular pattern:

* `/core`: Backend logic (API clients, image processing).
* `/ui`: UI components (Main window, Step frames, Dialogs).
* `/utils`: Helpers (Logging, Config management).

---

## 3. UI/UX Workflow: The 4 Steps

The main application window will host a navigation bar (top or side) indicating the 4 steps. Users proceed linearly.

### Step 1: Datasource

**Objective:** Define *where* the images are coming from.
**UI Elements:**

* **Source Selector:** A Radio Button or Dropdown to choose between:
* **Daminion Server**
* **Local Folder**



**Logic & Interaction:**

1. **Local Folder Mode:**
* **Input:** File path selector (Button: "Browse Folder").
* **Display:** Text field showing selected path.
* **Filter:** Checkboxes for file types (JPG, PNG, TIFF) - defaults inferred from `image_processing.py`.


2. **Daminion Server Mode:**
* **Connection Config:** Inputs for `Host`, `Username`, `Password`. (Load default from `config.py` if available).
* **Action:** "Connect" button.
* **Scope Selection (Post-Connect):**
* Dropdown: Select Catalog.
* Radio Buttons: `All Files`, `Current Selection`, `Specific Collection/Tag`.
* *Implementation Note:* Use `daminion_client.py` to authenticate and fetch available scopes.





### Step 2: Tagging Engine

**Objective:** Select and configure the AI model used for analysis.
**UI Elements:**

* **Engine Selector:** Large "Card" or Radio selection for:
* **Local Model**
* **Hugging Face**
* **OpenRouter**


* **Configuration Button:** A distinct "Configure [Selected Engine]" button.

**The "Configuration" Dialog (Modal Window):**

* **Layout:** A Tabbed Interface with 3 Tabs (one for each service).
* **Tab 1: Local Model**
* **Model Manager:** List of available models (e.g., facial recognition, object detection).
* **Actions:** "Download", "Load", "Clear Cache".
* **Status:** Indicators showing if the model is downloaded/ready (Reference `huggingface_utils.py` for local cache handling).


* **Tab 2: Hugging Face**
* **Input:** API Key field (masked).
* **Model ID:** Text field to specify the HF model string (e.g., `google/vit-base-patch16-224`).
* **Test:** "Verify Key" button.


* **Tab 3: OpenRouter**
* **Input:** API Key field (masked).
* **Model ID:** Dropdown or text field for OpenRouter model selection.
* **Prompt:** (Optional) Text area for custom system prompts if using LLMs for tagging.





### Step 3: Process (Execution)

**Objective:** Execute the tagging task and provide real-time feedback.
**UI Elements:**

* **Start/Stop Controls:** Big "Start Processing" button (Green) and "Abort" button (Red).
* **Progress Indicators:**
* **Granular Progress Bar:** Represents the batch (e.g., "Processing image 15 of 50").
* **Current Operation Label:** Dynamic text field updating rapidly (e.g., *"Uploading to API..."*, *"Parsing response..."*, *"Writing tags to Daminion..."*).
* **Console/Log View:** A scrolling text box showing detailed logs (Info/Error levels).


* **Logic:**
* Initialize the `ProgressTracker` (from `progress_tracker.py`).
* Run the processing loop in a separate thread to keep the UI responsive.
* Use `enhanced_progress.py` logic to calculate ETA and percentage.



### Step 4: Results & Review

**Objective:** Review the outcome and manage the session data. (This is the implied 4th self-contained step).
**UI Elements:**

* **Summary Dashboard:**
* **Metrics:** Total Processed, Successful, Failed, Skipped.


* **Review Grid:** A simple table listing:
* Filename
* Generated Tags
* Status (Success/Error)


* **Actions:**
* **"Export Report":** Save the session log/results to CSV/JSON (Reference `report_generator.py`).
* **"Open Log File":** Direct link to the `logs/` folder.
* **"New Session":** Button to reset the UI and return to Step 1.



---

## 4. Functional Requirements (Backend Mapping)

### A. Configuration Management

* **File:** `config_manager.py` / `config_schema.py`
* **Requirement:** The app must persist user settings (API keys, last used folder, Daminion credentials) to a local JSON/YAML file.
* **Security:** API keys must not be logged in plain text.

### B. Daminion Integration

* **Files:** `daminion_client.py`, `daminion_pool.py`
* **Requirement:**
* Implement connection pooling if processing >100 images.
* Implement a "Dry Run" mode where tags are fetched but not written back (optional toggle in Step 3).
* Ensure tag writing handles duplicates correctly.



### C. Image Processing Pipeline

* **File:** `image_processing.py`
* **Requirement:**
* Load image -> Resize/Format (if API requires) -> Send to Engine -> Parse Response -> Format Tags -> Return.
* Must handle timeouts (for API calls) and corrupt images gracefully without crashing the batch.



### D. Reporting

* **File:** `report_generator.py`
* **Requirement:** Automatically generate a timestamped report at the end of every Process run.

---

## 5. Development Phases

1. **Skeleton & UI:** Build the main window, the 4-step navigation, and the tabbed Configuration dialog using the chosen GUI framework.
2. **Core Logic Migration:** Port the Daminion and API client logic from the v1 repo into the new `core/` structure.
3. **Wiring:** Connect Step 1 inputs to the Daminion client. Connect Step 2 inputs to the AI Service factories.
4. **Process Loop:** Implement the async worker in Step 3 that orchestrates the flow.
5. **Testing:** Verify "Local" vs "API" modes independently.

## 6. Deliverables

* `main.py`: Entry point.
* `requirements.txt`: Updated dependencies.
* `/src`: Complete source code organized by module.
* `project specs.md`: This document.