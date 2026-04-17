import subprocess
import sys
from pathlib import Path

from Ket_noi.Sever.server_connection import Server
from mvc.models.user_model import UserModel


class ServerController:
    def __init__(self, view):
        self.view = view
        self.user_model = UserModel()
        self.server = Server(user_model=self.user_model)
        self.server.on_client_update = self.schedule_update_clients_list
        self.server.on_chat_from_client = self._on_chat_from_client
        self.server.on_remote_screenshot = self._on_remote_screenshot
        self.server.on_remote_admin_text = self._on_remote_admin_text
        self.server.on_order_from_client = self._on_order_from_client
        self.server.hourly_rate_fn = self._hourly_rate_from_ui
        self.selected_client_index = None
        self._setup_ai_auto_reply()

    def _setup_ai_auto_reply(self):
        try:
            from PyQt6.QtCore import Qt as QtCore
            from AI_chat.auto_reply import AutoReplyCoordinator
        except Exception:
            return
        if not self.view:
            return
        ar = AutoReplyCoordinator(
            self.server,
            on_ai_sent=lambda s, t: self.view.on_ai_chat_sent(s, t),
            parent=self.view,
        )
        self.view._auto_reply = ar
        self.view.update_signal.chat_incoming.connect(
            ar.on_client_message_pc_index,
            QtCore.ConnectionType.QueuedConnection,
        )

    def _hourly_rate_from_ui(self):
        try:
            return max(0, int(self.view.ui.spin_price_per_hour.value()))
        except Exception:
            return 15000

    def broadcast_hourly_rate_to_clients(self):
        if self.server.running and self.server.clients:
            self.server.broadcast_hourly_rate()

    def launch_extra_client_machine(self):
        """Chạy thêm một process giao diện client (mỗi lần bấm = một máy trạm mới)."""
        root = Path(__file__).resolve().parent.parent.parent
        main_py = root / "Ket_noi" / "Client" / "main.py"
        if not main_py.is_file():
            self.view.show_message(
                "Lỗi",
                f"Không tìm thấy file client:\n{main_py}",
            )
            return
        try:
            creationflags = 0
            if sys.platform == "win32":
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen(
                [sys.executable, str(main_py)],
                cwd=str(root),
                creationflags=creationflags,
            )
        except Exception as e:
            self.view.show_message("Lỗi", f"Không chạy thêm client:\n{e}")

    def _on_chat_from_client(self, client_socket, text):
        try:
            idx = list(self.server.clients.keys()).index(client_socket)
        except ValueError:
            return
        if self.view:
            self.view.update_signal.chat_incoming.emit(idx, text or "")

    def _on_remote_screenshot(self, client_socket, jpeg_bytes):
        try:
            idx = list(self.server.clients.keys()).index(client_socket)
        except ValueError:
            return
        if self.view:
            from PyQt6.QtCore import QByteArray

            self.view.update_signal.screenshot_ready.emit(idx, QByteArray(jpeg_bytes))

    def _on_remote_admin_text(self, client_socket, title, message):
        try:
            idx = list(self.server.clients.keys()).index(client_socket)
        except ValueError:
            idx = -1
        label = f"PC {idx + 1}" if idx >= 0 else "Máy trạm"
        if self.view:
            self.view.update_signal.admin_feedback.emit(f"{title} — {label}", message or "")

    def schedule_update_clients_list(self):
        # For PyQt6, call directly instead of using 'after'
        self.update_clients_list()

    def start_server(self):
        if not self.server.running:
            self.server.start()
            self.view.update_status("Đang chạy")
            self.view.set_start_button_text("Tắt server", self.stop_server)
        else:
            self.stop_server()

    def stop_server(self):
        self.view.close_all_chat_dialogs()
        self.server.stop()
        self.view.update_status("Đã dừng")
        self.view.set_start_button_text("Bật server", self.start_server)
        self.selected_client_index = None
        self.update_clients_list()

    def update_clients_list(self):
        clients = self.server.get_clients_info()
        # pyqtSignal.emit từ thread socket vẫn an toàn — Qt xếp hàng chạy slot trên luồng GUI
        if self.view:
            self.view.update_signal.update_clients.emit(clients)

    def sync_detail_after_grid(self, clients):
        """Gọi từ update_clients_grid (luồng GUI) sau khi vẽ lưới máy."""
        if not clients:
            self.selected_client_index = None
            return
        if self.selected_client_index is None:
            return
        if self.selected_client_index < len(clients):
            self.view.show_client_detail(clients[self.selected_client_index])
            self.view.highlight_selected_card(self.selected_client_index)
        else:
            self.selected_client_index = None
            self.view.show_client_detail(None)

    def select_client(self, client_index):
        self.selected_client_index = client_index
        clients = self.server.get_clients_info()
        if 0 <= client_index < len(clients):
            self.view.show_client_detail(clients[client_index])
            self.view.highlight_selected_card(client_index)

    def _get_selected_client_socket(self):
        if self.selected_client_index is None:
            return None
        clients = list(self.server.clients.keys())
        if 0 <= self.selected_client_index < len(clients):
            return clients[self.selected_client_index]
        return None

    def lock_selected(self):
        client = self._get_selected_client_socket()
        if client:
            self.server.send_command(client, "LOCK")
            self.view.show_message("Thông báo", "Đã gửi lệnh khóa đến máy được chọn")

    def unlock_selected(self):
        client = self._get_selected_client_socket()
        if client:
            self.server.send_command(client, "UNLOCK")
            self.view.show_message("Thông báo", "Đã gửi lệnh mở khóa đến máy được chọn")

    def shutdown_selected(self):
        client = self._get_selected_client_socket()
        if client:
            self.server.send_command(client, "SHUTDOWN")
            self.view.show_message("Thông báo", "Đã gửi lệnh tắt máy đến máy được chọn")

    def disconnect_selected_client(self):
        """Ngắt socket máy trạm đang chọn — phía client mở lại nút kết nối và ô IP."""
        client = self._get_selected_client_socket()
        if not client:
            self.view.show_message("Thông báo", "Chọn một máy trên lưới trước.")
            return
        self.view.close_chat_for_socket(client)
        self.server.disconnect_client(client)
        self.selected_client_index = None
        self.update_clients_list()
        self.view.show_client_detail(None)
        self.view.show_message(
            "Thông báo",
            "Đã ngắt kết nối máy trạm đó. Trên máy trạm có thể kết nối lại và nhập IP (nếu cần).",
        )

    def request_screenshot_selected(self):
        client = self._get_selected_client_socket()
        if not client:
            self.view.show_message("Thông báo", "Chọn một máy trên lưới trước.")
            return
        self.server.send_command(client, "SCREENSHOT_REQUEST")

    def kill_process_on_selected(self):
        client = self._get_selected_client_socket()
        if not client:
            self.view.show_message("Thông báo", "Chọn một máy trên lưới trước.")
            return
        exe = ""
        if hasattr(self.view.ui, "edt_kill_exe"):
            exe = self.view.ui.edt_kill_exe.text().strip()
        if not exe:
            self.view.show_message("Thông báo", "Nhập tên file .exe (ví dụ notepad.exe).")
            return
        safe = exe.replace("\n", "").replace("\r", "")
        self.server.send_command(client, f"KILL_PROCESS:{safe}")

    def launch_app_on_selected(self):
        client = self._get_selected_client_socket()
        if not client:
            self.view.show_message("Thông báo", "Chọn một máy trên lưới trước.")
            return
        path = ""
        if hasattr(self.view.ui, "edt_launch_path"):
            path = self.view.ui.edt_launch_path.text().strip()
        if not path:
            self.view.show_message("Thông báo", "Nhập đường dẫn hoặc tên ứng dụng (ví dụ notepad.exe).")
            return
        safe = path.replace("\n", "").replace("\r", "")
        if "|" in safe:
            self.view.show_message("Lỗi", "Không được dùng ký tự | trong lệnh mở.")
            return
        self.server.send_command(client, f"LAUNCH_APP|{safe}")

    def register_user(self, username, password, user_type="normal"):
        success, message = self.user_model.register(username, password, user_type)
        return success, message

    def login_user(self, username, password):
        success, user = self.user_model.login(username, password)
        return success, user

    def top_up_user(self, username, amount):
        success, message = self.user_model.top_up(username, amount)
        return success, message

    def assign_user_to_machine(self, username, machine_id):
        """Gán tài khoản qua đăng nhập từ máy trạm (LOGIN); không có lệnh riêng trên socket."""
        return False, "Dùng đăng nhập trên máy trạm để gán tài khoản cho máy đó."

    def get_user_history(self, username):
        user = self.user_model.get_user(username)
        if user:
            return user['history']
        return []

    def open_order_menu_manage(self):
        from mvc.ui.order_menu_manage_dialog import OrderMenuManageDialog

        dlg = OrderMenuManageDialog(self.view, self.server.menu_model)
        dlg.exec()

    def open_pending_orders_dialog(self):
        from mvc.ui.pending_orders_dialog import PendingOrdersDialog

        dlg = PendingOrdersDialog(
            self.view, self.server, on_changed=self.update_clients_list
        )
        dlg.exec()

    def _on_order_from_client(self, client_socket, pc_index, notice: str):
        if self.view:
            self.view.update_signal.order_from_client.emit(pc_index, notice or "")

    def open_user_management_dialog(self):
        from mvc.ui.user_management_dialog import UserManagementDialog

        dlg = UserManagementDialog(self.user_model, self.view)
        dlg.exec()
        self.after_user_admin_changed()

    def after_user_admin_changed(self):
        """Đồng bộ loại tài khoản trên máy đang kết nối và làm mới lưới PC."""
        for d in self.server.clients.values():
            u = d.get("user")
            if u:
                info = self.user_model.get_user(u)
                d["user_type"] = info.get("type") if info else None
            else:
                d["user_type"] = None
        if self.view:
            self.update_clients_list()
