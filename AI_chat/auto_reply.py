"""
Hẹn giờ trả lời tự động: sau AUTO_REPLY_DELAY_MS nếu không có tin từ nhân viên (server),
gọi Groq và gửi tin cho máy trạm (ghi history_from='ai').

Lưu ý: signal Qt chỉ mang int/str — không mang socket qua luồng (tránh queued signal bị bỏ qua).
"""

from __future__ import annotations

import json
import re
import threading
import traceback
from typing import Any, Callable, Optional

from PyQt6.QtCore import QObject, QTimer, Qt, pyqtSignal

from . import config
from .groq_client import chat_completion


def _format_menu_context(menu_items: list[dict]) -> str:
    if not menu_items:
        return ""
    lines = ["Danh sách sản phẩm và đồ uống hiện có:"]
    for item in menu_items[:16]:
        name = str(item.get("name") or "?").strip()
        price = int(item.get("price") or 0)
        lines.append(f"  • {name} — {price:,} đ")
    lines.append(
        "Nếu khách hỏi gợi ý, hãy đề xuất đồ uống/món ăn phù hợp với lịch sử đặt món và sở thích.")
    return "\n".join(lines)


def _looks_like_order_request(text: str) -> bool:
    """Phát hiện yêu cầu đặt hàng. Có thể là:
    - 'đặt/gọi/mua/order/muốn/cho' + 'món/nước/đồ uống/combo/gói'
    - Hoặc số + tên đồ uống/món ăn (vd: '2 trà sữa', '5 bánh mì')
    - Hoặc trực tiếp tên món + số lượng
    """
    if not text or not isinstance(text, str):
        return False
    s = text.lower()
    
    # Cách 1: Có từ khóa hành động + từ khóa loại đồ
    if re.search(r"\b(đặt|gọi|mua|order|muốn|cho|tôi.*cần|bạn.*tôi)\b", s):
        if re.search(r"\b(món|nước|đồ uống|combo|gói|cà phê|trà|cơm|bánh|ăn|uống)\b", s):
            return True
        # Hoặc có số
        if re.search(r"\b([1-9]|10)\b", s):
            return True
    
    # Cách 2: Số + tên đồ 
    if re.search(r"\b([1-9]|10)\s+\w+", s):
        if re.search(r"(cà phê|trà|cơm|bánh|nước|bia|nước|đồ|combo|cup|cốc)", s):
            return True
    
    return False


def _menu_items_prompt(menu_items: list[dict]) -> str:
    if not menu_items:
        return ""
    lines = ["Danh sách sản phẩm hiện có (id - tên - giá):"]
    for item in menu_items[:40]:
        lines.append(
            f"{int(item.get('id', 0))} - {item.get('name', '?')} - {int(item.get('price', 0)):,} đ"
        )
    lines.append(
        "Nếu khách muốn đặt món, hãy chọn chính xác id và số lượng tương ứng."
    )
    return "\n".join(lines)


def _extract_json_object(text: str) -> dict | None:
    if not text or not isinstance(text, str):
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    chunk = text[start : end + 1]
    try:
        return json.loads(chunk)
    except json.JSONDecodeError:
        return None


def _extract_order_items(server: Any, sock: Any, user_text: str) -> list[dict]:
    if not _looks_like_order_request(user_text):
        print(f"[AI_chat] Not an order request: {user_text}")
        return []
    menu_items = server.menu_model.list_active_for_menu() if server and server.menu_model else []
    if not menu_items:
        print(f"[AI_chat] No menu items available")
        return []
    menu_context = _menu_items_prompt(menu_items)
    if not menu_context:
        print(f"[AI_chat] Empty menu context")
        return []

    messages = [
        {"role": "system", "content": config.ORDER_EXTRACTION_SYSTEM_PROMPT},
        {"role": "system", "content": menu_context},
        {"role": "user", "content": user_text},
    ]
    try:
        print(f"[AI_chat] Calling Groq to extract order items from: {user_text}")
        output = chat_completion(messages)
        print(f"[AI_chat] Groq response: {output}")
    except Exception as ex:
        print(f"[AI_chat] Error calling Groq: {ex}")
        return []

    parsed = _extract_json_object(output)
    print(f"[AI_chat] Parsed JSON: {parsed}")
    if not parsed or not isinstance(parsed.get("items"), list):
        print(f"[AI_chat] Invalid JSON structure")
        return []
    items = []
    for item in parsed["items"]:
        if not isinstance(item, dict):
            continue
        try:
            pid = int(item.get("id", 0))
            qty = int(item.get("qty", 0))
        except (TypeError, ValueError):
            continue
        if pid <= 0 or qty <= 0:
            continue
        items.append({"id": pid, "qty": qty})
    return items


def _format_order_for_display(server, items: list[dict]) -> str:
    """Định dạng danh sách sản phẩm để hiển thị dạng: 'Bubble Tea x2, Cà phê x1'."""
    if not items or not server or not server.menu_model:
        return ""
    menu_items = {item.get("id"): item for item in server.menu_model.list_active_for_menu()}
    parts = []
    for item in items:
        item_id = item.get("id")
        qty = item.get("qty", 1)
        if item_id in menu_items:
            name = menu_items[item_id].get("name", f"ID {item_id}")
            parts.append(f"{name} x{qty}")
    return ", ".join(parts) if parts else ""


def _parse_order_history(history: list[dict]) -> str:
    orders: list[str] = []
    ordered_items: list[str] = []
    balance: Optional[int] = None

    for h in history:
        if h.get("from") != "order":
            continue
        text = (h.get("text") or "").strip()
        if not text:
            continue
        orders.append(text)
        for line in text.splitlines():
            match = re.match(r"^\s*•\s*(.+?)\s*×\s*\d+", line)
            if match:
                item_name = match.group(1).strip()
                if item_name and item_name not in ordered_items:
                    ordered_items.append(item_name)
        match = re.search(r"Số dư còn:\s*([0-9.,]+)", text)
        if match:
            try:
                balance = int(match.group(1).replace(".", "").replace(",", ""))
            except ValueError:
                pass

    if not orders:
        return ""

    lines = ["Lịch sử đơn hàng gần nhất:"]
    for text in orders[-3:]:
        lines.append(text)
    if ordered_items:
        lines.append("Món đã gọi trước đây: " + ", ".join(ordered_items))
    if balance is not None:
        lines.append(f"Số dư còn được ghi nhận: {balance:,} đ")
    return "\n".join(lines)


def _format_session_context(server: Any, sock: Any) -> str:
    if sock is None or sock not in server.clients:
        return ""
    data = server.clients[sock]
    lines: list[str] = ["Thông tin phiên khách hàng:"]
    username = data.get("user")
    if username:
        lines.append(f"- Tài khoản: {username}")
        try:
            user = server.user_model.get_user(username)
            if user is not None:
                balance = int(float(user.get("balance") or 0))
                lines.append(f"- Số dư hiện tại: {balance:,} đ")
                user_type = user.get("type")
                if user_type:
                    lines.append(f"- Loại khách hàng: {user_type}")
        except Exception:
            pass
    usage = data.get("usage")
    try:
        usage_val = float(usage or 0)
    except (TypeError, ValueError):
        usage_val = 0.0
    if usage_val > 0:
        hours = usage_val / 3600.0
        lines.append(f"- Thời gian sử dụng hiện tại: {hours:.2f} giờ")
    try:
        rate = int(server.hourly_rate_fn() or 0)
        if rate > 0:
            lines.append(f"- Giá giờ hiện tại: {rate:,} đ/giờ")
    except Exception:
        pass
    if len(lines) <= 1:
        return ""
    lines.append(
        "Nếu khách hỏi về gói giờ, đề xuất 1h, 2h, 4h, 8h, nêu ưu điểm từng gói.")
    return "\n".join(lines)


def _history_to_messages(server: Any, sock: Any, history: list[dict]) -> list[dict]:
    """Chuyển chat_history server sang định dạng Groq."""
    out: list[dict] = [{"role": "system", "content": config.SYSTEM_PROMPT}]
    menu_ctx = _format_menu_context(server.menu_model.list_active_for_menu())
    if menu_ctx:
        out.append({"role": "system", "content": menu_ctx})
    session_ctx = _format_session_context(server, sock)
    if session_ctx:
        out.append({"role": "system", "content": session_ctx})
    order_ctx = _parse_order_history(history)
    if order_ctx:
        out.append({"role": "system", "content": order_ctx})

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
        messages = _history_to_messages(self.server, sock, history)
        if len(messages) <= 1:
            return

        def worker() -> None:
            try:
                text = ""
                last_client_text = ""
                for h in reversed(history):
                    if h.get("from") == "client":
                        last_client_text = (h.get("text") or "").strip()
                        break
                print(f"[AI_chat] Last client message: {last_client_text}")
                if last_client_text:
                    looks_order = _looks_like_order_request(last_client_text)
                    print(f"[AI_chat] Looks like order? {looks_order}")
                    items = _extract_order_items(self.server, sock, last_client_text)
                    print(f"[AI_chat] Extracted items: {items}")
                    if items:
                        payload = json.dumps(
                            {"items": items}, ensure_ascii=False, separators=(",", ":")
                        )
                        print(f"[AI_chat] Submitting ORDER_SUBMIT: {payload}")
                        try:
                            self.server._process_message(sock, f"ORDER_SUBMIT:{payload}")
                            print(f"[AI_chat] ORDER_SUBMIT sent successfully")
                            # Lưu đơn hàng vào lịch sử AI
                            order_display = _format_order_for_display(self.server, items)
                            if order_display:
                                order_msg = f"🤖 Đã gửi: {order_display}"
                                self.server.send_chat_to_client(sock, order_msg, history_from="ai_order")
                        except Exception as ex:
                            print(f"[AI_chat] Error sending ORDER_SUBMIT: {ex}")
                            import traceback
                            traceback.print_exc()
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
