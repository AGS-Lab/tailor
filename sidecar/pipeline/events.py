"""
Pipeline Event Constants
"""

class PipelineEvents:
    # Lifecycle
    START = "pipeline.start"
    END = "pipeline.end"
    ERROR = "pipeline.error"
    
    # Phases
    INPUT = "pipeline.input"       # Plugins can transform input
    CONTEXT = "pipeline.context"   # RAG/Memory injection
    PROMPT = "pipeline.prompt"     # Final prompt assembly
    LLM = "pipeline.llm"           # Actual Model Call
    POST_PROCESS = "pipeline.post_process" # Response handling
    OUTPUT = "pipeline.output"     # UI Formatting
