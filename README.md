# Tatweer Real Estate Customer Agent

AI-powered customer assistant for **Tatweer Real Estate** (تطوير العقارية). Answers common customer questions about projects, payment plans, site visits, financing, and after-sales support in **English and Arabic**.

## Features

- Web chat UI with quick prompts
- Bilingual support (auto-detects Arabic/English)
- Built-in Tatweer knowledge base (projects, FAQs, contact info)
- Optional OpenAI integration for richer conversational replies
- FastAPI backend with `/api/chat` endpoint

## Quick start

```bash
cd tatweer-real-estate-agent
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and add your `OPENAI_API_KEY` for AI-powered responses. The agent still works without it using the built-in knowledge base.

Run the server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

## API

### `POST /api/chat`

```json
{
  "message": "What payment plans do you offer?",
  "history": [
    { "role": "user", "content": "Hello" },
    { "role": "assistant", "content": "Hello! How can I help?" }
  ]
}
```

Response:

```json
{
  "reply": "...",
  "language": "en",
  "source": "knowledge_base"
}
```

### `GET /api/company`

Returns company profile, projects, and whether LLM mode is enabled.

## Customize Tatweer content

Edit `app/knowledge/tatweer_kb.json` to update:

- Company contact details
- Project listings and highlights
- FAQ answers
- Greeting and fallback messages

## Project structure

```
tatweer-real-estate-agent/
├── app/
│   ├── agent.py          # Agent logic + knowledge matching
│   ├── config.py         # Environment settings
│   ├── main.py           # FastAPI app
│   ├── knowledge/
│   │   └── tatweer_kb.json
│   └── static/           # Chat UI
├── requirements.txt
└── .env.example
```

## Next steps

- Connect to your CRM for lead capture
- Add WhatsApp or website widget embed
- Replace sample project data with live Tatweer inventory
- Deploy to Azure App Service or Container Apps
