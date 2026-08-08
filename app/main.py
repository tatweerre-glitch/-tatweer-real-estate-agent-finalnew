from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.agent import TatweerAgent, load_knowledge
from app.config import settings
from app.conversation import conversation_manager
from app.routers.webhooks import router as webhooks_router

STATIC_DIR = Path(__file__).resolve().parent / "static"
agent = TatweerAgent()

app = FastAPI(
    title="Tatweer Real Estate Customer Agent",
    description="Multi-channel AI assistant for Tatweer Real Estate customer inquiries",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhooks_router)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    language: str
    source: str
    photos: list[str] = Field(default_factory=list)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "company": settings.company_name}


@app.get("/api/company")
def company_info() -> dict:
    kb = load_knowledge()
    return {
        "company": kb["company"],
        "projects": kb["projects"],
        "llm_enabled": bool(settings.openai_api_key),
        "channels": {
            "web": True,
            "telegram": bool(settings.telegram_bot_token),
            "whatsapp": bool(settings.twilio_whatsapp_from),
            "phone": bool(settings.twilio_phone_number),
        },
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    response = await conversation_manager.handle_message("web", "web-user", message)
    return ChatResponse(
        reply=response.reply,
        language=response.language,
        source=response.source,
        photos=response.photos,
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
