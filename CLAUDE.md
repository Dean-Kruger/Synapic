# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Synapic is an AI-powered image metadata tagging application for digital asset management. It generates categories, keywords, and descriptions for images using local or cloud AI models, with integration for Daminion DAM systems.

Key features:
- Wizard-style UI workflow (Datasource → Engine → Process → Results)
- Multiple AI engines: Local (Hugging Face), OpenRouter, Groq
- Daminion DAM integration for catalog-wide processing
- Visual deduplication using perceptual hashing
- Metadata writing to IPTC/EXIF standards
- Built with CustomTkinter, Python 3.8+

## Development Setup

### Prerequisites
- Python 3.8+ (3.10+ recommended)
- Git
- Optional: GPU drivers for local model acceleration

### Environment Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/deanable/Synapic.git
   cd Synapic
   ```

2. Create and activate virtual environment:
   ```bash
   # Windows
   python -m venv .venv
   .\.venv\Scripts\activate
   
   # Linux/macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. For development, install test dependencies:
   ```bash
   pip install pytest pytest-cov
   ```

### Running the Application
- GUI mode (default): `python main.py`
- Headless mode: `python main.py --no-gui`
- Force GUI: `python main.py --gui`

### Building Executable
```bash
pyinstaller main.spec
```
Output appears in `dist/Synapic/`. GitHub Actions automates builds on pushes to `main`.

## Common Commands

| Command | Description |
|---------|-------------|
| `python main.py` | Launch Synapic GUI |
| `python main.py --no-gui` | Run in headless mode (exits after init) |
| `pytest tests/` | Run all unit tests (recommended) |
| `pytest tests/ --cov=src` | Run tests with coverage report |
| `python -m unittest discover tests/` | Run tests via unittest framework |
| `pyinstaller main.spec` | Build Windows executable |
| `python scripts/update_deps.py` | Update dependencies (if script exists) |
| `start_synapic.bat` | Windows launcher (auto-installs Python/venv) |

### Running Specific Tests
- Single test file: `pytest tests/unit/test_config.py -v`
- Specific test class: `pytest tests/integration/test_daminion_api.py::TestDaminionAPI::test_auth_success -v`
- Single test method: `pytest tests/unit/test_config.py::TestConfig::test_load_defaults -v`

### Linting and Formatting
The project uses Ruff for linting (via pre-commit). To run manually:
```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run all hooks
pre-commit run --all-files

# Or run Ruff directly
ruff check src/
ruff format --check src/
```

## Code Architecture

### High-Level Structure
```
Synapic/
├── main.py                 # Application entry point
├── src/                    # Source code
│   ├── core/               # Core logic (processing, AI engines, DAM integration)
│   │   ├── processing.py   # Tagging pipeline orchestration
│   │   ├── session.py      # Centralized session state management
│   │   ├── daminion_api.py # Low-level Daminion REST API wrapper
│   │   ├── daminion_client.py # High-level Daminion integration
│   │   ├── huggingface_utils.py # Local HF model inference
│   │   ├── openrouter_utils.py # OpenRouter cloud API
│   │   └── dedup/          # Deduplication subsystem
│   ├── integrations/       # AI provider clients (Groq, Cerebras, NVIDIA, etc.)
│   ├── ui/                 # CustomTkinter-based wizard interface
│   │   ├── app.py          # Main application window
│   │   └── steps/          # Wizard steps (datasource, engine, process, results)
│   └── utils/              # Utilities (logging, config, concurrency, helpers)
├── tests/                  # Test suite (unit/integration/manual)
├── docs/                   # Documentation (developer guide, API references)
├── requirements.txt        # Python dependencies
├── main.spec               # PyInstaller build specification
└── start_synapic.bat       # Windows launcher script
```

### Key Architectural Patterns

1. **Wizard Workflow**: 
   - Strict 4-step linear flow managed by `src.ui.app.App`
   - Each step is a `CustomTkinter.CTkFrame` in `src/ui/steps/`
   - State flows via centralized `Session` object (`src.core.session`)

2. **Session Management**:
   - `Session` class holds all configuration and state
   - Passed between UI steps and processing engine
   - Persists to `~/.synapic_v2_config.json` via `src.utils.config_manager`

3. **AI Engine Strategy**:
   - Strategy-like pattern for different providers
   - Local: `src.core.huggingface_utils` (direct Transformers/Torch)
   - Cloud: `src.core.openrouter_utils` (REST API)
   - Specialized: `src.integrations.*` (Groq, Cerebras, etc.)
   - Engine selected in Step 2 of wizard

4. **Tagging Pipeline** (`src.core.processing`):
   - Item fetching from datasource (folder/Daminion)
   - Image validation (format/dimensions)
   - AI inference (selected engine)
   - Output parsing (categories/keywords/descriptions)
   - Metadata writing (IPTC via `iptcinfo3`, EXIF via `piexif`)
   - Runs on background thread to keep UI responsive

5. **Daminion Integration** (two-layered):
   - `src.core.daminion_api`: Low-level REST API wrapper (auth, rate limiting)
   - `src.core.daminion_client`: High-level app-specific logic
   - Handles catalog browsing, batch updates, shared collections

6. **Deduplication**:
   - Perceptual hashing (pHash, dHash, etc.) in `src.core.dedup`
   - Hash storage/comparison/strategies
   - Integrated in wizard as optional step

7. **Concurrency & Threading**:
   - Background worker pattern (`src.utils.background_worker`)
   - Processing runs on separate thread from UI
   - Thread-safe communication via queues/events
   - GPU acceleration via CUDA when available

## Testing Strategy

### Test Types
- **Unit Tests**: Mock external dependencies (APIs, models), located in `tests/unit/`
- **Integration Tests**: Require real Daminion server, enabled via `RUN_INTEGRATION_TESTS=1`
- **Manual Tests**: Exploratory scripts in `tests/manual/` (not automated)

### Running Tests
```bash
# Quick unit test run (no server needed)
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Integration tests (requires Daminion server)
RUN_INTEGRATION_TESTS=1 DAMINION_URL=http://server DAMINION_USERNAME=user DAMINION_PASSWORD=pass pytest tests/integration/ -v

# Specific subsystem
pytest tests/unit/core/dedup/ -v  # Deduplication tests
```

### Test Framework
- Primary: `pytest` (recommended)
- Alternative: Python's built-in `unittest` framework
- Mocking: `unittest.mock` for isolation
- Coverage: `pytest-cov`

## Configuration & Environment

### Runtime Configuration
- Settings persisted to `~/.synapic_v2_config.json` (user home)
- Modified via UI (Step 2: Engine selection) or manually edited

### Environment Variables (for Cloud APIs & Testing)
| Variable | Purpose |
|----------|---------|
| `GROQ_API_KEY` | Groq API key (for Groq integration) |
| `CEREBRAS_API_KEY` | Cerebras Cloud API key |
| `NVIDIA_API_KEY` | NVIDIA NIM API key |
| `DAMINION_URL` | Daminion server URL (for tests/integration) |
| `DAMINION_USERNAME` | Daminion username |
| `DAMINION_PASSWORD` | Daminion password |
| `RUN_INTEGRATION_TESTS` | Set to "1" to enable integration tests |
| `HF_HUB_DISABLE_SYMLINKS_WARNING` | Set to "1" to avoid HF symlink warnings on Windows |

### Important Files
- `requirements.txt`: Production dependencies
- `main.spec`: PyInstaller configuration (executable build)
- `.pre-commit-config.yaml`: Pre-commit hooks (Ruff, etc.)
- `CONFIG.md`: Detailed configuration guide

## Development Notes

### Wizard Workflow Details
1. **Step 1: Datasource** - Select local folder or connect to Daminion server
2. **Step 2: Engine** - Choose AI provider (Local/HF, OpenRouter, Groq, etc.)
3. **Step 3: Process** - Execute batch job with progress monitoring
4. **Step 4: Results** - Review metadata, export reports, apply to files/DAM
5. **Bonus: Deduplication** - Optional workflow for finding similar images

### Performance Considerations
- Local model inference benefits from GPU (CUDA) acceleration
- Background processing keeps UI responsive during long jobs
- Rate limiting configured for Daminion and cloud API calls
- Memory heavy; 8GB+ RAM recommended for local models

### Building & Distribution
- Windows executable built via PyInstaller (`main.spec`)
- Build artifacts (`build/`, `dist/`, `release/`) should not be committed
- GitHub Actions automates builds and releases

### Code Conventions
- Follow existing style (PEP 8 with Ruff enforcement)
- Type hints used selectively in newer code
- Logging via `src.utils.logger` (console + rotating file)
- Error handling with comprehensive logging
- GUI thread safety: UI updates only on main thread

## Useful Files for Understanding
- `docs/developer/DEVELOPER_GUIDE.md`: Deep technical architecture
- `README.md`: User-focused getting started and features
- `CONFIG.md`: Configuration details and testing
- `src/core/session.py`: Central state management
- `src/core/processing.py`: Core tagging pipeline
- `src/ui/app.py`: Main application and wizard flow