import base64
import json
import socket
import threading
import time
from mvc.models.menu_product_model import MenuProductModel
from mvc.models.user_model import UserModel
from mvc.ui.chat_codec import encode_chat, decode_chat


def _format_order_chat_notice(
    pc_index: int,
    username: str,
    line_details: list,
    balance_after: float | None = None,
) -> str:
    """Nội dung thông báo đơn trên máy chủ (PC, TK, món, tạm tính, trừ ví) — không gửi xuống client."""
    lines = [f"【Đặt món】PC số {pc_index}"]
    u = (username or "").strip()
    if u:
        lines.append(f"Tài khoản: {u}")
    lines.append("Chi tiết:")
    total = 0
    for x in line_details:
        if not isinstance(x, dict):
            continue
        name = str(x.get("name") or "?").strip() or "?"
        try:
            qty = int(x.get("qty", 0))
        except (TypeError, ValueError):
            qty = 0
        try:
            sub = int(x.get("subtotal", 0))
        except (TypeError, ValueError):
            sub = 0
        total += sub
        lines.append(f"  • {name} × {qty}  ({sub:,} đ)")
    lines.append(f"Tạm tính: {total:,} đ")
    if balance_after is not None and total > 0:
        lines.append(
            f"Thanh toán ví: -{total:,} đ | Số dư còn: {int(balance_after):,} đ"
        )
    return "\n".join(lines)


def _format_order_pending_notice(
    order_id: int,
    pc_index: int,
    username: str,
    line_details: list,
    total_vnd: int,
) -> str:
    """Thông báo đơn chờ quầy xác nhận (chưa trừ tiền)."""
    lines = [
        f"【Chờ xác nhận】Đơn #{order_id} · PC số {pc_index} · Chưa trừ ví"
    ]
    u = (username or "").strip()
    if u:
        lines.append(f"Tài khoản: {u}")
    lines.append("Chi tiết:")
    total = 0
    for x in line_details:
        if not isinstance(x, dict):
            continue
        name = str(x.get("name") or "?").strip() or "?"
        try:
            qty = int(x.get("qty", 0))
        except (TypeError, ValueError):
            qty = 0
        try:
            sub = int(x.get("subtotal", 0))
        except (TypeError, ValueError):
            sub = 0
        total += sub
        lines.append(f"  • {name} × {qty}  ({sub:,} đ)")
    lines.append(f"Tạm tính: {total:,} đ (sẽ trừ khi quầy xác nhận)")
    return "\n".join(lines)


class Server:
    def __init__(self, host='0.0.0.0', port=8888, user_model=None):
        self.host = host
        self.port = port
        self.server_socket = None
        self.clients = {}  # {client_socket: {'status': str, 'usage': float, 'last_seen': time}}
        self.running = False
        self.on_client_update = None
        self.user_model = user_model if user_model is not None else UserModel()
        self.menu_model = MenuProductModel()
        self.hourly_rate_fn = lambda: 15000
        self.on_chat_from_client = None
        self.on_remote_screenshot = None  # (client_socket, jpeg_bytes)
        self.on_remote_admin_text = None  # (client_socket, title, message) — lỗi chụp / kết quả kill
        self.on_order_from_client = None  # (client_socket, pc_index: int, summary: str)
        self._pending_orders_lock = threading.Lock()
        self._pending_orders: list = []
        self._next_pending_order_id = 1

    def _discard_pending_orders_for_socket(self, client_socket) -> None:
        with self._pending_orders_lock:
            self._pending_orders = [
                o
                for o in self._pending_orders
                if o.get("client_socket") is not client_socket
            ]

    def _forget_client(self, client_socket) -> None:
        self._discard_pending_orders_for_socket(client_socket)
        if client_socket in self.clients:
            del self.clients[client_socket]
        if self.on_client_update:
            self.on_client_update()

    def list_pending_orders(self) -> list[dict]:
        """Danh sách đơn chờ xác nhận (không chứa socket)."""
        with self._pending_orders_lock:
            return [
                {
                    "id": int(o["id"]),
                    "pc_index": int(o["pc_index"]),
                    "username": str(o.get("username") or ""),
                    "total_vnd": int(o.get("total_vnd", 0)),
                    "summary": str(o.get("summary") or ""),
                }
                for o in self._pending_orders
            ]

    def confirm_pending_order(self, order_id: int) -> tuple[bool, str]:
        """Quầy xác nhận: trừ ví, ghi đơn SQL (nếu có), thông báo máy trạm."""
        with self._pending_orders_lock:
            po = None
            idx = -1
            for i, o in enumerate(self._pending_orders):
                if int(o["id"]) == int(order_id):
                    po = o
                    idx = i
                    break
            if po is None:
                return False, "Không tìm thấy đơn"
            self._pending_orders.pop(idx)
        sock = po["client_socket"]
        if sock not in self.clients:
            return False, "Máy trạm đã ngắt kết nối (đơn đã gỡ khỏi danh sách chờ)."
        uname = (po.get("username") or "").strip()
        total = float(po.get("total_vnd", 0) or 0)
        pc_index = int(po.get("pc_index", 0) or 0)
        summary = po.get("summary") or ""
        line_details = po.get("line_details") or []
        ok_pay, pay_err, new_bal = self.user_model.try_pay_order(uname, total)
        if not ok_pay:
            with self._pending_orders_lock:
                self._pending_orders.insert(0, po)
            return False, pay_err or "Không trừ được ví"
        try:
            self.menu_model.persist_order(pc_index, summary, line_details)
        except Exception as ex:
            self.user_model.refund_order_payment(uname, total)
            with self._pending_orders_lock:
                self._pending_orders.insert(0, po)
            u = self.user_model.get_user(uname)
            ut = u.get("type") if u else None
            for d in self.clients.values():
                if d.get("user") == uname:
                    d["user_type"] = ut
            if self.on_client_update:
                self.on_client_update()
            return False, f"Không lưu đơn: {ex}"[:200]
        u = self.user_model.get_user(uname)
        ut = u.get("type") if u else None
        for d in self.clients.values():
            if d.get("user") == uname:
                d["user_type"] = ut
        if self.on_client_update:
            self.on_client_update()
        notice = _format_order_chat_notice(
            pc_index, uname, line_details, balance_after=new_bal
        )
        self.append_local_chat_history(
            sock, notice, history_from="order", bump_unread=True
        )
        if self.on_order_from_client:
            self.on_order_from_client(sock, pc_index, notice)
        self._client_sendall(sock, b"ORDER_CONFIRMED\n")
        self._client_sendall(sock, f"BALANCE:{new_bal}\n".encode("utf-8"))
        return True, ""

    def cancel_pending_order(self, order_id: int) -> tuple[bool, str]:
        """Quầy hủy đơn chờ (không trừ tiền)."""
        with self._pending_orders_lock:
            po = None
            idx = -1
            for i, o in enumerate(self._pending_orders):
                if int(o["id"]) == int(order_id):
                    po = o
                    idx = i
                    break
            if po is None:
                return False, "Không tìm thấy đơn"
            self._pending_orders.pop(idx)
        sock = po["client_socket"]
        if sock in self.clients:
            self._client_sendall(
                sock,
                "ORDER_CANCELLED:Quầy đã hủy đơn.\n".encode("utf-8"),
            )
        return True, ""

    @staticmethod
    def _parse_register_message(message):
        """REGISTER:user:pass hoặc REGISTER:user:pass:type (type = normal|vip; cho phép ':' trong mật khẩu)."""
        payload = message[9:].strip()
        parts = payload.split(":")
        if len(parts) < 2:
            return None
        if len(parts) == 2:
            return parts[0], parts[1], "normal"
        user_type = parts[-1]
        if user_type not in ("normal", "vip"):
            user_type = "normal"
        return parts[0], ":".join(parts[1:-1]), user_type

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True
        print(f"Server started on {self.host}:{self.port}")

        # Start accepting clients
        accept_thread = threading.Thread(target=self._accept_clients)
        accept_thread.daemon = True
        accept_thread.start()

    def stop(self):
        self.running = False
        with self._pending_orders_lock:
            self._pending_orders.clear()
        for client in list(self.clients.keys()):
            client.close()
        if self.server_socket:
            self.server_socket.close()
        self.clients.clear()

    def _accept_clients(self):
        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                print(f"Client connected: {addr}")
                self.clients[client_socket] = {
                    'status': 'CONNECTED',
                    'usage': 0,
                    'last_seen': time.time(),
                    'ip': addr[0],
                    'send_lock': threading.Lock(),
                    'user_type': None,
                }
                if self.on_client_update:
                    self.on_client_update()
                # Start handling client
                client_thread = threading.Thread(target=self._handle_client, args=(client_socket,))
                client_thread.daemon = True
                client_thread.start()
            except:
                break

    def _client_sendall(self, client_socket, payload: bytes) -> bool:
        if client_socket not in self.clients:
            return False
        lock = self.clients[client_socket].get("send_lock")
        try:
            if lock:
                with lock:
                    client_socket.sendall(payload)
            else:
                client_socket.sendall(payload)
            return True
        except Exception:
            return False

    def _push_hourly_rate(self, client_socket):
        try:
            rate = int(self.hourly_rate_fn())
            if rate < 0:
                rate = 0
            self._client_sendall(client_socket, f"RATE:{rate}\n".encode("utf-8"))
        except Exception:
            pass

    def broadcast_hourly_rate(self):
        line = None
        try:
            rate = int(self.hourly_rate_fn())
            if rate < 0:
                rate = 0
            line = f"RATE:{rate}\n".encode("utf-8")
        except Exception:
            line = b"RATE:15000\n"
        for sock in list(self.clients.keys()):
            if not self._client_sendall(sock, line):
                pass

    def _handle_client(self, client_socket):
        self._push_hourly_rate(client_socket)
        buffer = ""
        while self.running and client_socket in self.clients:
            try:
                data = client_socket.recv(1024)
                if not data:
                    break
                buffer += data.decode('utf-8')
                while '\n' in buffer:
                    message, buffer = buffer.split('\n', 1)
                    self._process_message(client_socket, message.strip())
            except:
                break
        # Client disconnected
        if client_socket in self.clients:
            self._forget_client(client_socket)

    def _process_message(self, client_socket, message):
        if message.startswith("STATUS:"):
            status = message[7:]
            if client_socket in self.clients:
                self.clients[client_socket]['status'] = status
                self.clients[client_socket]['last_seen'] = time.time()
                if self.on_client_update:
                    self.on_client_update()
        elif message.startswith("USAGE:"):
            try:
                usage = float(message[6:])
                if client_socket in self.clients:
                    self.clients[client_socket]['usage'] = usage
                    # Add to history if user assigned
                    if 'user' in self.clients[client_socket]:
                        username = self.clients[client_socket]['user']
                        machine_id = list(self.clients.keys()).index(client_socket) + 1
                        self.user_model.add_usage_history(username, machine_id, usage)
                if self.on_client_update:
                    self.on_client_update()
            except ValueError:
                pass
        elif message.startswith("CHAT:"):
            text = decode_chat(message[5:])
            if text is None or client_socket not in self.clients:
                return
            data = self.clients[client_socket]
            data.setdefault("chat_history", []).append({"from": "client", "text": text})
            data["chat_unread"] = data.get("chat_unread", 0) + 1
            if self.on_chat_from_client:
                self.on_chat_from_client(client_socket, text)
        elif message.startswith("REGISTER:"):
            parsed = self._parse_register_message(message)
            if parsed:
                username, password, user_type = parsed
                success, msg = self.user_model.register(username, password, user_type)
                response = "REGISTER_SUCCESS" if success else f"REGISTER_FAILED:{msg}"
                self._client_sendall(client_socket, f"{response}\n".encode("utf-8"))
                if self.on_client_update:
                    self.on_client_update()
        elif message.startswith("LOGIN:"):
            parts = message[6:].split(":")
            if len(parts) == 2:
                username, password = parts
                success, user = self.user_model.login(username, password)
                if success:
                    self.clients[client_socket]['user'] = username
                    self.clients[client_socket]['user_type'] = user.get('type')
                    response = f"LOGIN_SUCCESS:{user['type']}"
                else:
                    response = "LOGIN_FAILED"
                self._client_sendall(client_socket, f"{response}\n".encode("utf-8"))
                if success:
                    b = float(user.get("balance", 0) or 0)
                    self._client_sendall(
                        client_socket, f"BALANCE:{b}\n".encode("utf-8")
                    )
                if self.on_client_update:
                    self.on_client_update()
        elif message.startswith("TOPUP:"):
            parts = message[6:].split(":")
            if len(parts) == 2:
                username, amount = parts[0], float(parts[1])
                success, msg = self.user_model.top_up(username, amount)
                response = "TOPUP_SUCCESS" if success else f"TOPUP_FAILED:{msg}"
                self._client_sendall(client_socket, f"{response}\n".encode("utf-8"))
                if success:
                    u = self.user_model.get_user(username)
                    ut = u.get("type") if u else None
                    for d in self.clients.values():
                        if d.get("user") == username:
                            d["user_type"] = ut
                    if (
                        client_socket in self.clients
                        and self.clients[client_socket].get("user") == username
                        and u
                    ):
                        self._client_sendall(
                            client_socket,
                            f"BALANCE:{float(u.get('balance', 0) or 0)}\n".encode(
                                "utf-8"
                            ),
                        )
                if self.on_client_update:
                    self.on_client_update()
        elif message == "GET_MENU":
            if client_socket not in self.clients or not self.clients[client_socket].get(
                "user"
            ):
                self._client_sendall(
                    client_socket,
                    "MENU_FAIL:Đăng nhập tài khoản trước khi xem thực đơn.\n".encode(
                        "utf-8"
                    ),
                )
                return
            prods = self.menu_model.list_active_for_menu()
            payload = json.dumps(prods, ensure_ascii=False, separators=(",", ":"))
            self._client_sendall(
                client_socket, f"MENU_JSON:{payload}\n".encode("utf-8")
            )
        elif message.startswith("ORDER_SUBMIT:"):
            if client_socket not in self.clients or not self.clients[client_socket].get(
                "user"
            ):
                self._client_sendall(
                    client_socket,
                    "ORDER_FAIL:Chưa đăng nhập\n".encode("utf-8"),
                )
                return
            raw = message[13:].strip()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                self._client_sendall(
                    client_socket,
                    "ORDER_FAIL:Dữ liệu đơn không hợp lệ\n".encode("utf-8"),
                )
                return
            items = data.get("items") if isinstance(data, dict) else None
            summary, err, line_details = self.menu_model.validate_order(items or [])
            if err:
                safe = err.replace("\n", " ").strip()[:200]
                self._client_sendall(
                    client_socket, f"ORDER_FAIL:{safe}\n".encode("utf-8")
                )
                return
            try:
                pc_index = list(self.clients.keys()).index(client_socket) + 1
            except ValueError:
                pc_index = 0
            uname = (self.clients[client_socket].get("user") or "").strip()
            total_vnd = sum(
                int(x.get("subtotal", 0))
                for x in line_details
                if isinstance(x, dict)
            )
            info = self.user_model.get_user(uname)
            bal0 = float(info.get("balance", 0) or 0) if info else 0.0
            if bal0 < float(total_vnd):
                self._client_sendall(
                    client_socket,
                    f"ORDER_FAIL:Số dư không đủ (còn {bal0:,.0f} đ). Vui lòng nạp tiền tại quầy.\n".encode(
                        "utf-8"
                    ),
                )
                return
            with self._pending_orders_lock:
                oid = self._next_pending_order_id
                self._next_pending_order_id += 1
                self._pending_orders.append(
                    {
                        "id": oid,
                        "client_socket": client_socket,
                        "pc_index": pc_index,
                        "username": uname,
                        "summary": summary or "",
                        "line_details": [dict(x) for x in line_details],
                        "total_vnd": int(total_vnd),
                    }
                )
            notice = _format_order_pending_notice(
                oid, pc_index, uname, line_details, int(total_vnd)
            )
            self.append_local_chat_history(
                client_socket, notice, history_from="order", bump_unread=True
            )
            if self.on_order_from_client:
                self.on_order_from_client(client_socket, pc_index, notice)
            self._client_sendall(client_socket, b"ORDER_PENDING\n")
            if self.on_client_update:
                self.on_client_update()
        elif message.startswith("SCREENSHOT_START:"):
            if client_socket not in self.clients:
                return
            try:
                total = int(message.split(":", 1)[1])
            except ValueError:
                return
            if total <= 0 or total > 5000:
                return
            self.clients[client_socket]["screenshot_rx"] = {"total": total, "parts": {}}
        elif message.startswith("SCREENSHOT_PART:"):
            if client_socket not in self.clients:
                return
            rx = self.clients[client_socket].get("screenshot_rx")
            if not rx:
                return
            rest = message[len("SCREENSHOT_PART:") :]
            idx_end = rest.find(":")
            if idx_end < 0:
                return
            try:
                part_idx = int(rest[:idx_end])
                payload = rest[idx_end + 1 :]
            except ValueError:
                return
            rx["parts"][part_idx] = payload
            if len(rx["parts"]) == rx["total"]:
                self._finalize_screenshot(client_socket, rx)
        elif message.startswith("SCREENSHOT_END"):
            pass
        elif message.startswith("SCREENSHOT_ERROR:"):
            err = message[len("SCREENSHOT_ERROR:") :][:500]
            if self.on_remote_admin_text:
                self.on_remote_admin_text(client_socket, "Chụp màn hình", err or "Lỗi không xác định")
        elif message.startswith("KILL_RESULT:"):
            rest = message[len("KILL_RESULT:") :]
            if rest == "OK":
                if self.on_remote_admin_text:
                    self.on_remote_admin_text(client_socket, "Tắt ứng dụng", "Đã gửi lệnh tắt (taskkill thành công).")
            elif rest.startswith("FAIL:"):
                detail = rest[5:][:500]
                if self.on_remote_admin_text:
                    self.on_remote_admin_text(client_socket, "Tắt ứng dụng", detail or "Thất bại")
            else:
                if self.on_remote_admin_text:
                    self.on_remote_admin_text(client_socket, "Tắt ứng dụng", rest[:500])
        elif message.startswith("LAUNCH_RESULT:"):
            rest = message[len("LAUNCH_RESULT:") :]
            if rest == "OK":
                if self.on_remote_admin_text:
                    self.on_remote_admin_text(
                        client_socket,
                        "Mở ứng dụng",
                        "Đã khởi chạy lệnh trên máy trạm (process tách khỏi client).",
                    )
            elif rest.startswith("FAIL:"):
                detail = rest[5:][:500]
                if self.on_remote_admin_text:
                    self.on_remote_admin_text(client_socket, "Mở ứng dụng", detail or "Thất bại")
            else:
                if self.on_remote_admin_text:
                    self.on_remote_admin_text(client_socket, "Mở ứng dụng", rest[:500])

    def _finalize_screenshot(self, client_socket, rx):
        try:
            total = rx["total"]
            parts = rx["parts"]
            b64 = "".join(parts[i] for i in range(total))
            jpeg_bytes = base64.b64decode(b64, validate=False)
        except Exception:
            if client_socket in self.clients:
                self.clients[client_socket].pop("screenshot_rx", None)
            if self.on_remote_admin_text:
                self.on_remote_admin_text(client_socket, "Chụp màn hình", "Không ghép được dữ liệu ảnh.")
            return
        if client_socket in self.clients:
            self.clients[client_socket].pop("screenshot_rx", None)
        if self.on_remote_screenshot:
            self.on_remote_screenshot(client_socket, jpeg_bytes)

    def disconnect_client(self, client_socket):
        """Đóng kết nối TCP với một máy trạm (quầy chủ động). Client sẽ mất kết nối và có thể kết nối lại."""
        if client_socket not in self.clients:
            return False
        try:
            client_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            client_socket.close()
        except OSError:
            pass
        return True

    def send_command(self, client_socket, command):
        if client_socket not in self.clients:
            return
        ok = self._client_sendall(client_socket, f"{command}\n".encode("utf-8"))
        if not ok and client_socket in self.clients:
            self._forget_client(client_socket)

    def append_local_chat_history(
        self,
        client_socket,
        text: str,
        history_from: str = "order",
        bump_unread: bool = False,
    ) -> bool:
        """Chỉ ghi vào lịch sử chat trên máy chủ (không gửi gói TCP tới máy trạm)."""
        if client_socket not in self.clients or not (text or "").strip():
            return False
        data = self.clients[client_socket]
        data.setdefault("chat_history", []).append(
            {"from": history_from, "text": text}
        )
        if bump_unread:
            data["chat_unread"] = data.get("chat_unread", 0) + 1
        if self.on_client_update:
            self.on_client_update()
        return True

    def send_chat_to_client(
        self, client_socket, text: str, history_from: str = "server"
    ) -> bool:
        if client_socket not in self.clients or not text:
            return False
        raw = encode_chat(text)
        ok = self._client_sendall(client_socket, f"CHAT:{raw}\n".encode("utf-8"))
        if not ok:
            if client_socket in self.clients:
                self._forget_client(client_socket)
            return False
        self.clients[client_socket].setdefault("chat_history", []).append(
            {"from": history_from, "text": text}
        )
        return True

    def get_chat_history_lines(self, client_socket):
        if client_socket not in self.clients:
            return []
        hist = self.clients[client_socket].get("chat_history", [])
        lines = []
        for h in hist:
            f = h.get("from")
            if f == "client":
                who = "Máy trạm"
            elif f == "order":
                who = "Đơn hàng"
            elif f == "ai":
                who = "Trợ lý AI"
            else:
                who = "Bạn"
            lines.append((who, h.get("text", "")))
        return lines

    def get_total_chat_unread(self) -> int:
        return sum(d.get("chat_unread", 0) for d in self.clients.values())

    def clear_chat_unread(self, client_socket):
        if client_socket in self.clients:
            self.clients[client_socket]["chat_unread"] = 0

    def list_chat_unread_machines(self):
        """[(pc_id 1-based, unread_count), ...]"""
        out = []
        for i, (sock, data) in enumerate(self.clients.items()):
            u = data.get("chat_unread", 0)
            if u > 0:
                out.append((i + 1, u, sock))
        return out

    def get_client_socket_by_pc_index(self, pc_index_zero_based: int):
        keys = list(self.clients.keys())
        if 0 <= pc_index_zero_based < len(keys):
            return keys[pc_index_zero_based]
        return None

    def get_clients_info(self):
        info = []
        for i, (sock, data) in enumerate(self.clients.items()):
            username = data.get("user")
            user_type = data.get("user_type")
            if username and user_type is None:
                uinfo = self.user_model.get_user(username)
                if uinfo:
                    user_type = uinfo.get("type")
            info.append({
                'id': i + 1,
                'status': data['status'],
                'usage': data['usage'],
                'last_seen': time.time() - data['last_seen'],
                'ip': data.get('ip', ''),
                'user': username,
                'user_type': user_type,
            })
        return info