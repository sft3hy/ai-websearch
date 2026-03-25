import os
import time
import uuid
import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from agent import run_agent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("api")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- OpenAI-compatible models ---

class ChatMessage(BaseModel):
    role: str
    content: str
    name: Optional[str] = None

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = False

class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = "stop"

class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4()}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: List[ChatCompletionChoice]


# --- Available Groq models ---
GROQ_MODELS = [
    {"id": "meta-llama/llama-4-scout-17b-16e-instruct", "owned_by": "meta"},
    {"id": "meta-llama/llama-4-maverick-17b-128e-instruct", "owned_by": "meta"},
    {"id": "llama-3.3-70b-versatile", "owned_by": "meta"},
    {"id": "llama-3.1-8b-instant", "owned_by": "meta"},
    {"id": "llama-3.2-90b-vision-preview", "owned_by": "meta"},
    {"id": "deepseek-r1-distill-llama-70b", "owned_by": "deepseek"},
    {"id": "qwen/qwen3-32b", "owned_by": "qwen"},
]


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    logger.info(f"📨 Request for model: {request.model}")
    try:
        msgs = [{"role": m.role, "content": m.content} for m in request.messages]
        response_text = run_agent(msgs, request.model)

        return ChatCompletionResponse(
            model=request.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=response_text),
                )
            ],
        )
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {"id": m["id"], "object": "model", "created": 1700000000, "owned_by": m["owned_by"]}
            for m in GROQ_MODELS
        ],
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
