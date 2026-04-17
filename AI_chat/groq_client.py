import json
import ssl
import urllib.error
import urllib.request

from . import config


def chat_completion(messages: list[dict]) -> str:
    """
    Gọi Groq OpenAI-compatible chat completions.
    messages: [{"role": "system"|"user"|"assistant", "content": "..."}, ...]
    """
    key = (config.GROQ_API_KEY or "").strip()
    if not key:
        raise ValueError("Chưa điền GROQ_API_KEY trong AI_chat/config.py")

    body = json.dumps(
        {
            "model": config.GROQ_MODEL,
            "messages": messages,
            "temperature": 0.6,
            "max_tokens": 512,
        },
        ensure_ascii=False,
    ).encode("utf-8")

    req = urllib.request.Request(
        config.GROQ_API_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "AIChat/1.0 (Python)",
        },
    )

    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        if not err_body.strip():
            err_body = e.reason or "<no body>"
        detail = ""
        if e.code == 403 and "1010" in err_body:
            detail = " (possible invalid API key, wrong endpoint, or Cloudflare blocking)"
        raise RuntimeError(f"Groq HTTP {e.code}{detail}: {err_body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Lỗi kết nối Groq: {e}") from e

    data = json.loads(raw)
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("Groq không trả về choices")
    msg = choices[0].get("message") or {}
    content = (msg.get("content") or "").strip()
    if not content:
        raise RuntimeError("Groq trả về nội dung rỗng")
    return content
