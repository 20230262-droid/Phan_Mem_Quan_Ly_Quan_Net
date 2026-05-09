from PyQt6.QtWidgets import QMainWindow, QMessageBox, QComboBox, QLabel, QStyle
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QObject, QSettings
from mvc.ui.client_ui import Ui_MainWindow
from mvc.ui.chat_dialog import ChatDialog


class ClientViewSignals(QObject):
    """Cập nhật UI từ thread socket — emit từ thread khác, slot chạy trên luồng Qt chính."""

    show_message = pyqtSignal(str, str)
    show_checkout = pyqtSignal(int, float)
    hourly_rate_changed = pyqtSignal(int)
    chat_notify = pyqtSignal()
    chat_server_message = pyqtSignal(str)
    update_user_info = pyqtSignal(str)
    update_usage = pyqtSignal(int)
    update_status = pyqtSignal(str)
    set_connect_text = pyqtSignal(str)
    set_connect_enabled = pyqtSignal(bool)
    server_ip_locked = pyqtSignal(bool)
    order_menu_ready = pyqtSignal(list)
    order_result = pyqtSignal(bool, str)
    login_state_changed = pyqtSignal()


class ClientView(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.lbl_user_info.setWordWrap(True)
        self._ui_settings = QSettings("QuanLyQuanNet", "ClientMay")
        self._theme_name = str(self._ui_settings.value("ui_theme", "dark")).lower()
        if self._theme_name not in ("dark", "light"):
            self._theme_name = "dark"
        self._add_theme_switcher()
        self._apply_modern_theme(self._theme_name)

        self._hourly_rate_vnd = 15000
        self._client_chat_dialog = None
        self._pc_slot_id = None

        self.signals = ClientViewSignals()
        self.signals.show_message.connect(self.show_message)
        self.signals.show_checkout.connect(self._show_checkout_dialog)
        self.signals.hourly_rate_changed.connect(self._set_hourly_rate_vnd)
        self.signals.chat_notify.connect(self.refresh_chat_badge_client)
        self.signals.chat_server_message.connect(self._on_chat_server_message)
        self.signals.update_user_info.connect(self.ui.lbl_user_info.setText)
        self.signals.update_usage.connect(self.update_usage)
        self.signals.update_status.connect(self.update_status)
        self.signals.set_connect_text.connect(self.set_connect_button_text)
        self.signals.set_connect_enabled.connect(self.set_connect_button_enabled)
        self.signals.server_ip_locked.connect(self.set_server_ip_locked)
        self.signals.order_menu_ready.connect(self._open_order_dialog)
        self.signals.order_result.connect(self._on_order_result)
        self.signals.login_state_changed.connect(self._refresh_order_button)

        self.ui.lbl_chat_badge.setStyleSheet(
            "QLabel { background: #c62828; color: white; border-radius: 10px; "
            "padding: 2px 8px; font-weight: bold; min-width: 1.2em; }"
        )
        self.ui.lbl_chat_badge.hide()
        self.enable_chat_buttons(False)
        self._refresh_order_button()

        if controller:
            self._connect_signals()

        self.apply_saved_server_ip_field()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_usage_display)

    def _add_theme_switcher(self):
        lbl = QLabel("Giao diện:")
        cbo = QComboBox()
        cbo.addItem("Dark", "dark")
        cbo.addItem("Light", "light")
        cbo.setCurrentIndex(0 if self._theme_name == "dark" else 1)
        cbo.currentIndexChanged.connect(self._on_theme_changed)
        h = self.ui.groupBox_chat.layout()
        h.insertWidget(0, lbl)
        h.insertWidget(1, cbo)
        self._theme_label = lbl
        self._theme_combo = cbo

    def _apply_modern_theme(self, theme_name: str = "dark"):
        self.setMinimumSize(560, 760)
        self.ui.lbl_title.setText("Net Station Client")
        if theme_name == "light":
            self.ui.lbl_title.setStyleSheet(
                "font-size: 28px; font-weight: 700; color: #0f172a; letter-spacing: 0.4px;"
            )
            self.ui.lbl_status.setStyleSheet(
                "font-size: 13px; color: #334155; background: #e2e8f0; "
                "border: 1px solid #cbd5e1; border-radius: 10px; padding: 8px;"
            )
            self.ui.lbl_usage.setStyleSheet(
                "font-size: 13px; color: #0f766e; background: #ccfbf1; "
                "border: 1px solid #5eead4; border-radius: 10px; padding: 8px;"
            )
            base_style = (
                "QWidget { background: #f8fafc; color: #0f172a; font-size: 12px; } "
                "QLineEdit { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 10px; "
                "padding: 8px 10px; selection-background-color: #2563eb; } "
                "QLineEdit:focus { border: 1px solid #3b82f6; } "
                "QPushButton { border-radius: 10px; padding: 8px 12px; border: 1px solid #cbd5e1; "
                "background: #e2e8f0; color: #0f172a; font-weight: 600; } "
                "QPushButton:hover { background: #cbd5e1; } "
                "QPushButton:disabled { color: #94a3b8; background: #f1f5f9; border-color: #e2e8f0; }"
            )
        else:
            self.ui.lbl_title.setStyleSheet(
                "font-size: 28px; font-weight: 700; color: #f8fafc; letter-spacing: 0.4px;"
            )
            self.ui.lbl_status.setStyleSheet(
                "font-size: 13px; color: #cbd5e1; background: #1e293b; "
                "border: 1px solid #334155; border-radius: 10px; padding: 8px;"
            )
            self.ui.lbl_usage.setStyleSheet(
                "font-size: 13px; color: #bae6fd; background: #082f49; "
                "border: 1px solid #155e75; border-radius: 10px; padding: 8px;"
            )
            base_style = (
                "QWidget { background: #020617; color: #e2e8f0; font-size: 12px; } "
                "QLineEdit { background: #0b1220; border: 1px solid #334155; border-radius: 10px; "
                "padding: 8px 10px; selection-background-color: #2563eb; } "
                "QLineEdit:focus { border: 1px solid #3b82f6; } "
                "QPushButton { border-radius: 10px; padding: 8px 12px; border: 1px solid #334155; "
                "background: #1e293b; color: #e2e8f0; font-weight: 600; } "
                "QPushButton:hover { background: #334155; } "
                "QPushButton:disabled { color: #64748b; background: #0f172a; border-color: #1e293b; }"
            )
        self.ui.groupBox_chat.setTitle("Liên lạc quầy")
        self.ui.groupBox_order.setTitle("Đặt đồ ăn & thức uống")
        self.ui.groupBox_user.setTitle("Tài khoản khách hàng")
        self.ui.lbl_amount.setText("Số tiền nạp (chơi máy):")
        self.ui.btn_topup.setText("Nạp tiền chơi máy (VietQR)")
        self.ui.btn_topup.setToolTip(
            "Hiện mã VietQR + STK, sau đó xác nhận ghi có vào ví «tiền chơi máy»."
        )

        for gb in (self.ui.groupBox_chat, self.ui.groupBox_order, self.ui.groupBox_user):
            gb.setStyleSheet(
                "QGroupBox { color: #e2e8f0; font-size: 13px; font-weight: 600; "
                "border: 1px solid #334155; border-radius: 12px; margin-top: 12px; "
                "background-color: #0f172a; } "
                "QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }"
            )

        self.ui.centralwidget.setStyleSheet(base_style)

        # Button hierarchy for better UX.
        self.ui.btn_connect.setStyleSheet(
            "QPushButton { background: #2563eb; border: 1px solid #1d4ed8; color: #f8fafc; "
            "font-weight: 700; } QPushButton:hover { background: #1d4ed8; }"
        )
        self.ui.btn_order.setStyleSheet(
            "QPushButton { background: #0891b2; border: 1px solid #0e7490; color: #ecfeff; "
            "font-weight: 700; } QPushButton:hover { background: #0e7490; }"
        )
        self.ui.btn_login.setStyleSheet(
            "QPushButton { background: #16a34a; border: 1px solid #15803d; color: #f0fdf4; "
            "font-weight: 700; } QPushButton:hover { background: #15803d; }"
        )
        self.ui.btn_topup.setStyleSheet(
            "QPushButton { background: #7c3aed; border: 1px solid #6d28d9; color: #f5f3ff; "
            "font-weight: 700; } QPushButton:hover { background: #6d28d9; }"
        )
        self._apply_button_icons()

    def _on_theme_changed(self):
        theme_name = str(self._theme_combo.currentData() or "dark")
        self._theme_name = theme_name
        self._ui_settings.setValue("ui_theme", theme_name)
        self._apply_modern_theme(theme_name)

    def _apply_button_icons(self):
        s = self.style()
        self.ui.btn_connect.setIcon(s.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.ui.btn_login.setIcon(s.standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        self.ui.btn_topup.setIcon(s.standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
        self.ui.btn_chat.setIcon(s.standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation))
        self.ui.btn_chat_notify.setIcon(s.standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning))
        self.ui.btn_order.setIcon(s.standardIcon(QStyle.StandardPixmap.SP_DialogYesButton))

    def is_client_chat_visible(self):
        d = self._client_chat_dialog
        return d is not None and d.isVisible()

    def enable_chat_buttons(self, on: bool):
        self.ui.btn_chat.setEnabled(on)
        self.ui.btn_chat_notify.setEnabled(on)

    def _refresh_order_button(self):
        c = self.controller
        conn = bool(
            c and c.connection and c.connection.is_connected and getattr(c, "logged_in", False)
        )
        self.ui.btn_order.setEnabled(conn)

    def refresh_chat_badge_client(self):
        n = self.controller.chat_unread if self.controller else 0
        if n > 0:
            self.ui.lbl_chat_badge.setText(str(n))
            self.ui.lbl_chat_badge.show()
        else:
            self.ui.lbl_chat_badge.setText("")
            self.ui.lbl_chat_badge.hide()

    def _on_chat_server_message(self, text: str):
        d = self._client_chat_dialog
        if d and d.isVisible():
            d.append_line("Máy chủ", text)

    def close_client_chat_dialog(self):
        if self._client_chat_dialog:
            self._client_chat_dialog.close()
            self._client_chat_dialog = None

    def _open_client_chat(self):
        if not self.controller or not self.controller.connection:
            QMessageBox.information(self, "Chat", "Chưa kết nối máy chủ.")
            return
        if not self.controller.connection.is_connected:
            QMessageBox.information(self, "Chat", "Chưa kết nối máy chủ.")
            return
        if self._client_chat_dialog and self._client_chat_dialog.isVisible():
            self._client_chat_dialog.raise_()
            self._client_chat_dialog.activateWindow()
            self.controller.clear_chat_unread()
            self.refresh_chat_badge_client()
            return
        dlg = ChatDialog("Chat — máy chủ", "Máy chủ", self)
        dlg.load_history_lines(self.controller.get_chat_display_lines())
        dlg.send_requested.connect(lambda t, d=dlg: self._client_send_chat(t, d))
        dlg.finished.connect(self._on_client_chat_finished)
        self._client_chat_dialog = dlg
        self.controller.clear_chat_unread()
        self.refresh_chat_badge_client()
        dlg.show()

    def _on_client_chat_finished(self, _result=0):
        self._client_chat_dialog = None

    def _client_send_chat(self, text, dlg):
        if self.controller.send_chat_message(text):
            dlg.append_line("Bạn", text)
        else:
            QMessageBox.warning(self, "Chat", "Không gửi được tin nhắn.")

    def _request_order_menu(self):
        if not self.controller:
            return
        if not getattr(self.controller, "logged_in", False):
            QMessageBox.information(
                self,
                "Đặt hàng",
                "Vui lòng đăng nhập tài khoản trước khi đặt món.",
            )
            return
        self.controller.request_product_menu()

    def _open_order_dialog(self, products: list):
        from mvc.ui.order_client_dialog import OrderClientDialog

        if not products:
            QMessageBox.information(
                self,
                "Đặt hàng",
                "Quầy chưa có món nào (hoặc đã tắt hết). Liên hệ quầy.",
            )
            return
        dlg = OrderClientDialog(self, products, self.controller.submit_order_items)
        dlg.exec()

    def _on_order_result(self, ok: bool, message: str):
        if ok:
            QMessageBox.information(self, "Đặt hàng", message)
        else:
            QMessageBox.warning(self, "Đặt hàng", message)

    def _open_client_notifications(self):
        if not self.controller or not self.controller.connection:
            QMessageBox.information(self, "Thông báo", "Chưa kết nối máy chủ.")
            return
        if not self.controller.connection.is_connected:
            QMessageBox.information(self, "Thông báo", "Chưa kết nối máy chủ.")
            return
        n = self.controller.chat_unread
        if n == 0:
            QMessageBox.information(
                self,
                "Thông báo",
                "Không có tin nhắn mới từ máy chủ.",
            )
            return
        QMessageBox.information(
            self,
            "Thông báo",
            f"Bạn có {n} tin nhắn chưa xem từ máy chủ.\nBấm OK để mở cửa sổ chat.",
        )
        self.controller.clear_chat_unread()
        self.refresh_chat_badge_client()
        self._open_client_chat()

    def _set_hourly_rate_vnd(self, rate):
        self._hourly_rate_vnd = max(0, int(rate))

    def _connect_signals(self):
        self.ui.btn_connect.clicked.connect(self.controller.connect_to_server)
        self.ui.btn_login.clicked.connect(self.controller.login)
        self.ui.btn_topup.clicked.connect(self.controller.top_up)
        self.ui.btn_chat.clicked.connect(self._open_client_chat)
        self.ui.btn_chat_notify.clicked.connect(self._open_client_notifications)
        self.ui.btn_order.clicked.connect(self._request_order_menu)

    @property
    def txt_server_ip(self):
        return self.ui.txt_server_ip

    def apply_saved_server_ip_field(self):
        from mvc.client_persistent_config import load_server_ip

        ip = load_server_ip()
        if ip:
            self.ui.txt_server_ip.setText(ip)
            self.set_server_ip_locked(True)

    def set_server_ip_locked(self, locked: bool):
        le = self.ui.txt_server_ip
        le.setReadOnly(locked)
        le.setFocusPolicy(Qt.FocusPolicy.NoFocus if locked else Qt.FocusPolicy.StrongFocus)
        if locked:
            le.setToolTip(
                "IP đã lưu trên máy này. Chỉ sửa được sau khi máy chủ ngắt kết nối."
            )
        else:
            le.setToolTip("")

    @property
    def txt_username(self):
        return self.ui.txt_username

    @property
    def txt_password(self):
        return self.ui.txt_password

    @property
    def txt_amount(self):
        return self.ui.txt_amount

    def update_status(self, status):
        if self._pc_slot_id:
            self.ui.lbl_status.setText(f"Trạng thái (PC {self._pc_slot_id}): {status}")
        else:
            self.ui.lbl_status.setText(f"Trạng thái: {status}")

    def set_pc_slot(self, pc_slot_id: int):
        self._pc_slot_id = int(pc_slot_id)
        self.setWindowTitle(f"Net Station Client - PC {self._pc_slot_id}")
        current = self.ui.lbl_status.text().replace("Trạng thái: ", "")
        self.update_status(current)

    def update_usage(self, usage_seconds):
        self.ui.lbl_usage.setText(f"Thời gian sử dụng: {self._format_duration(usage_seconds)}")

    def update_user_info(self, info):
        self.ui.lbl_user_info.setText(info)

    def _format_duration(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def show_message(self, title, message):
        QMessageBox.information(self, title, message)

    def _show_checkout_dialog(self, total_seconds: int, food_tab_vnd: float = 0.0):
        from mvc.ui.checkout_dialog import CheckoutDialog

        uname = ""
        if self.controller and getattr(self.controller, "logged_in", False):
            uname = self.txt_username.text().strip()
        dlg = CheckoutDialog(
            self,
            total_seconds=int(total_seconds),
            hourly_rate_vnd=self._hourly_rate_vnd,
            food_tab_vnd=float(food_tab_vnd or 0),
            username_hint=uname,
        )
        dlg.exec()

    def set_connect_button_text(self, text):
        self.ui.btn_connect.setText(text)

    def set_connect_button_enabled(self, enabled: bool):
        self.ui.btn_connect.setEnabled(enabled)
        if enabled:
            self.ui.btn_connect.setToolTip("")
        else:
            self.ui.btn_connect.setToolTip(
                "Kết nối do máy chủ quản lý — không ngắt từ máy trạm."
            )

    def start_usage_timer(self):
        self.usage_timer_running = True
        self.timer.start(1000)

    def stop_usage_timer(self):
        self.usage_timer_running = False
        self.timer.stop()

    def update_usage_display(self):
        if self.controller and self.controller.usage_timer_running:
            current_usage = self.controller.get_total_usage_seconds()
            if current_usage is not None:
                self.update_usage(current_usage)
