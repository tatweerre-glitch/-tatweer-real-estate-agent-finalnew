from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from openai import OpenAI

from app.config import settings

KB_PATH = Path(__file__).resolve().parent / "knowledge" / "tatweer_kb.json"

ARABIC_RE = re.compile(r"[\u0600-\u06FF]")


def load_knowledge() -> dict[str, Any]:
    with KB_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def detect_language(text: str) -> str:
    return "ar" if ARABIC_RE.search(text) else "en"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _score_faq(message: str, faq: dict[str, Any]) -> int:
    normalized = _normalize(message)
    score = 0
    for topic in faq.get("topics", []):
        topic_norm = _normalize(str(topic))
        if topic_norm in normalized:
            score += 3
        elif any(part in normalized for part in topic_norm.split()):
            score += 1
    return score


def _match_faq(message: str, language: str) -> str | None:
    kb = load_knowledge()
    best_score = 0
    best_answer: str | None = None
    answer_key = f"answer_{language}"

    for faq in kb.get("faqs", []):
        score = _score_faq(message, faq)
        if score > best_score:
            best_score = score
            best_answer = faq.get(answer_key) or faq.get("answer_en")

    return best_answer if best_score >= 2 else None


def _match_project(message: str, language: str) -> str | None:
    kb = load_knowledge()
    normalized = _normalize(message)
    name_key = f"name_{language}"
    highlights_key = f"highlights_{language}"

    for project in kb.get("projects", []):
        names = [
            _normalize(project.get("name_en", "")),
            _normalize(project.get("name_ar", "")),
            _normalize(project.get("id", "").replace("-", " ")),
        ]
        if any(name and name in normalized for name in names):
            highlights = project.get(highlights_key) or project.get("highlights_en", [])
            bullets = "\n".join(f"- {item}" for item in highlights)
            label = project.get(name_key) or project.get("name_en")
            status = project.get("status", "available").replace("_", " ")
            return (
                f"**{label}** ({project.get('city')}, {status})\n"
                f"Unit types: {', '.join(project.get('units', []))}\n"
                f"{bullets}"
            )
    return None


def _is_greeting(message: str) -> bool:
    normalized = _normalize(message)
    greetings = {
        "hi",
        "hello",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
        "marhaba",
        "salam",
        "assalamu alaikum",
        "السلام عليكم",
        "مرحبا",
        "اهلا",
        "أهلا",
    }
    return normalized in greetings or any(normalized.startswith(g) for g in greetings)


def _build_system_prompt(language: str) -> str:
    kb = load_knowledge()
    company = kb["company"]
    projects_summary = []
    for project in kb.get("projects", []):
        name = project.get(f"name_{language}") or project.get("name_en")
        projects_summary.append(
            f"- {name} ({project.get('city')}): {project.get('status')}, units: {', '.join(project.get('units', []))}"
        )

    lang_instruction = (
        "Respond in Arabic when the customer writes in Arabic; otherwise respond in English."
        if language == "ar"
        else "Respond in English unless the customer clearly writes in Arabic."
    )

    return f"""You are a helpful customer service agent for {settings.company_name}.

Company: {company.get('name_en')} / {company.get('name_ar')}
Phone: {company.get('phone')}
Email: {company.get('email')}
Hours: {company.get('hours_en')}

Projects:
{chr(10).join(projects_summary)}

Rules:
- Be professional, warm, and concise.
- Only answer using Tatweer-related information. Do not invent prices, unit numbers, or legal terms.
- For booking visits or financing, collect name and phone number and explain next steps.
- If you cannot answer, offer to connect the customer to sales at {company.get('phone')}.
- {lang_instruction}
"""


def _rule_based_reply(message: str, language: str) -> str | None:
    kb = load_knowledge()
    intents = kb.get("intents", {})

    if _is_greeting(message):
        return intents.get(f"greeting_{language}") or intents.get("greeting_en")

    project_answer = _match_project(message, language)
    if project_answer:
        prefix = "Here are details about the project:" if language == "en" else "إليك تفاصيل المشروع:"
        return f"{prefix}\n\n{project_answer}"

    faq_answer = _match_faq(message, language)
    if faq_answer:
        return faq_answer

    normalized = _normalize(message)
    if any(word in normalized for word in ["project", "projects", "مشروع", "مشاريع"]):
        lines = []
        for project in kb.get("projects", []):
            name = project.get(f"name_{language}") or project.get("name_en")
            lines.append(f"- **{name}** — {project.get('city')} ({project.get('status')})")
        header = "Our current projects:" if language == "en" else "مشاريعنا الحالية:"
        return header + "\n" + "\n".join(lines)

    return None


class TatweerAgent:
    def __init__(self) -> None:
        self.kb = load_knowledge()

    def reply(self, message: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
        history = history or []
        language = detect_language(message)
        rule_reply = _rule_based_reply(message, language)

        if rule_reply and not settings.openai_api_key:
            return {
                "reply": rule_reply,
                "language": language,
                "source": "knowledge_base",
            }

        if settings.openai_api_key:
            try:
                client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
                messages = [{"role": "system", "content": _build_system_prompt(language)}]
                for turn in history[-8:]:
                    messages.append({"role": turn["role"], "content": turn["content"]})
                messages.append({"role": "user", "content": message})

                if rule_reply:
                    messages.append(
                        {
                            "role": "system",
                            "content": f"Relevant Tatweer knowledge you should use:\n{rule_reply}",
                        }
                    )

                completion = client.chat.completions.create(
                    model=settings.openai_model,
                    messages=messages,
                    temperature=0.3,
                )
                content = completion.choices[0].message.content or ""
                return {
                    "reply": content.strip(),
                    "language": language,
                    "source": "llm",
                }
            except Exception:
                if rule_reply:
                    return {
                        "reply": rule_reply,
                        "language": language,
                        "source": "knowledge_base",
                    }

        fallback = self.kb.get("intents", {}).get(f"fallback_{language}") or self.kb.get("intents", {}).get(
            "fallback_en", ""
        )
        return {
            "reply": rule_reply or fallback,
            "language": language,
            "source": "knowledge_base",
        }
