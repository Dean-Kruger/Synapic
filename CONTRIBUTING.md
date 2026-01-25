# Contributing to Synapic

Thank you for your interest in contributing to Synapic! This document outlines our coding standards, documentation requirements, and the process for submitting contributions.

## Coding Standards

### Python Style
- Follow **PEP 8** guidelines for code style.
- Use meaningful variable and function names.
- Keep functions focused and concise.

### Documentation Requirements
Every module, class, and public function must have a docstring following the **Google Style**.

#### Module Docstring Template
```python
"""
Module Name
===========

Brief description of what this module does and its role in the application.

Key Components:
- Component 1: Description
- Component 2: Description

Author: Synapic Project
"""
```

#### Function Docstring Template
```python
def function_name(param1: Type1, param2: Type2) -> ReturnType:
    """
    Brief one-line description.
    
    Detailed explanation of what the function does.
    
    Args:
        param1: Description of parameter 1.
        param2: Description of parameter 2.
    
    Returns:
        Description of return value.
    
    Raises:
        ExceptionType: When this exception is raised.
    """
```

### Logging
- Use the centralized logging system in `src.utils.logger`.
- Avoid `print()` statements in production code.
- Use appropriate log levels (`DEBUG`, `INFO`, `WARNING`, `ERROR`).
- **CRITICAL**: Never log raw API keys, passwords, or tokens. The logging system includes automatic masking, but avoid logging sensitive data where possible.

## Project Structure

- `src/core/`: Business logic, AI integration, and DAM clients.
- `src/ui/`: CustomTkinter UI components and wizard steps.
- `src/utils/`: Shared utilities (logging, configuration, etc.).
- `docs/`: Technical documentation and feature guides.
- `tests/`: Automated test suite.

## Submission Process

1. **Fork the repository**.
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`).
3. **Commit your changes** (`git commit -m 'Add amazing feature'`).
4. **Push to the branch** (`git push origin feature/amazing-feature`).
5. **Open a Pull Request**.

## Testing

Before submitting a pull request, ensure that:
1. All existing tests pass.
2. New features have accompanying tests.
3. The application runs without errors from the main entry point.

---
*Created by the Synapic Project team.*
