"""
LLM Module - LangGraph-based LLM processing with plugin hooks.

This module provides:
- HookRegistry: Registry for plugin hooks at extension points
- LLMPipeline: LangGraph-based processing pipeline
- HookContext: Context passed through hooks
- HookPhase: Enum of available hook phases
"""

from .hook_registry import (
    HookRegistry,
    HookPhase,
    HookContext,
    HookHandler,
    RegisteredHook
)

from .pipeline import (
    LLMPipeline,
    PipelineConfig,
    PipelineState
)

__all__ = [
    # Hook Registry
    "HookRegistry",
    "HookPhase",
    "HookContext",
    "HookHandler",
    "RegisteredHook",
    
    # Pipeline
    "LLMPipeline",
    "PipelineConfig",
    "PipelineState"
]
