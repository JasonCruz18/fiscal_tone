# Contributing to FiscalTone

Thank you for your interest in contributing to FiscalTone! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Standards](#code-standards)
- [Testing Guidelines](#testing-guidelines)
- [Pull Request Process](#pull-request-process)
- [Code of Conduct](#code-of-conduct)

## Getting Started

### Ways to Contribute

- **Bug Reports**: Open an issue describing the bug
- **Feature Requests**: Open an issue describing the feature
- **Documentation**: Improve or add documentation
- **Code**: Submit pull requests for bug fixes or features
- **Testing**: Add or improve tests

### Before Starting

1. Check existing issues to avoid duplicates
2. For major changes, open an issue first to discuss
3. Fork the repository and create a feature branch

## Development Setup

### 1. Fork and Clone

```bash
# Fork via GitHub UI, then:
git clone https://github.com/YOUR_USERNAME/FiscalTone.git
cd FiscalTone
git remote add upstream https://github.com/JasonCruz18/FiscalTone.git
```

### 2. Create Development Environment

**Option A: Conda (Recommended)**
```bash
conda env create -f environment.yml
conda activate fiscal_tone
pip install -e .
```

**Option B: Pip**
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
pip install -r requirements-dev.txt
pip install -e .
```

### 3. Set Up Configuration

```bash
cp config/config.example.yaml config/config.yaml
# Edit config.yaml with your settings
```

### 4. Verify Setup

```bash
# Run tests
pytest

# Check code quality
black --check fiscal_tone scripts
isort --check-only fiscal_tone scripts
flake8 fiscal_tone scripts
```

## Code Standards

### Python Style Guide

We follow [PEP 8](https://peps.python.org/pep-0008/) with these tools:

- **Black**: Code formatter (100 char line length)
- **isort**: Import sorter (black-compatible profile)
- **flake8**: Linter
- **mypy**: Type checker (optional but encouraged)

### Formatting Commands

```bash
# Format code
black fiscal_tone scripts
isort fiscal_tone scripts

# Check without modifying
black --check fiscal_tone scripts
isort --check-only fiscal_tone scripts
flake8 fiscal_tone scripts
```

### Type Hints

Use type hints for function signatures:

```python
def process_paragraph(text: str, threshold: float = 0.5) -> dict[str, Any]:
    """Process a paragraph and return results."""
    ...
```

### Docstrings

Use Google-style docstrings:

```python
def classify_paragraph(text: str, context: str | None = None) -> int:
    """Classify fiscal tone of a paragraph.

    Args:
        text: The paragraph text to classify.
        context: Optional domain context to include.

    Returns:
        Fiscal risk score from 1 (no concern) to 5 (alarm).

    Raises:
        ValueError: If text is empty.
        APIError: If LLM API call fails.

    Example:
        >>> score = classify_paragraph("El CF considera...")
        >>> assert 1 <= score <= 5
    """
    ...
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Modules | lowercase_with_underscores | `text_cleaner.py` |
| Classes | PascalCase | `PipelineRunner` |
| Functions | lowercase_with_underscores | `clean_text()` |
| Constants | UPPERCASE_WITH_UNDERSCORES | `DEFAULT_RATE_LIMIT` |
| Variables | lowercase_with_underscores | `paragraph_text` |

### File Organization

```python
"""Module docstring describing purpose."""

from __future__ import annotations

# Standard library imports
import os
import sys
from pathlib import Path

# Third-party imports
import pandas as pd
from tqdm import tqdm

# Local imports
from fiscal_tone.config import settings

# Constants
DEFAULT_THRESHOLD = 0.5

# Classes and functions
class MyClass:
    ...

def my_function():
    ...

# Main execution (if applicable)
if __name__ == "__main__":
    ...
```

## Testing Guidelines

### Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_collectors.py       # Collector tests
├── test_processors.py       # Processor tests
├── test_analyzers.py        # Analyzer tests
└── test_integration.py      # Integration tests
```

### Writing Tests

```python
import pytest
from fiscal_tone.processors import text_cleaner

class TestTextCleaner:
    """Tests for text_cleaner module."""

    def test_clean_removes_headers(self):
        """Test that clean_text removes section headers."""
        text = "Opinión del CF\n\nEl Consejo Fiscal considera..."
        result = text_cleaner.clean_text(text)
        assert "Opinión del CF" not in result

    def test_clean_preserves_content(self):
        """Test that clean_text preserves paragraph content."""
        text = "El CF considera que esta medida es adecuada."
        result = text_cleaner.clean_text(text)
        assert "considera" in result

    @pytest.mark.parametrize("input_text,expected", [
        ("", ""),
        ("   ", ""),
        ("text", "text"),
    ])
    def test_clean_edge_cases(self, input_text, expected):
        """Test clean_text handles edge cases."""
        assert text_cleaner.clean_text(input_text) == expected
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=fiscal_tone --cov-report=html

# Run specific test file
pytest tests/test_processors.py

# Run specific test
pytest tests/test_processors.py::TestTextCleaner::test_clean_removes_headers

# Run with verbose output
pytest -v

# Run only fast tests (skip slow integration tests)
pytest -m "not slow"
```

### Test Coverage

- Aim for >80% coverage on new code
- Focus on critical paths and edge cases
- Don't test external APIs directly (use mocks)

## Pull Request Process

### 1. Create Feature Branch

```bash
git checkout main
git pull upstream main
git checkout -b feature/your-feature-name
```

### 2. Make Changes

- Write code following standards above
- Add/update tests as needed
- Update documentation if applicable

### 3. Commit Changes

```bash
# Stage changes
git add .

# Commit with descriptive message
git commit -m "Add feature: brief description

- Detail 1
- Detail 2"
```

**Commit Message Guidelines:**

- Use present tense ("Add feature" not "Added feature")
- First line: 50 chars max, imperative mood
- Body: 72 chars per line, explain what and why

### 4. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create PR via GitHub UI.

### 5. PR Template

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring

## Testing
- [ ] Tests pass locally
- [ ] New tests added (if applicable)
- [ ] Coverage maintained/improved

## Checklist
- [ ] Code follows project style guide
- [ ] Self-reviewed my code
- [ ] Documentation updated (if needed)
- [ ] No new warnings introduced
```

### 6. Review Process

- Maintainer will review within a few days
- Address feedback by pushing new commits
- Once approved, maintainer will merge

## Code of Conduct

### Our Standards

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Accept constructive criticism gracefully
- Focus on what's best for the project

### Unacceptable Behavior

- Harassment or discrimination
- Trolling or insulting comments
- Publishing others' private information
- Other unprofessional conduct

### Enforcement

Violations can be reported to jj.cruza@up.edu.pe. All complaints will be reviewed and may result in temporary or permanent bans.

## Questions?

- Open an issue for general questions
- Email jj.cruza@up.edu.pe for sensitive matters
- Check existing documentation first

Thank you for contributing!
