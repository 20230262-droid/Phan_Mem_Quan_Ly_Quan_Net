"""Mã hóa nội dung chat một dòng (UTF-8 → base64) cho giao thức CHAT:..."""

import base64
from typing import Optional


def encode_chat(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def decode_chat(payload: str) -> Optional[str]:
    try:
        return base64.b64decode(payload.encode("ascii")).decode("utf-8")
    except Exception:
        return None
