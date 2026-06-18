Synapic Configuration Guide

Global defaults
- DAMINION_URL: URL of Daminion server (e.g. http://damserver.local/daminion)
- DAMINION_USERNAME: Admin username for DAM
- DAMINION_PASSWORD: Admin password for DAM
- RUN_INTEGRATION_TESTS: Enable integration tests (1 to enable, 0 to disable)

Cloud AI provider keys
- The primary way to configure cloud providers is the in-app UI (Step 2: Select
  Engine), which persists settings to the config file (see below).
- The following providers also read their key from an environment variable,
  which is useful for headless/automated runs:
  - GROQ_API_KEY: Groq API key (get one at https://console.groq.com)
  - GROQ_API_BASE_URL: Override the Groq base URL (defaults to the public API)
  - CEREBRAS_API_KEY: Cerebras Cloud key (https://cloud.cerebras.ai)
  - NVIDIA_API_KEY: NVIDIA NIM key (https://build.nvidia.com)
- OpenRouter, Google AI, Ollama, and Hugging Face keys are configured through
  the UI and stored in the config file rather than via environment variables.

Config file
- Settings (including saved API keys) are persisted to `~/.synapic_v2_config.json`
  in your user home directory.

Usage
- Tests can be run with Python's pytest or unittest via test suite. Integration tests require environment variables to be set.
- Example:
  export DAMINION_URL=http://damserver.local/daminion
  export DAMINION_USERNAME=admin
  export DAMINION_PASSWORD=admin
  RUN_INTEGRATION_TESTS=1 python -m pytest tests/ -q

Notes
- The repo uses a Windows launcher for local runs; on Unix, run `python main.py` as appropriate.
- Heavy ML dependencies may require sufficient RAM/CPU; consider using CPU-only builds if CUDA is unavailable.
