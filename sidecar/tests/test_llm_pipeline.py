"""
Tests for LLM Hook Registry and Pipeline.

Run with: pytest tests/test_llm_pipeline.py -v
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm.hook_registry import HookRegistry, HookPhase, HookContext
from llm.pipeline import LLMPipeline, PipelineConfig


class TestHookRegistry:
    """Tests for HookRegistry."""
    
    @pytest.fixture
    def registry(self):
        """Create a fresh hook registry."""
        return HookRegistry()
    
    def test_register_hook(self, registry):
        """Test registering a hook."""
        async def dummy_hook(ctx):
            return ctx
        
        registry.register(HookPhase.INPUT_TRANSFORM, dummy_hook, "test_plugin")
        
        hooks = registry.get_hooks(HookPhase.INPUT_TRANSFORM)
        assert "test_plugin" in hooks[HookPhase.INPUT_TRANSFORM.value]
    
    def test_register_multiple_hooks_sorted_by_priority(self, registry):
        """Test that hooks are sorted by priority."""
        async def hook_a(ctx):
            return ctx
        
        async def hook_b(ctx):
            return ctx
        
        # Register with different priorities
        registry.register(HookPhase.INPUT_TRANSFORM, hook_a, "plugin_a", priority=100)
        registry.register(HookPhase.INPUT_TRANSFORM, hook_b, "plugin_b", priority=50)
        
        hooks = registry.get_hooks(HookPhase.INPUT_TRANSFORM)
        # plugin_b should come first (lower priority)
        assert hooks[HookPhase.INPUT_TRANSFORM.value] == ["plugin_b", "plugin_a"]
    
    def test_unregister_hook(self, registry):
        """Test unregistering a hook."""
        async def dummy_hook(ctx):
            return ctx
        
        registry.register(HookPhase.INPUT_TRANSFORM, dummy_hook, "test_plugin")
        removed = registry.unregister(HookPhase.INPUT_TRANSFORM, "test_plugin")
        
        assert removed == 1
        assert not registry.has_hooks(HookPhase.INPUT_TRANSFORM)
    
    def test_unregister_all(self, registry):
        """Test unregistering all hooks for a plugin."""
        async def dummy_hook(ctx):
            return ctx
        
        registry.register(HookPhase.INPUT_TRANSFORM, dummy_hook, "test_plugin")
        registry.register(HookPhase.OUTPUT_FORMAT, dummy_hook, "test_plugin")
        
        removed = registry.unregister_all("test_plugin")
        
        assert removed == 2
    
    @pytest.mark.asyncio
    async def test_run_phase(self, registry):
        """Test running hooks for a phase."""
        call_order = []
        
        async def hook_a(ctx):
            call_order.append("a")
            ctx.metadata["a"] = True
            return ctx
        
        async def hook_b(ctx):
            call_order.append("b")
            ctx.metadata["b"] = True
            return ctx
        
        registry.register(HookPhase.INPUT_TRANSFORM, hook_a, "plugin_a", priority=100)
        registry.register(HookPhase.INPUT_TRANSFORM, hook_b, "plugin_b", priority=50)
        
        ctx = HookContext(message="test")
        result = await registry.run_phase(HookPhase.INPUT_TRANSFORM, ctx)
        
        # hook_b runs first (priority 50)
        assert call_order == ["b", "a"]
        assert result.metadata["a"] is True
        assert result.metadata["b"] is True
    
    @pytest.mark.asyncio
    async def test_run_phase_with_abort(self, registry):
        """Test that abort stops further processing."""
        call_order = []
        
        async def validator(ctx):
            call_order.append("validator")
            ctx.should_abort = True
            ctx.abort_reason = "Content blocked"
            return ctx
        
        async def should_not_run(ctx):
            call_order.append("should_not_run")
            return ctx
        
        registry.register(HookPhase.INPUT_VALIDATE, validator, "validator", priority=50)
        registry.register(HookPhase.INPUT_VALIDATE, should_not_run, "other", priority=100)
        
        ctx = HookContext(message="test")
        result = await registry.run_phase(HookPhase.INPUT_VALIDATE, ctx)
        
        assert result.should_abort is True
        assert "should_not_run" not in call_order
    
    def test_clear(self, registry):
        """Test clearing all hooks."""
        async def dummy_hook(ctx):
            return ctx
        
        registry.register(HookPhase.INPUT_TRANSFORM, dummy_hook, "plugin")
        registry.clear()
        
        assert not registry.has_hooks(HookPhase.INPUT_TRANSFORM)


class TestHookContext:
    """Tests for HookContext."""
    
    def test_default_values(self):
        """Test HookContext default values."""
        ctx = HookContext(message="test")
        
        assert ctx.message == "test"
        assert ctx.conversation_history == []
        assert ctx.response == ""
        assert ctx.metadata == {}
        assert ctx.should_abort is False
        assert ctx.abort_reason == ""
        assert ctx.hooks_executed == []
    
    def test_modifying_context(self):
        """Test modifying context values."""
        ctx = HookContext(message="original")
        ctx.message = "modified"
        ctx.metadata["key"] = "value"
        
        assert ctx.message == "modified"
        assert ctx.metadata["key"] == "value"


class TestLLMPipeline:
    """Tests for LLMPipeline."""
    
    @pytest.fixture
    def pipeline(self):
        """Create a pipeline with empty registry."""
        registry = HookRegistry()
        config = PipelineConfig()
        return LLMPipeline(registry, config)
    
    @pytest.mark.asyncio
    async def test_process_simple_message(self, pipeline):
        """Test processing a simple message."""
        result = await pipeline.process("hello")
        
        assert result["status"] == "success"
        assert "response" in result
        assert len(result["response"]) > 0
    
    @pytest.mark.asyncio
    async def test_process_with_history(self, pipeline):
        """Test processing with conversation history."""
        history = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"}
        ]
        
        result = await pipeline.process("How are you?", history=history)
        
        assert result["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_process_with_hooks(self):
        """Test processing with custom hooks."""
        registry = HookRegistry()
        
        # Add a hook that modifies the message
        async def uppercase_hook(ctx):
            ctx.message = ctx.message.upper()
            return ctx
        
        registry.register(HookPhase.INPUT_TRANSFORM, uppercase_hook, "test")
        
        pipeline = LLMPipeline(registry, PipelineConfig())
        result = await pipeline.process("hello")
        
        # The response should be based on uppercase input
        assert result["status"] == "success"
        assert "test:input.transform" in result["hooks_executed"]
    
    @pytest.mark.asyncio
    async def test_process_aborted(self):
        """Test processing that gets aborted."""
        registry = HookRegistry()
        
        async def block_hook(ctx):
            ctx.should_abort = True
            ctx.abort_reason = "Blocked for testing"
            return ctx
        
        registry.register(HookPhase.INPUT_VALIDATE, block_hook, "blocker")
        
        pipeline = LLMPipeline(registry, PipelineConfig())
        result = await pipeline.process("blocked message")
        
        assert result["status"] == "aborted"
        assert result["reason"] == "Blocked for testing"
    
    def test_get_config(self, pipeline):
        """Test getting pipeline config."""
        config = pipeline.get_config()
        
        assert "model" in config
        assert "temperature" in config
        assert "registered_hooks" in config
    
    def test_update_config(self, pipeline):
        """Test updating pipeline config."""
        pipeline.update_config(model="gpt-3.5-turbo", temperature=0.5)
        
        assert pipeline.config.model == "gpt-3.5-turbo"
        assert pipeline.config.temperature == 0.5


class TestPipelineConfig:
    """Tests for PipelineConfig."""
    
    def test_from_dict(self):
        """Test creating config from dict."""
        config = PipelineConfig.from_dict({
            "model": "claude-3",
            "temperature": 0.8,
            "max_tokens": 2048
        })
        
        assert config.model == "claude-3"
        assert config.temperature == 0.8
        assert config.max_tokens == 2048
    
    def test_from_dict_defaults(self):
        """Test defaults when keys missing."""
        config = PipelineConfig.from_dict({})
        
        assert config.model == "gpt-4"
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
