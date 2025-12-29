from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import os

from app.services.llm import LLMClient
from app.core.plugin_loader import PluginLoader
from app.services.orchestrator import Orchestrator

app = FastAPI(title="Tailor API", version="0.1.0")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Services
orchestrator: Optional[Orchestrator] = None

class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, str]] = []

class ChatResponse(BaseModel):
    response: str
    # we could return updated history here if we wanted the frontend to manage it entirely
    # but for now we stick to simple response

@app.on_event("startup")
def startup_event():
    global orchestrator
    
    # Check for API Key
    if not os.getenv("OPENAI_API_KEY"):
        print("WARNING: OPENAI_API_KEY not set. Chat may fail.")

    # Load Plugins
    # We assume we operate from backend/ directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Plugins are in app/plugins
    # But PluginLoader uses python module paths (app.plugins)
    
    loader = PluginLoader(plugin_dir="") # dir arg is legacy in my simplified loader implementation
    
    llm_client = LLMClient() 
    
    orchestrator = Orchestrator(llm_client, loader)
    print("Tailor Backend Initialized.")

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Backend not initialized")
    
    try:
        response_text = await orchestrator.process_message(request.message, request.history)
        return ChatResponse(response=response_text)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok", "plugins": [p.name for p in orchestrator.plugins] if orchestrator else []}
