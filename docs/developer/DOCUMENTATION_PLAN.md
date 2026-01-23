# Synapic Codebase Documentation Plan

## Overview
This document outlines the systematic approach to adding comprehensive inline documentation to the entire Synapic codebase. The goal is to make the code accessible and understandable to new developers.

## Documentation Standards

### Module-Level Documentation
Every Python file should have:
- **Module docstring** explaining the purpose and scope
- **Section headers** using comment blocks (e.g., `# ============ SECTION ============`)
- **Import organization** with comments grouping related imports

### Function/Method Documentation
Every function/method should have:
- **Docstring** with description of purpose
- **Parameters** section explaining each argument
- **Returns** section explaining return value and type
- **Raises** section if exceptions are raised
- **Examples** for complex functions
- **TODO** notes for incomplete implementations

### Inline Comments
- Explain **WHY**, not just WHAT
- Comment complex algorithms or business logic
- Explain non-obvious design decisions
- Mark important state changes
- Clarify external API interactions

## Progress Tracker

### ✅ Completed (Part 1)
- [x] `main.py` - Application entry point
- [x] `src/core/session.py` - Session and configuration management
- [x] `src/core/processing.py` - Main processing pipeline

### 🔄 In Progress

### ⏳ Pending - Core Business Logic (Priority 1)
- [ ] `src/core/image_processing.py` - Image metadata and tag extraction
- [ ] `src/core/config.py` - Application constants and configuration

### ⏳ Pending - Integration Modules (Priority 2)
- [ ] `src/core/daminion_client.py` - Daminion DAM integration
- [ ] `src/core/daminion_api.py` - Low-level Daminion API wrapper
- [ ] `src/core/huggingface_utils.py` - Hugging Face model utilities
- [ ] `src/core/openrouter_utils.py` - OpenRouter API integration

### ⏳ Pending - UI Components (Priority 3)
- [ ] `src/ui/app.py` - Main application window
- [ ] `src/ui/steps/step1_datasource.py` - Data source selection UI
- [ ] `src/ui/steps/step2_tagging.py` - Engine configuration UI
- [ ] `src/ui/steps/step3_process.py` - Processing execution UI
- [ ] `src/ui/steps/step4_results.py` - Results display UI

### ⏳ Pending - Utilities (Priority 4)
- [ ] `src/utils/logger.py` - Logging system setup
- [ ] `src/utils/config_manager.py` - Configuration persistence
- [ ] `src/utils/registry_config.py` - Windows registry integration

### ⏳ Pending - Support Files (Priority 5)
- [ ] `src/core/__init__.py`
- [ ] `src/ui/steps/__init__.py`
- [ ] `src/utils/__init__.py`

### 📝 To Skip (Test/Example Files)
- `src/core/daminion_api_example.py` - Example code
- `src/core/daminion_client_old.py` - Deprecated
- `src/core/test_daminion_api.py` - Test file
- `src/core/enhanced_progress.py` - Utility (low priority)

## Documentation Templates

### Module Template
```python
"""
Module Name
===========

Brief description of what this module does and its role in the application.

Key Components:
- Component 1: Description
- Component 2: Description

Dependencies:
- External library 1: Why it's used
- External library 2: Why it's used

Author: Dean
"""
```

### Function Template
```python
def function_name(param1: Type1, param2: Type2) -> ReturnType:
    """
    Brief one-line description.
    
    Detailed explanation of what the function does, including any important
    algorithms, side effects, or design decisions.
    
    Args:
        param1: Description of parameter 1
        param2: Description of parameter 2
    
    Returns:
        Description of return value
    
    Raises:
        ExceptionType: When this exception is raised
    
    Example:
        >>> function_name(value1, value2)
        expected_result
    
    Note:
        Any important notes about usage or behavior
    """
    # Implementation with inline comments
    pass
```

### Class Template
```python
class ClassName:
    """
    Brief description of the class purpose.
    
    This class is responsible for [main responsibility]. It [key behavior].
    
    Attributes:
        attribute1: Description of attribute 1
        attribute2: Description of attribute 2
    
    Example:
        >>> obj = ClassName(param)
        >>> obj.method()
        result
    """
    
    def __init__(self, param: Type):
        """Initialize the class with given parameters."""
        # Implementation
        pass
```

## Key Areas Requiring Special Attention

### 1. Processing Pipeline (`processing.py`)
- Explain the workflow from item fetching to metadata writing
- Document the threading model
- Clarify error handling and retry logic
- Explain device selection for local inference

### 2. Image Processing (`image_processing.py`)
- Document the tag extraction algorithms
- Explain JSON parsing logic for VLM responses
- Clarify threshold filtering mechanism
- Document metadata writing (EXIF/IPTC)

### 3. Daminion Integration (`daminion_client.py`, `daminion_api.py`)
- Explain the API authentication flow
- Document query building for different scopes
- Clarify tag schema mapping
- Explain metadata update mechanism

### 4. Model Utilities (`huggingface_utils.py`, `openrouter_utils.py`)
- Document model discovery and caching
- Explain download progress tracking
- Clarify task detection logic
- Document API interaction patterns

### 5. UI Components (`app.py`, `step*.py`)
- Explain the wizard workflow
- Document state management between steps
- Clarify configuration persistence
- Explain validation and error display

## Next Steps

1. **Continue with Priority 1 files** (core business logic)
2. **Add examples** to complex functions
3. **Create architecture diagram** showing component relationships
4. **Add README sections** for each major subsystem
5. **Generate API documentation** using Sphinx or similar tool

## Notes for Developers

- **Be consistent** with the established style
- **Explain WHY** not just WHAT the code does
- **Think like a new developer** - what would confuse you?
- **Update this plan** as you complete sections
- **Commit frequently** with descriptive messages like "docs: add comments to [filename]"

## Estimated Effort

- **Core files (Priority 1-2)**: ~8-10 hours
- **UI files (Priority 3)**: ~6-8 hours  
- **Utilities (Priority 4)**: ~2-3 hours
- **Total**: ~16-21 hours for complete documentation

---

Last Updated: 2026-01-22
Status: In Progress (3/23 files completed)

