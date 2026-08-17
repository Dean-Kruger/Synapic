# Synapic



**AI-Powered Image Metadata Tagging for Digital Asset Management**

Synapic automatically generates professional metadata (categories, keywords, and descriptions) for your image library using state-of-the-art AI models. Whether you're managing a personal photo collection or a professional DAM system, Synapic streamlines the tagging workflow with intelligent automation.

### Getting Started

Prerequisites
- Python 3.8+ (Windows/macOS/Linux)
- Optional GPU drivers if you plan to run local inference (CPU is supported)

### Automatic Launcher (Recommended for Windows)

The easiest way to run Synapic from source is using the included launcher script:
1.  Double-click `start_synapic.bat` in the root directory.
2.  The script will automatically:
    -   Check for Python (and offer to install it via Winget if missing).
    -   Create a virtual environment (`.venv`).
    -   Install/Update all dependencies from `requirements.txt`.
    -   Launch the application.

### Manual Installation
- Create a virtual environment:
  - Windows: python -m venv .venv
  - macOS/Linux: python3 -m venv .venv
- Activate the virtual environment:
  - Windows: .\.venv\Scripts\activate
  - macOS/Linux: source .venv/bin/activate
- Install dependencies:
  - pip install -r requirements.txt

Run
- Start the application:
  - Windows: python main.py
  - macOS/Linux: python3 main.py
- The GUI will launch. Use the wizard to:
  1) Select data source (local folder or Daminion DAM)
  2) Configure tagging engine (model, device, thresholds)
  3) Process images and view results

Testing & Packaging
- Run tests with pytest:
  - pytest tests
- Packaging with PyInstaller is supported via the main.spec file:
  - pyinstaller main.spec
- Note: Packaging artifacts (build/dist/release) are typically produced during the build process and should not be committed to source control.

Notes
- This repository uses a wizard-style UI built with CustomTkinter.
- The project includes heavy ML dependencies; ensure you have sufficient RAM/CPU/GPU resources as appropriate.

## Features

### 🤖 **Multi-Engine AI Support**
- **Local Models**: Run Hugging Face models locally with GPU acceleration
- **Cloud API**: Use OpenRouter's unified API for Gemini, Qwen, and other vision models
- **Groq Integration**: Leverage Groq's ultra-fast LPU inference engine for near-instant tagging
- **Flexibility**: Switch seamlessly between local privacy and cloud performance

### 📁 **Flexible Data Sources**
- **Folder Mode**: Process images from any local directory
- **Daminion DAM**: Direct integration with Daminion Digital Asset Management systems
  - Catalog-wide processing
  - Saved searches support
  - Shared collections integration

### ✨ **Intelligent Tagging**
- **Auto-Keywords**: Extract relevant tags from image content
- **Categorization**: Assign broad categories automatically or via zero-shot classification
- **Descriptions**: Generate detailed captions for image context

### 🔍 **Duplicate Elimination**
- **Visual Deduplication**: Find exact and similar images using perceptual hashing (pHash, dHash, etc.)
- **Smart Selection**: Auto-select duplicates to keep based on size, date, or quality.
- **Daminion Sync**: Tag duplicates or remove them directly from your catalog.

### 💾 **Professional Metadata Writing**
- **IPTC Standard**: Keywords, categories, and captions written to IPTC fields
- **EXIF Support**: Metadata embedded in standard EXIF fields for maximum compatibility
- **Non-Destructive**: Preserves existing metadata while adding new AI-generated tags

### 🎨 **User-Friendly Interface**
- Wizard-style workflow (Datasource → Engine → Process → Results)
- Real-time progress monitoring with detailed logging
- Model download manager with progress tracking
- Dark mode UI with modern CustomTkinter design

## Download

Get the latest Windows executable from the [Releases page](https://github.com/deanable/Synapic/releases).

No installation required—just download and run!

## Quick Start

1. **Launch Synapic** (or run `python main.py` from source)
2. **Select Datasource**: Choose a folder or connect to Daminion
3. **Configure Engine**: Pick an AI model (local or cloud)
4. **Process Images**: Start batch tagging with real-time progress
5. **Review Results**: Export or commit metadata to your files/DAM

## System Requirements

- **OS**: Windows 10/11 (x64)
- **RAM**: 4GB minimum, 8GB+ recommended for local models
- **GPU**: Optional but recommended for local model acceleration (CUDA-compatible)
- **Python** (if running from source): 3.10+

## Configuration

### API Keys (Optional)
For cloud-based AI models:
- **OpenRouter**: Get a free API key at [openrouter.ai](https://openrouter.ai)

Configure in the application settings or via environment variables.

Groq Integration
-----------------
- Synapic includes native support for the Groq Python SDK.
- Configure via **Step 2: Select Engine -> Groq Tab**:
  - Enter your Groq API Key (get one at [console.groq.com](https://console.groq.com))
  - Browse and select from available vision-capable models (e.g., Llama 3).
- Settings are persisted to the `.synapic_v2_config.json` file in your user home directory.
- Environment variable `GROQ_API_KEY` is also supported for headless/automated runs.

### Daminion Connection
- Server URL (e.g., `http://yourserver.com/daminion`)
- Username and password
- Catalog selection

## Supported AI Models

### Local Models (via Hugging Face)
### Recommended Models (Tested & Verified)

For the best results, we recommend downloading the following models for local use:

| Task | Recommended Model | Description | Size |
| :--- | :--- | :--- | :--- |
| **Description** | `Salesforce/blip-image-captioning-base` | Best general-purpose captioning. Good balance of speed and detail. | ~1GB |
| **Description** | `Salesforce/blip-image-captioning-large` | Higher quality descriptions at the cost of being slower. | ~2GB |
| **Keywords** | `google/vit-base-patch16-224` | Excellent for tagging objects and scenes (ImageNet-21k classes). | ~340MB |
| **Keywords** | `microsoft/resnet-50` | Faster, lightweight alternative for standard object tagging. | ~100MB |
| **Categorization** | `openai/clip-vit-base-patch32` | Zero-shot classification. Matches images to your *exact* category names. | ~600MB |
| **Categorization** | `openai/clip-vit-large-patch14` | Higher accuracy zero-shot classification for nuanced categories. | ~1.7GB |

### Groq Models (Ultra-Fast)
- **Llama 3 Vision**: High-performance multimodal model optimized for Groq LPUs.
- **Mixtral 8x7B (v0.1)**: Powerful mixture-of-experts model for complex descriptions.

### Cloud Models (via OpenRouter)
- **Google Gemini 2.0 Flash**: Fast, free, and multimodal.
- **Qwen VL Max**: State-of-the-art open visual language model.
- **Nvidia Nemotron Vision**: Optimized for high-fidelity visual understanding.

## Technology Stack

- **UI Framework**: CustomTkinter (modern, responsive, dark-mode-first UI)
- **Concurrency**: Multi-threaded backend with `ProcessingManager` loop orchestration
- **AI Integration**: Hugging Face Transformers & OpenRouter REST gateway
- **Metadata**: piexif (EXIF), iptcinfo3 (IPTC keywords/caption)
- **DAM Integration**: Official Daminion REST API with retry/masking logic
- **Build**: PyInstaller for Windows executable generation

## Development

### Running from Source

```bash
# Clone the repository
git clone https://github.com/deanable/Synapic.git
cd Synapic

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### Building Executable

```bash
# Build with PyInstaller
pyinstaller main.spec

# Output will be in dist/Synapic/
```

The GitHub Actions workflow automatically builds executables on every push to `main`.

## Philosophy & Workflow

Synapic iterates on traditional tagging workflows by providing a linear, 4-step "Wizard" experience:

1.  **🚀 Step 1: Datasource**: Connect to your Daminion server or a local image folder. Supports advanced filtering by status (flags), untagged fields, and specific catalog scopes.
2.  **🤖 Step 2: Tagging Engine**: Choose your intelligence. Run local models via Hugging Face for privacy, or use cloud-based VLMs via OpenRouter for state-of-the-art accuracy.
3.  **⚙️ Step 3: Process**: Execute the batch job with real-time feedback, multithreaded logging, and granular progress monitoring.
4.  **📊 Step 4: Results**: Review your new metadata, verify successful writes to the DAM, and export session reports.

**Probability Scoring (Local Models)**
- When using a local image-classification model in Step 2, pick a **Tagging Mode**: **LLM only**, **Probability only**, or **Both**.
- **Probability only** tags assets directly from the model's per-label confidence scores — the top-scoring candidate becomes the category and every candidate passing the threshold becomes a keyword — without running captioning inference.
- **Both** runs the normal LLM/captioning flow and adds the same per-label scores alongside it.
- Candidate tokens preload automatically from the selected model's label set, so there's no need to type them by hand.
- The acceptance threshold is a **Less strict → Strict** slider (0–100%), and during processing the log lists each candidate's score with a **PASS/FAIL** verdict against it.

**Bonus: Deduplication Wizard**
- A dedicated workflow step to scan collections for visual duplicates, review matches side-by-side, and apply bulk actions (Tag or Delete).

## Documentation

Comprehensive documentation is available for both users and developers:
- **[DEVELOPER_GUIDE.md](docs/developer/DEVELOPER_GUIDE.md)**: Technical architecture and subsystem overview.
- **[CHANGELOG.md](CHANGELOG.md)**: Detailed version history and fix summaries.
- **[CONTRIBUTING.md](CONTRIBUTING.md)**: Standards for code, documentation, and PRs.
- **[PROBABILITY_SCORING_TAGGING.md](docs/PROBABILITY_SCORING_TAGGING.md)**: Guide to extracting calibrated probability scores from vision models.

### Knowledge Base (docs/)
- **[Threshold Features](docs/features/THRESHOLD_FEATURE.md)**: Tuning AI confidence levels.
- **[Daminion API Detail](docs/api/DAMINION_API_REFERENCE.md)**: Complete method reference.
- **[Daminion API Guide](docs/api/DAMINION_API_GUIDE.md)**: Logic and migration guide.
- **[Daminion API Quick Ref](docs/api/DAMINION_API_QUICK_REFERENCE.md)**: Common code snippets.
- **[Daminion Debugging](docs/api/DAMINION_API_DEBUGGING.md)**: Troubleshooting connection issues.

## Contributing

Contributions are welcome! Please see the [CONTRIBUTING.md](CONTRIBUTING.md) for details on our coding standards and how to submit pull requests.

## Version History

### [1.1.0] - 2026-01-28
#### Added
- **Automatic Process Termination**: Added robust logic to ensure all Python processes are killed when the GUI is closed.
  - Implemented `ProcessingManager.shutdown()` for graceful background thread termination.
  - Added `Step3Process.shutdown()` to UI wizard steps.
  - Enhanced `App.on_close()` to orchestrate a clean shutdown sequence.
  - Added explicit `sys.exit(0)` to `main.py` to prevent zombie processes.
- **GitHub Download Support**: Added capability to download the repository directly from the launcher.

## License

Proprietary. All rights reserved.

## Credits

Developed by **Dean** for professional digital asset management workflows.

---

**Need Help?** Check the documentation or open an issue on GitHub.
