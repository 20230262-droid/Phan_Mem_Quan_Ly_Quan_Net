import base64
import io
import json
import os
import subprocess
import sys
import threading
import time

from Ket_noi.Client.connection import Connection

from mvc.client_persistent_config import load_server_ip, save_server_ip


class ClientController:
    """Tính giờ chỉ khi server gửi UNLOCK; LOCK tạm dừng; SHUTDOWN/ngắt kết nối kết thúc phiên và thanh toán."""

    def __init__(self, view):
        self.view = view
        self.connection = None
        self.chat_history = []
        self.chat_unread = 0
        self.accumulated_seconds = 0
        self.segment_start = None
        self.usage_timer_running = False
        self.usage_timer = None
        self.logged_in = False
        self.logged_in_user_type = None

    def get_total_usage_seconds(self):
        t = self.accumulated_seconds
        if self.segment_start is not None:
            t += int(time.time() - self.segment_start)
        return t

    def _finalize_segment(self):
        if self.segment_start is not None:
            self.accumulated_seconds += int(time.time() - self.segment_start)
            self.segment_start = None

    def _finalize_all_billing(self):
        self._finalize_segment()
        total = self.accumulated_seconds
        self.accumulated_seconds = 0
        self.stop_usage_timer()
        return total

    def _begin_billing_segment(self):
        if self.segment_start is None:
            self.segment_start = time.time()
            self.start_usage_timer()

    def connect_to_server(self):
        ip = self.view.txt_server_ip.text().strip()
        if not ip:
            self.view.show_message("Lỗi", "Vui lòng nhập IP server hợp lệ")
            return

        if self.connection and self.connection.is_connected:
            return

        self._attempt_connect(ip, from_saved=False)

    def try_startup_autoconnect(self):
        ip = (load_server_ip() or "").strip()
        if not ip:
            return
        if self.connection and self.connection.is_connected:
            return
        self._attempt_connect(ip, from_saved=True)

    def _attempt_connect(self, ip: str, from_saved: bool):
        sig = self.view.signals
        self.connection = Connection(ip)
        self.connection.on_message_received = self.on_message_received
        self.connection.on_disconnected = self.on_disconnected

        if self.connection.connect():
            save_server_ip(ip)
            sig.server_ip_locked.emit(True)
            sig.set_connect_text.emit("Đã kết nối máy chủ")
            sig.set_connect_enabled.emit(False)
            self.accumulated_seconds = 0
            self.segment_start = None
            self.stop_usage_timer()
            self.chat_history = []
            self.chat_unread = 0
            self.logged_in = False
            self.logged_in_user_type = None
            self.view.update_status("Đã kết nối — chờ mở khóa máy")
            self.view.update_usage(0)
            self.view.enable_chat_buttons(True)
            sig.login_state_changed.emit()
            self.view.refresh_chat_badge_client()
            self.connection.send_status("WAITING")
        else:
            self.view.update_status("Kết nối thất bại")
            self.connection = None
            sig.server_ip_locked.emit(False)
            sig.set_connect_text.emit("Kết nối")
            sig.set_connect_enabled.emit(True)
            if from_saved:
                sig.show_message.emit(
                    "Kết nối thất bại",
                    "Không kết nối được máy chủ đã lưu. Kiểm tra máy chủ hoặc sửa IP rồi bấm Kết nối.",
                )

    def on_message_received(self, message):
        sig = self.view.signals
        if message.startswith("RATE:"):
            try:
                r = max(0, int(float(message[5:])))
                sig.hourly_rate_changed.emit(r)
            except ValueError:
                pass
            return
        if message.startswith("CHAT:"):
            from mvc.ui.chat_codec import decode_chat

            t = decode_chat(message[5:])
            if t:
                self.chat_history.append({"from": "server", "text": t})
                if not self.view.is_client_chat_visible():
                    self.chat_unread += 1
                sig.chat_notify.emit()
                sig.chat_server_message.emit(t)
            return
        if message == "LOCK":
            self._finalize_segment()
            self.stop_usage_timer()
            self.view.signals.update_usage.emit(self.accumulated_seconds)
            if self.connection:
                self.connection.send_usage_time(self.accumulated_seconds)
                self.connection.send_status("LOCKED")
            sig.show_message.emit("Đã khóa", "Đã tạm dừng tính giờ.")
        elif message == "UNLOCK":
            self._begin_billing_segment()
            self.connection.send_status("AVAILABLE")
            sig.show_message.emit("Đã mở khóa", "Đã bắt đầu tính giờ sử dụng.")
        elif message == "SHUTDOWN":
            total = self._finalize_all_billing()
            if self.connection:
                self.connection.send_usage_time(total)
            if total > 0:
                sig.show_checkout.emit(total)
            else:
                sig.show_message.emit("Kết phiên", "Chưa có thời gian tính phí.")
            self.view.signals.update_usage.emit(0)
            if self.connection:
                self.connection.send_usage_time(0)
                self.connection.send_status("WAITING")
            self.view.update_status("Đã kết nối — chờ mở khóa máy")
        elif message == "SCREENSHOT_REQUEST":
            threading.Thread(target=self._capture_and_send_screenshot, daemon=True).start()
        elif message.startswith("KILL_PROCESS:"):
            exe = message[len("KILL_PROCESS:") :].strip()
            threading.Thread(target=self._kill_process_remote, args=(exe,), daemon=True).start()
        elif message.startswith("LAUNCH_APP|"):
            target = message[len("LAUNCH_APP|") :].strip()
            threading.Thread(target=self._launch_app_remote, args=(target,), daemon=True).start()
        elif message.startswith("LOGIN_SUCCESS:"):
            user_type = message[14:]
            self.logged_in = True
            self.logged_in_user_type = user_type
            sig.login_state_changed.emit()
            sig.update_user_info.emit(f"Đã đăng nhập - Loại: {user_type}")
            sig.show_message.emit("Thành công", f"Đăng nhập thành công. Loại: {user_type}")
        elif message == "LOGIN_FAILED":
            self.logged_in = False
            self.logged_in_user_type = None
            sig.login_state_changed.emit()
            sig.show_message.emit("Lỗi", "Đăng nhập thất bại")
        elif message.startswith("TOPUP_SUCCESS"):
            sig.show_message.emit("Thành công", "Nạp tiền thành công")
        elif message.startswith("TOPUP_FAILED:"):
            msg = message[13:]
            sig.show_message.emit("Lỗi", f"Nạp tiền thất bại: {msg}")
        elif message.startswith("MENU_JSON:"):
            _, raw = message.split(":", 1)
            try:
                prods = json.loads(raw)
            except json.JSONDecodeError:
                prods = []
            if not isinstance(prods, list):
                prods = []
            sig.order_menu_ready.emit(prods)
        elif message.startswith("MENU_FAIL:"):
            _, msg = message.split(":", 1)
            sig.show_message.emit("Đặt hàng", (msg or "Không tải được thực đơn").strip())
        elif message.startswith("BALANCE:"):
            raw = message[8:].strip()
            try:
                bal = float(raw)
            except ValueError:
                return
            t = self.logged_in_user_type or "?"
            sig.update_user_info.emit(
                f"Đã đăng nhập - Loại: {t} - Số dư: {bal:,.0f} đ"
            )
        elif message == "ORDER_PENDING":
            sig.order_result.emit(
                True,
                "Đã gửi đơn tới quầy. Chờ quầy xác nhận — số dư chưa trừ.",
            )
        elif message == "ORDER_CONFIRMED":
            sig.order_result.emit(
                True,
                "Quầy đã xác nhận đơn (đã trừ số dư).",
            )
        elif message.startswith("ORDER_CANCELLED:"):
            _, msg = message.split(":", 1)
            sig.order_result.emit(False, (msg or "Đơn đã hủy").strip())
        elif message.startswith("ORDER_FAIL:"):
            err = message[11:].strip()
            sig.order_result.emit(False, err or "Không gửi được đơn")

    def request_product_menu(self):
        if not self.connection or not self.connection.is_connected:
            self.view.show_message("Lỗi", "Chưa kết nối máy chủ")
            return
        if not self.logged_in:
            self.view.show_message(
                "Đặt hàng", "Vui lòng đăng nhập tài khoản trước khi đặt món."
            )
            return
        self.connection.send_message("GET_MENU")

    def submit_order_items(self, items: list):
        if not self.connection or not self.connection.is_connected:
            self.view.show_message("Lỗi", "Chưa kết nối máy chủ")
            return
        if not self.logged_in:
            self.view.show_message(
                "Đặt hàng", "Vui lòng đăng nhập tài khoản trước khi đặt món."
            )
            return
        payload = json.dumps({"items": items}, ensure_ascii=False, separators=(",", ":"))
        self.connection.send_message(f"ORDER_SUBMIT:{payload}")

    def login(self):
        if not self.connection or not self.connection.is_connected:
            self.view.show_message("Lỗi", "Chưa kết nối máy chủ")
            return
        username = self.view.txt_username.text().strip()
        password = self.view.txt_password.text()
        if username and password:
            self.connection.send_message(f"LOGIN:{username}:{password}")

    def get_chat_display_lines(self):
        lines = []
        for h in self.chat_history:
            who = "Máy chủ" if h["from"] == "server" else "Bạn"
            lines.append((who, h["text"]))
        return lines

    def send_chat_message(self, text: str) -> bool:
        if not self.connection or not self.connection.is_connected or not text:
            return False
        self.chat_history.append({"from": "me", "text": text})
        self.connection.send_chat_text(text)
        return True

    def clear_chat_unread(self):
        self.chat_unread = 0
        self.view.signals.chat_notify.emit()

    def top_up(self):
        if not self.connection or not self.connection.is_connected:
            self.view.show_message("Lỗi", "Chưa kết nối máy chủ")
            return
        username = self.view.txt_username.text().strip()
        amount = self.view.txt_amount.text()
        if username and amount:
            try:
                amt = float(amount)
                self.connection.send_message(f"TOPUP:{username}:{amt}")
            except ValueError:
                self.view.show_message("Lỗi", "Số tiền không hợp lệ")

    def on_disconnected(self):
        self.logged_in = False
        self.logged_in_user_type = None
        sig = self.view.signals
        total = self._finalize_all_billing()
        if total > 0:
            sig.show_checkout.emit(total)
        sig.server_ip_locked.emit(False)
        sig.update_status.emit("Đã ngắt kết nối")
        sig.set_connect_text.emit("Kết nối")
        sig.set_connect_enabled.emit(True)
        self.connection = None
        self.chat_history = []
        self.chat_unread = 0
        self.view.enable_chat_buttons(False)
        sig.login_state_changed.emit()
        self.view.refresh_chat_badge_client()
        self.view.close_client_chat_dialog()
        sig.update_user_info.emit("Chưa đăng nhập")
        sig.update_usage.emit(0)

    def start_usage_timer(self):
        if not self.usage_timer_running:
            self.usage_timer_running = True
            self.send_usage_time()

    def stop_usage_timer(self):
        self.usage_timer_running = False
        if self.usage_timer and self.usage_timer.is_alive():
            self.usage_timer.cancel()
            self.usage_timer = None

    def send_usage_time(self):
        if self.connection and self.connection.is_connected:
            usage_seconds = self.get_total_usage_seconds()
            self.view.signals.update_usage.emit(usage_seconds)
            self.connection.send_usage_time(usage_seconds)
        if self.usage_timer_running:
            self.usage_timer = threading.Timer(1.0, self.send_usage_time)
            self.usage_timer.daemon = True
            self.usage_timer.start()

    def _capture_and_send_screenshot(self):
        conn = self.connection
        if not conn or not conn.is_connected:
            return

        def send_line(text: str) -> bool:
            c = self.connection
            if not c or not c.is_connected:
                return False
            c.send_message(text)
            return True

        try:
            from PIL import ImageGrab, Image
        except ImportError:
            send_line("SCREENSHOT_ERROR:Thiếu thư viện Pillow. Cài: pip install Pillow")
            return

        try:
            img = ImageGrab.grab(all_screens=True)
            w, h = img.size
            max_w = 1280
            if w > max_w:
                ratio = max_w / float(w)
                img = img.resize(
                    (max(1, int(w * ratio)), max(1, int(h * ratio))),
                    Image.Resampling.LANCZOS,
                )
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=55, optimize=True)
            raw = buf.getvalue()
            b64 = base64.b64encode(raw).decode("ascii")
            chunk_size = 900
            parts = [b64[i : i + chunk_size] for i in range(0, len(b64), chunk_size)]
            if not parts:
                send_line("SCREENSHOT_ERROR:Ảnh rỗng")
                return
            if not send_line(f"SCREENSHOT_START:{len(parts)}"):
                return
            for i, chunk in enumerate(parts):
                if not send_line(f"SCREENSHOT_PART:{i}:{chunk}"):
                    return
            send_line("SCREENSHOT_END")
        except Exception as e:
            send_line(f"SCREENSHOT_ERROR:{str(e)[:200]}")

    def _kill_process_remote(self, exe: str):
        conn = self.connection
        if not conn or not conn.is_connected:
            return
        if not exe:
            conn.send_message("KILL_RESULT:FAIL:Thiếu tên file .exe")
            return
        exe = exe.strip().strip('"')
        if not exe.lower().endswith(".exe"):
            exe = exe + ".exe"
        creationflags = 0
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            if sys.platform == "win32":
                r = subprocess.run(
                    ["taskkill", "/IM", exe, "/F"],
                    capture_output=True,
                    text=True,
                    timeout=45,
                    creationflags=creationflags,
                )
            else:
                r = subprocess.run(
                    ["pkill", "-f", exe],
                    capture_output=True,
                    text=True,
                    timeout=45,
                )
            ok = r.returncode == 0
            out = (r.stdout or "").strip()
            err = (r.stderr or "").strip()
            detail = out or err or ("OK" if ok else "Không tắt được process")
            line = "KILL_RESULT:OK" if ok else f"KILL_RESULT:FAIL:{detail[:400]}"
        except Exception as e:
            line = f"KILL_RESULT:FAIL:{str(e)[:400]}"
        if self.connection and self.connection.is_connected:
            self.connection.send_message(line)

    def _launch_app_remote(self, target: str):
        conn = self.connection
        if not conn or not conn.is_connected:
            return
        cmd = (target or "").strip().strip('"')
        if not cmd or "\n" in cmd or "\r" in cmd:
            conn.send_message("LAUNCH_RESULT:FAIL:Thiếu đường dẫn hoặc ký tự không hợp lệ")
            return
        try:
            if sys.platform == "win32":
                if "|" in cmd:
                    conn.send_message("LAUNCH_RESULT:FAIL:Không dùng ký tự | trong đường dẫn")
                    return
                if not any(sep in cmd for sep in ("\\", "/")):
                    if not cmd.lower().endswith(".exe"):
                        cmd = cmd + ".exe"
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
                if hasattr(subprocess, "DETACHED_PROCESS"):
                    creationflags |= subprocess.DETACHED_PROCESS
                cwd = None
                if os.path.isfile(cmd):
                    d = os.path.dirname(os.path.abspath(cmd))
                    if d and os.path.isdir(d):
                        cwd = d
                subprocess.Popen(
                    [cmd],
                    cwd=cwd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=False,
                    creationflags=creationflags,
                )
            else:
                subprocess.Popen(
                    ["/bin/sh", "-c", cmd],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            line = "LAUNCH_RESULT:OK"
        except Exception as e:
            line = f"LAUNCH_RESULT:FAIL:{str(e)[:400]}"
        if self.connection and self.connection.is_connected:
            self.connection.send_message(line)
