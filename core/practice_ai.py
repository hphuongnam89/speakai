import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class PracticeGenerationError(Exception):
    """A safe, user-displayable error while creating an AI practice set."""


def generate_practice_questions(*, level, topic, question_count):
    model = os.getenv("LOCAL_AI_MODEL", "ornith-1.5:9b")
    endpoint = os.getenv("LOCAL_AI_BASE_URL", "http://host.docker.internal:11434").rstrip("/") + "/api/chat"
    requested_topic = topic or "choose one suitable everyday topic"
    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "format": "json",
        "options": {"temperature": 0.6},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You create original English speaking PRACTICE prompts, not official exam questions. "
                    "Do not claim alignment with a specific textbook, institution, or exam. "
                    "Return only valid JSON with keys topic and questions. Each question must have prompt "
                    "and candidate_instructions strings. Avoid sensitive personal data and keep prompts "
                    "appropriate for the specified CEFR level."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Create exactly {question_count} distinct English speaking practice questions for CEFR {level}. "
                    f"Topic: {requested_topic}. Use concise natural language. "
                    'JSON shape: {"topic":"...","questions":[{"prompt":"...",'
                    '"candidate_instructions":"..."}]}'
                ),
            },
        ],
    }
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=int(os.getenv("LOCAL_AI_TIMEOUT_SECONDS", "150"))) as response:
            result = json.loads(response.read().decode("utf-8"))
        content = json.loads(result["message"]["content"])
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError, TypeError, OSError) as exc:
        raise PracticeGenerationError(
            "Không kết nối được Local AI hoặc AI trả dữ liệu không hợp lệ. Hãy kiểm tra Ollama trên MacBook rồi thử lại."
        ) from exc

    questions = content.get("questions") if isinstance(content, dict) else None
    if not isinstance(questions, list) or len(questions) != question_count:
        raise PracticeGenerationError("AI chưa tạo đủ số câu hỏi. Hãy thử lại hoặc giảm số câu.")
    normalized = []
    for question in questions:
        if not isinstance(question, dict):
            raise PracticeGenerationError("AI trả cấu trúc câu hỏi không hợp lệ.")
        prompt = question.get("prompt")
        instructions = question.get("candidate_instructions", "")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 1200:
            raise PracticeGenerationError("AI trả nội dung câu hỏi không hợp lệ.")
        if not isinstance(instructions, str) or len(instructions) > 1000:
            raise PracticeGenerationError("AI trả hướng dẫn trả lời không hợp lệ.")
        normalized.append({"prompt": prompt.strip(), "candidate_instructions": instructions.strip()})
    actual_topic = content.get("topic", "")
    if not isinstance(actual_topic, str):
        actual_topic = ""
    return {"model": model, "topic": (actual_topic or topic or "Chủ đề ngẫu nhiên")[:120], "questions": normalized}
