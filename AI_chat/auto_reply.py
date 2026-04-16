"""
Hẹn giờ trả lời tự động: sau AUTO_REPLY_DELAY_MS nếu không có tin từ nhân viên (server),
gọi Groq và gửi tin cho máy trạm (ghi history_from='ai').

Lưu ý: signal Qt chỉ mang int/str — không mang socket qua luồng (tránh queued signal bị bỏ qua).
"""

from __future__ import annotations

import threading
import traceback
from typing import Any, Callable, Optional

from PyQt6.QtCore import QObject, QTimer, Qt, pyqtSignal

from . import config
from .groq_client import chat_completion


def _history_to_messages(history: list[dict]) -> list[dict]:
    """Chuyển chat_history server sang định dạng Groq."""
    out: list[dict] = [{"role": "system", "content": config.SYSTEM_PROMPT}]
    tail = history[-config.MAX_HISTORY_MESSAGES :]
    for h in tail:
        frm = h.get("from")
        text = (h.get("text") or "").strip()
        if not text:
            continue
        if frm == "client":
            out.append({"role": "user", "content": text})
        elif frm in ("server", "ai"):
            out.append({"role": "assistant", "content": text})
        elif frm == "order":
            out.append({"role": "user", "content": f"[Thông báo đơn hàng] {text}"})
    return out


def _should_send_auto_reply(history: list[dict]) -> bool:
    """Còn lượt khách chưa được nhân viên trả lời và chưa có bản trả lời AI sau tin khách cuối."""
    client_indices = [i for i, e in enumerate(history) if e.get("from") == "client"]
    if not client_indices:
        return False
    last_i = client_indices[-1]
    for j in range(last_i + 1, len(history)):
        if history[j].get("from") == "server":
            return False
    for j in range(last_i + 1, len(history)):
        if history[j].get("from") == "ai":
            return False
    return True


class AutoReplyCoordinator(QObject):
    """Chạy trên luồng GUI; gọi Groq trong thread phụ."""

    # pc_index (0-based), generation, nội dung — toàn int/str để queued cross-thread ổn định
    reply_ready = pyqtSignal(int, int, str)

    def __init__(
        self,
        server: Any,
        on_ai_sent: Optional[Callable[[Any, str], None]] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.server = server
        self.on_ai_sent = on_ai_sent
        self._gen: dict[int, int] = {}
        self.reply_ready.connect(self._deliver_reply, Qt.ConnectionType.QueuedConnection)

    def on_client_message_pc_index(self, pc_index_zero: int, _text: str) -> None:
        if not config.ENABLE_AUTO_REPLY:
            return
        if not (config.GROQ_API_KEY or "").strip():
            return
        if pc_index_zero < 0:
            return
        sock = self.server.get_client_socket_by_pc_index(pc_index_zero)
        if sock is None:
            return
        self._gen[pc_index_zero] = self._gen.get(pc_index_zero, 0) + 1
        gen = self._gen[pc_index_zero]
        delay = int(config.AUTO_REPLY_DELAY_MS)
        QTimer.singleShot(
            delay, lambda p=pc_index_zero, g=gen: self._timer_fired(p, g)
        )

    def on_staff_sent(self, sock: Any) -> None:
        """Hủy hẹn giờ đang chờ cho máy vừa được nhân viên gửi tin."""
        if sock is None or sock not in self.server.clients:
            return
        try:
            pc_index = list(self.server.clients.keys()).index(sock)
        except ValueError:
            return
        self._gen[pc_index] = self._gen.get(pc_index, 0) + 1

    def _timer_fired(self, pc_index: int, gen: int) -> None:
        if self._gen.get(pc_index) != gen:
            return
        sock = self.server.get_client_socket_by_pc_index(pc_index)
        if sock is None or sock not in self.server.clients:
            return
        history = self.server.clients[sock].get("chat_history", [])
        if not _should_send_auto_reply(history):
            return
        messages = _history_to_messages(history)
        if len(messages) <= 1:
            return

        def worker() -> None:
            try:
                text = chat_completion(messages).strip()
            except Exception as e:
                text = ""
                if getattr(config, "LOG_AUTO_REPLY_ERRORS", True):
                    print(f"[AI_chat] Groq lỗi: {e}")
                    traceback.print_exc()
            self.reply_ready.emit(pc_index, gen, text)

        threading.Thread(target=worker, daemon=True).start()

    def _deliver_reply(self, pc_index: int, gen: int, text: str) -> None:
        if self._gen.get(pc_index) != gen:
            return
        sock = self.server.get_client_socket_by_pc_index(pc_index)
        if sock is None or sock not in self.server.clients or not text:
            return
        history = self.server.clients[sock].get("chat_history", [])
        if not _should_send_auto_reply(history):
            return
        ok = self.server.send_chat_to_client(sock, text, history_from="ai")
        if ok and self.on_ai_sent:
            self.on_ai_sent(sock, text)
