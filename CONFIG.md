Synapic Configuration Guide

Global defaults
- DAMINION_URL: URL of Daminion server (e.g. http://damserver.local/daminion)
- DAMINION_USERNAME: Admin username for DAM
- DAMINION_PASSWORD: Admin password for DAM
- RUN_INTEGRATION_TESTS: Enable integration tests (1 to enable, 0 to disable)

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
