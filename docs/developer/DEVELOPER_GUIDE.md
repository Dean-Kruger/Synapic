# Synapic Developer Guide

This guide provides technical details on the architecture, subsystems, and integration patterns used in Synapic.

## Architecture Overview

Synapic follows a modular architecture designed for extensibility and separation of concerns.

### 1. Wizard Workflow
The UI is structured as a 4-step wizard:
- **Step 1: Datasource**: File system or Daminion DAM integration.
- **Step 2: Engine**: AI provider selection (Local, Hugging Face Hub, OpenRouter).
- **Step 3: Process**: Multithreaded execution of the tagging pipeline.
- **Step 4: Results**: Review and metrics.

### 2. Session Management (`src.core.session`)
A centralized `Session` object stores all configuration and state. This object is passed between UI steps and to the processing engine.

### 3. AI Engine Strategy
The application uses a strategy-like pattern for different AI providers:
- **Local (`huggingface_utils.py`)**: Direct use of `transformers` and `torch` for local inference.
- **Hugging Face Hub**: Remote inference (currently mapped to local inference logic in many cases).
- **OpenRouter (`openrouter_utils.py`)**: Unified REST API for various vision-language models.

## Tagging Pipeline

The pipeline in `src.core.processing.py` handles:
1. **Item Fetching**: Retrieving filenames/IDs from the datasource.
2. **Image Validation**: Checking formats and dimensions.
3. **Inference**: Calling the selected AI model.
4. **Parsing**: Extracting structured tags (categories, keywords, descriptions) from AI output.
5. **Metadata Writing**: Embedding results into IPTC/EXIF using `iptcinfo3` and `piexif`.

## Daminion DAM Integration

The integration with Daminion is two-layered:
- **`src.core.daminion_api.py`**: A robust, low-level wrapper for the Daminion REST API. It handles authentication, catalog browsing, and batch metadata updates.
- **`src.core.daminion_client.py`**: A high-level integration layer that maps application-specific logic to the API calls.

## Metadata Standards

- **Keywords**: Written to IPTC Keywords and EXIF ImageDescription tag groups.
- **Categories**: Assigned to IPTC Category or mapped to specific Daminion tags.
- **Descriptions**: Written to IPTC Caption/Abstract and EXIF UserComment.

## Performance Considerations

- **Threading**: The tagging pipeline runs on a background thread to keep the UI responsive.
- **GPU Acceleration**: CUDA is preferred for local models if available.
- **Rate Limiting**: Configured for DAM and Cloud API calls to prevent throttling.

## Development Setup

See `README.md` for installation and build instructions.
