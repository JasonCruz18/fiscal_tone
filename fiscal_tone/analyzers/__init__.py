"""
LLM-based analyzers for FiscalTone.

This module provides GPT-4o based classification of fiscal policy text
into a 1-5 fiscal risk scale.

Modules:
    llm_classifier: LLM classification pipeline
    prompt_templates: Domain context and prompt engineering

Note:
    Requires additional dependencies:
    pip install openai aiolimiter tenacity tqdm
"""

__all__ = [
    "llm_classifier",
    "prompt_templates",
]


def __getattr__(name: str):
    """Lazy import of submodules."""
    if name == "llm_classifier":
        from fiscal_tone.analyzers import llm_classifier
        return llm_classifier
    elif name == "prompt_templates":
        from fiscal_tone.analyzers import prompt_templates
        return prompt_templates
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
