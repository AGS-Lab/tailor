import os
from openai import OpenAI
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

class LLMClient:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.client = OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url
        )
        self.model = os.getenv("LLM_MODEL", "gpt-3.5-turbo")

    def generate_response(
        self, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None
    ) -> Any:
        
        # Prepare messages
        final_messages = []
        if system_prompt:
            final_messages.append({"role": "system", "content": system_prompt})
        
        final_messages.extend(messages)

        # Call OpenAI
        params = {
            "model": self.model,
            "messages": final_messages,
        }
        
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**params)
        return response.choices[0].message
