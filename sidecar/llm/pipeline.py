"""
LLM Processing Pipeline - LangGraph-based pipeline with plugin hooks.

This module provides the main LLM processing pipeline that integrates
plugin hooks at defined extension points.
"""

import os
from typing import Dict, Any, List, Optional, TypedDict
from dataclasses import dataclass
import asyncio

from loguru import logger

# Try to import OpenAI integration
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("langchain-openai not installed. Using placeholder responses.")

from .hook_registry import HookRegistry, HookPhase, HookContext


class PipelineState(TypedDict):
    """State passed through the LangGraph pipeline."""
    
    message: str
    history: List[Dict[str, str]]
    context: Dict[str, Any]
    response: str
    metadata: Dict[str, Any]
    should_abort: bool
    abort_reason: str


@dataclass
class PipelineConfig:
    """Configuration for the LLM pipeline."""
    
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: float = 30.0
    enable_streaming: bool = False
    api_key: Optional[str] = None
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PipelineConfig":
        """Create config from dictionary."""
        return cls(
            model=d.get("model", os.getenv("LLM_MODEL", "gpt-4")),
            temperature=d.get("temperature", float(os.getenv("LLM_TEMPERATURE", "0.7"))),
            max_tokens=d.get("max_tokens", int(os.getenv("LLM_MAX_TOKENS", "4096"))),
            timeout=d.get("timeout", 30.0),
            enable_streaming=d.get("enable_streaming", False),
            api_key=d.get("api_key", os.getenv("OPENAI_API_KEY"))
        )


class LLMPipeline:
    """
    LangGraph-based LLM processing pipeline.
    
    This pipeline processes messages through defined phases:
    1. Input Transform - Modify user message
    2. Input Validate - Filter/validate input
    3. Process Before LLM - Inject context (RAG, etc.)
    4. LLM Call - Call the language model
    5. Process After LLM - Post-process response
    6. Output Format - Format for UI
    
    Plugins can hook into any phase except the LLM call itself.
    """
    
    def __init__(
        self,
        hook_registry: HookRegistry,
        config: Optional[PipelineConfig] = None
    ):
        """
        Initialize the pipeline.
        
        Args:
            hook_registry: Registry for plugin hooks
            config: Pipeline configuration
        """
        self.hooks = hook_registry
        self.config = config or PipelineConfig()
        self._logger = logger.bind(component="LLMPipeline")
        
        # Initialize OpenAI client if available and API key is set
        self._llm: Optional[ChatOpenAI] = None
        self._init_llm_client()
    
    def _init_llm_client(self) -> None:
        """Initialize the LLM client if OpenAI is available."""
        if not OPENAI_AVAILABLE:
            self._logger.warning("OpenAI not available - using placeholder responses")
            return
        
        api_key = self.config.api_key or os.getenv("OPENAI_API_KEY")
        
        if not api_key or api_key == "your-openai-api-key-here":
            self._logger.warning("No valid OpenAI API key found - using placeholder responses")
            return
        
        try:
            self._llm = ChatOpenAI(
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                api_key=api_key,
                request_timeout=self.config.timeout
            )
            self._logger.info(f"OpenAI client initialized with model: {self.config.model}")
        except Exception as e:
            self._logger.error(f"Failed to initialize OpenAI client: {e}")
            self._llm = None
    
    async def process(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a message through the full pipeline.
        
        Args:
            message: User message to process
            history: Conversation history
            metadata: Additional metadata
            
        Returns:
            Dict with response and metadata
        """
        history = history or []
        metadata = metadata or {}
        
        # Create hook context
        ctx = HookContext(
            message=message,
            conversation_history=history,
            metadata=metadata
        )
        
        self._logger.info(f"Processing message: {message[:50]}...")
        
        try:
            # Phase 1: Input Transform
            ctx = await self._run_input_transform(ctx)
            
            # Phase 2: Input Validate
            ctx = await self._run_input_validate(ctx)
            
            if ctx.should_abort:
                return {
                    "status": "aborted",
                    "reason": ctx.abort_reason,
                    "response": "",
                    "hooks_executed": ctx.hooks_executed
                }
            
            # Phase 3: Process Before LLM
            ctx = await self._run_process_before(ctx)
            
            # Phase 4: LLM Call
            ctx = await self._call_llm(ctx)
            
            # Phase 5: Process After LLM
            ctx = await self._run_process_after(ctx)
            
            # Phase 6: Output Format
            ctx = await self._run_output_format(ctx)
            
            self._logger.info("Pipeline completed successfully")
            
            return {
                "status": "success",
                "response": ctx.response,
                "metadata": ctx.metadata,
                "hooks_executed": ctx.hooks_executed
            }
            
        except Exception as e:
            self._logger.error(f"Pipeline error: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "response": "",
                "hooks_executed": ctx.hooks_executed
            }
    
    async def _run_input_transform(self, ctx: HookContext) -> HookContext:
        """Run input.transform hooks."""
        return await self.hooks.run_phase(HookPhase.INPUT_TRANSFORM, ctx)
    
    async def _run_input_validate(self, ctx: HookContext) -> HookContext:
        """Run input.validate hooks."""
        return await self.hooks.run_phase(HookPhase.INPUT_VALIDATE, ctx)
    
    async def _run_process_before(self, ctx: HookContext) -> HookContext:
        """Run process.before_llm hooks."""
        return await self.hooks.run_phase(HookPhase.PROCESS_BEFORE_LLM, ctx)
    
    async def _run_process_after(self, ctx: HookContext) -> HookContext:
        """Run process.after_llm hooks."""
        return await self.hooks.run_phase(HookPhase.PROCESS_AFTER_LLM, ctx)
    
    async def _run_output_format(self, ctx: HookContext) -> HookContext:
        """Run output.format hooks."""
        return await self.hooks.run_phase(HookPhase.OUTPUT_FORMAT, ctx)
    
    async def _call_llm(self, ctx: HookContext) -> HookContext:
        """
        Call the language model.
        
        Uses OpenAI API if available and API key is configured,
        otherwise falls back to placeholder responses.
        """
        self._logger.debug(f"Calling LLM with model: {self.config.model}")
        
        # Build context from metadata
        system_prompt = ctx.metadata.get(
            "system_prompt", 
            "You are a helpful AI assistant for a Tailor vault. "
            "Help the user with their questions and tasks."
        )
        rag_context = ctx.metadata.get("rag_context", [])
        
        # Enhance system prompt with RAG context if available
        if rag_context:
            context_str = "\n\n".join(rag_context[:5])  # Limit to 5 context items
            system_prompt += f"\n\nRelevant context from the vault:\n{context_str}"
        
        # Try OpenAI API call
        if self._llm is not None:
            try:
                response = await self._call_openai(ctx, system_prompt)
                ctx.response = response
                ctx.hooks_executed.append("llm:openai")
                return ctx
            except Exception as e:
                self._logger.error(f"OpenAI API error: {e}")
                # Fall through to placeholder
        
        # Fallback to placeholder
        response = await self._generate_placeholder_response(ctx, rag_context)
        ctx.response = response
        ctx.hooks_executed.append("llm:placeholder")
        
        return ctx
    
    async def _call_openai(self, ctx: HookContext, system_prompt: str) -> str:
        """
        Call OpenAI API with conversation history.
        
        Args:
            ctx: Hook context with message and history
            system_prompt: System message for the LLM
            
        Returns:
            Generated response text
        """
        # Build messages list
        messages = [SystemMessage(content=system_prompt)]
        
        # Add conversation history
        for msg in ctx.conversation_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        
        # Add current message
        messages.append(HumanMessage(content=ctx.message))
        
        self._logger.debug(f"Sending {len(messages)} messages to OpenAI")
        
        # Call the API (run in thread pool since it's blocking)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._llm.invoke(messages)
        )
        
        return response.content
    
    async def _generate_placeholder_response(
        self,
        ctx: HookContext,
        rag_context: List[str]
    ) -> str:
        """
        Generate a placeholder response when OpenAI is not available.
        
        This provides demo functionality without an API key.
        """
        message = ctx.message.lower()
        
        # Simple pattern matching for demo
        if "hello" in message or "hi" in message:
            return (
                "Hello! I'm your vault AI assistant. "
                "Note: OpenAI API key not configured - using demo mode. "
                "Add your API key to .env to enable real responses."
            )
        
        if "?" in ctx.message:
            if rag_context:
                context_str = "\n".join(rag_context[:3])
                return (
                    f"[Demo Mode - No API Key]\n\n"
                    f"Based on your vault context:\n\n"
                    f"{context_str}\n\n"
                    f"In production, I would answer: '{ctx.message}'"
                )
            return (
                f"[Demo Mode - No API Key]\n\n"
                f"That's an interesting question. "
                f"Configure your OpenAI API key in .env to get real answers.\n\n"
                f"Your question: '{ctx.message}'"
            )
        
        # Echo with info
        word_count = len(ctx.message.split())
        
        return (
            f"[Demo Mode - OpenAI API key not configured]\n\n"
            f"Received message ({word_count} words).\n\n"
            f"To enable real AI responses:\n"
            f"1. Copy .env.example to .env\n"
            f"2. Add your OPENAI_API_KEY\n"
            f"3. Restart the vault"
        )
    
    def get_config(self) -> Dict[str, Any]:
        """Get current pipeline configuration."""
        return {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "timeout": self.config.timeout,
            "enable_streaming": self.config.enable_streaming,
            "openai_available": self._llm is not None,
            "registered_hooks": self.hooks.get_hooks()
        }
    
    def update_config(self, **kwargs: Any) -> None:
        """Update pipeline configuration."""
        reinit_client = False
        
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                self._logger.info(f"Updated config: {key}={value}")
                
                # Need to reinit client if model or API key changes
                if key in ("model", "api_key", "temperature", "max_tokens"):
                    reinit_client = True
        
        if reinit_client:
            self._init_llm_client()

