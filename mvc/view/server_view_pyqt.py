import sys
from PyQt6.QtWidgets import (
    QMainWindow,
    QApplication,
    QMessageBox,
    QGridLayout,
    QPushButton,
    QWidget,
    QLabel,
    QSpacerItem,
    QHBoxLayout,
    QVBoxLayout,
    QDialog,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QScrollArea,
    QAbstractItemView,
    QComboBox,
    QStyle,
    QGraphicsOpacityEffect,
    QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize, QObject, QSettings, QByteArray, QEvent, QEasingCurve, QPropertyAnimation
from PyQt6.QtGui import QColor, QFont, QImage, QPixmap
from mvc.ui.server_ui import Ui_MainWindow
from mvc.ui.chat_dialog import ChatDialog
from mvc.ui.history_dialog import HistoryDialog
from functools import partial
import time

class UpdateSignal(QObject):
    update_clients = pyqtSignal(list)
    chat_incoming = pyqtSignal(int, str)
    screenshot_ready = pyqtSignal(int, QByteArray)
    admin_feedback = pyqtSignal(str, str)
    order_from_client = pyqtSignal(int, str)

class ServerView(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self._ui_settings = QSettings("QuanLyQuanNet", "ServerMay")
        self._theme_name = str(self._ui_settings.value("ui_theme", "dark")).lower()
        if self._theme_name not in ("dark", "light"):
            self._theme_name = "dark"
        self._card_anims = {}

        self.menuBar().hide()
        row_chuc_nang = QWidget()
        lay_cn = QHBoxLayout(row_chuc_nang)
        lay_cn.setContentsMargins(4, 4, 4, 2)
        lay_cn.setSpacing(8)
        lbl_cn = QLabel("Chức năng:")
        _f_cn = QFont()
        _f_cn.setBold(True)
        lbl_cn.setFont(_f_cn)
        lay_cn.addWidget(lbl_cn)
        btn_ql_nd = QPushButton("Quản lý người dùng")
        btn_ql_nd.setMinimumHeight(32)
        btn_ql_nd.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        btn_ql_nd.clicked.connect(self._open_user_management_dialog)
        lay_cn.addWidget(btn_ql_nd)
        btn_order_menu = QPushButton("Danh mục sản phẩm")
        btn_order_menu.setMinimumHeight(32)
        btn_order_menu.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView))
        btn_order_menu.clicked.connect(self._open_order_menu_manage)
        lay_cn.addWidget(btn_order_menu)
        btn_pending_orders = QPushButton("Đơn khách oder")
        btn_pending_orders.setMinimumHeight(32)
        btn_pending_orders.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogListView))
        btn_pending_orders.clicked.connect(self._open_pending_orders_dialog)
        lay_cn.addWidget(btn_pending_orders)
        btn_pc_history = QPushButton("Lịch sử đã lưu theo PC")
        btn_pc_history.setMinimumHeight(32)
        btn_pc_history.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        btn_pc_history.clicked.connect(self._open_persisted_pc_history_dialog)
        lay_cn.addWidget(btn_pc_history)
        btn_revenue_stats = QPushButton("Thống kê doanh thu")
        btn_revenue_stats.setMinimumHeight(32)
        btn_revenue_stats.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon))
        btn_revenue_stats.clicked.connect(self._open_revenue_stats_dialog)
        lay_cn.addWidget(btn_revenue_stats)
        btn_ai_analysis = QPushButton("🤖 Phân tích AI")
        btn_ai_analysis.setMinimumHeight(32)
        btn_ai_analysis.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        btn_ai_analysis.clicked.connect(self._open_ai_analysis_dialog)
        lay_cn.addWidget(btn_ai_analysis)
        lay_cn.addWidget(QLabel("Giao diện:"))
        self.cbo_theme = QComboBox()
        self.cbo_theme.addItem("Dark", "dark")
        self.cbo_theme.addItem("Light", "light")
        self.cbo_theme.setCurrentIndex(0 if self._theme_name == "dark" else 1)
        self.cbo_theme.currentIndexChanged.connect(self._on_theme_changed)
        lay_cn.addWidget(self.cbo_theme)
        lay_cn.addStretch()
        self.ui.verticalLayout.insertWidget(0, row_chuc_nang)

        saved_price = self._ui_settings.value("price_per_hour", 15000)
        try:
            self.ui.spin_price_per_hour.setValue(int(saved_price))
        except (TypeError, ValueError):
            self.ui.spin_price_per_hour.setValue(15000)
        self.ui.spin_price_per_hour.valueChanged.connect(self._on_server_price_changed)

        self.selected_client_index = None
        self.client_cards = []
        self.detail_window = None
        
        # Signal for thread-safe UI updates
        self.update_signal = UpdateSignal()
        self.update_signal.update_clients.connect(
            self.update_clients_grid,
            Qt.ConnectionType.QueuedConnection,
        )
        self.update_signal.chat_incoming.connect(
            self._on_chat_incoming,
            Qt.ConnectionType.QueuedConnection,
        )
        self.update_signal.screenshot_ready.connect(
            self._on_screenshot_ready,
            Qt.ConnectionType.QueuedConnection,
        )
        self.update_signal.admin_feedback.connect(
            self._on_admin_feedback,
            Qt.ConnectionType.QueuedConnection,
        )
        self.update_signal.order_from_client.connect(
            self._on_order_from_client,
            Qt.ConnectionType.QueuedConnection,
        )

        self._chat_dialogs = {}
        self._auto_reply = None
        self.ui.lbl_chat_badge.setStyleSheet(
            "QLabel { background: #c62828; color: white; border-radius: 10px; "
            "padding: 2px 8px; font-weight: bold; min-width: 1.2em; }"
        )
        self.ui.lbl_chat_badge.hide()
        self.ui.btn_chat.setEnabled(False)
        self.ui.btn_chat.clicked.connect(self._open_chat_selected_machine)
        self.ui.btn_chat_notify.clicked.connect(self._open_chat_notifications)
        self.btn_chat_history = QPushButton("Lịch sử trò chuyện")
        self.btn_chat_history.setMinimumSize(0, 36)
        self.btn_chat_history.setEnabled(False)
        self.btn_chat_history.clicked.connect(self._open_chat_history_selected_machine)
        self.ui.verticalLayout_3.insertWidget(
            self.ui.verticalLayout_3.indexOf(self.ui.btn_chat_notify) + 1,
            self.btn_chat_history,
        )
        self.btn_order_history = QPushButton("Lịch sử order")
        self.btn_order_history.setMinimumSize(0, 36)
        self.btn_order_history.setEnabled(False)
        self.btn_order_history.clicked.connect(self._open_order_history_selected_machine)
        self.ui.verticalLayout_3.insertWidget(
            self.ui.verticalLayout_3.indexOf(self.btn_chat_history) + 1,
            self.btn_order_history,
        )

        # Connect signals chỉ nếu controller không None
        if controller:
            self._connect_signals()

        self.ui.btn_disconnect_client.setEnabled(False)
        self.ui.btn_lock.setEnabled(False)
        self.ui.btn_unlock.setEnabled(False)
        self.ui.btn_shutdown.setEnabled(False)

        idx_lock = self.ui.verticalLayout_3.indexOf(self.ui.btn_lock)
        self.ui.lbl_remote_section = QLabel("Giám sát từ xa")
        _bf = QFont()
        _bf.setBold(True)
        self.ui.lbl_remote_section.setFont(_bf)
        self.ui.verticalLayout_3.insertWidget(idx_lock, self.ui.lbl_remote_section)

        self.ui.btn_screenshot = QPushButton("Chụp màn hình")
        self.ui.btn_screenshot.setMinimumSize(120, 36)
        self.ui.btn_screenshot.setEnabled(False)
        self.ui.verticalLayout_3.insertWidget(idx_lock + 1, self.ui.btn_screenshot)

        self.ui.edt_kill_exe = QLineEdit()
        self.ui.edt_kill_exe.setPlaceholderText("Tên .exe, ví dụ: notepad.exe")
        self.ui.verticalLayout_3.insertWidget(idx_lock + 2, self.ui.edt_kill_exe)

        self.ui.btn_kill_process = QPushButton("Tắt ứng dụng")
        self.ui.btn_kill_process.setMinimumSize(120, 36)
        self.ui.btn_kill_process.setEnabled(False)
        self.ui.verticalLayout_3.insertWidget(idx_lock + 3, self.ui.btn_kill_process)

        self.ui.edt_launch_path = QLineEdit()
        self.ui.edt_launch_path.setPlaceholderText(
            "Mở app: notepad.exe hoặc đường dẫn đầy đủ .exe"
        )
        self.ui.verticalLayout_3.insertWidget(idx_lock + 4, self.ui.edt_launch_path)

        self.ui.btn_launch_app = QPushButton("Mở ứng dụng")
        self.ui.btn_launch_app.setMinimumSize(120, 36)
        self.ui.btn_launch_app.setEnabled(False)
        self.ui.verticalLayout_3.insertWidget(idx_lock + 5, self.ui.btn_launch_app)
        self._make_detail_panel_scrollable()
        self._apply_modern_theme(self._theme_name)

    def _apply_modern_theme(self, theme_name: str = "dark"):
        self.setMinimumSize(1260, 780)
        self.ui.lbl_title.setText("Net Cafe Control Center")
        if theme_name == "light":
            self.ui.lbl_title.setStyleSheet(
                "font-size: 30px; font-weight: 700; color: #0f172a; letter-spacing: 0.5px;"
            )
            self.ui.lbl_status.setStyleSheet(
                "font-size: 13px; color: #1e3a8a; background: #dbeafe; "
                "border: 1px solid #93c5fd; border-radius: 10px; padding: 8px 12px;"
            )
            base_style = (
                "QWidget { background: #f1f5f9; color: #0f172a; font-size: 12px; } "
                "QFrame { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 12px; } "
                "QLabel { background: transparent; } "
                "QPushButton { border-radius: 10px; padding: 8px 12px; border: 1px solid #cbd5e1; "
                "background: #e2e8f0; color: #0f172a; font-weight: 600; } "
                "QPushButton:hover { background: #cbd5e1; } "
                "QPushButton:disabled { color: #94a3b8; background: #f1f5f9; border-color: #e2e8f0; } "
                "QLineEdit, QSpinBox { background: #ffffff; border: 1px solid #cbd5e1; "
                "border-radius: 10px; padding: 6px 8px; } "
                "QLineEdit:focus, QSpinBox:focus { border: 1px solid #2563eb; } "
                "QScrollArea { border: 1px solid #cbd5e1; border-radius: 10px; }"
            )
        else:
            self.ui.lbl_title.setStyleSheet(
                "font-size: 30px; font-weight: 700; color: #f8fafc; letter-spacing: 0.5px;"
            )
            self.ui.lbl_status.setStyleSheet(
                "font-size: 13px; color: #bfdbfe; background: #1e3a8a; "
                "border: 1px solid #1d4ed8; border-radius: 10px; padding: 8px 12px;"
            )
            base_style = (
                "QWidget { background: #020617; color: #e2e8f0; font-size: 12px; } "
                "QFrame { background: #0b1220; border: 1px solid #1e293b; border-radius: 12px; } "
                "QLabel { background: transparent; } "
                "QPushButton { border-radius: 10px; padding: 8px 12px; border: 1px solid #334155; "
                "background: #1e293b; color: #e2e8f0; font-weight: 600; } "
                "QPushButton:hover { background: #334155; } "
                "QPushButton:disabled { color: #64748b; background: #0f172a; border-color: #1e293b; } "
                "QLineEdit, QSpinBox { background: #0f172a; border: 1px solid #334155; "
                "border-radius: 10px; padding: 6px 8px; } "
                "QLineEdit:focus, QSpinBox:focus { border: 1px solid #3b82f6; } "
                "QScrollArea { border: 1px solid #334155; border-radius: 10px; }"
            )
        self.ui.centralwidget.setStyleSheet(base_style)

        # Action hierarchy.
        self.ui.btn_start.setStyleSheet(
            "QPushButton { background: #2563eb; border: 1px solid #1d4ed8; color: #f8fafc; "
            "font-weight: 700; } QPushButton:hover { background: #1d4ed8; }"
        )
        self.ui.btn_refresh.setStyleSheet(
            "QPushButton { background: #0f766e; border: 1px solid #0d9488; color: #ecfeff; "
            "font-weight: 700; } QPushButton:hover { background: #0d9488; }"
        )
        self.ui.btn_add_client.setStyleSheet(
            "QPushButton { background: #7c3aed; border: 1px solid #6d28d9; color: #f5f3ff; "
            "font-weight: 700; } QPushButton:hover { background: #6d28d9; }"
        )
        
        # ===== STYLE NÚT XÓA MÁY =====
        if hasattr(self.ui, "btn_delete_client"):
            self.ui.btn_delete_client.setStyleSheet(
                "QPushButton { background: #dc2626; border: 1px solid #b91c1c; color: #fef2f2; "
                "font-weight: 700; } QPushButton:hover { background: #b91c1c; }"
            )
        
        self.ui.btn_lock.setStyleSheet(
            "QPushButton { background: #b45309; border: 1px solid #92400e; color: #fffbeb; "
            "font-weight: 700; } QPushButton:hover { background: #92400e; }"
        )
        self.ui.btn_unlock.setStyleSheet(
            "QPushButton { background: #15803d; border: 1px solid #166534; color: #f0fdf4; "
            "font-weight: 700; } QPushButton:hover { background: #166534; }"
        )
        self.ui.btn_shutdown.setStyleSheet(
            "QPushButton { background: #b91c1c; border: 1px solid #991b1b; color: #fef2f2; "
            "font-weight: 700; } QPushButton:hover { background: #991b1b; }"
        )
        self._apply_button_icons()

    def _on_theme_changed(self):
        theme_name = str(self.cbo_theme.currentData() or "dark")
        self._theme_name = theme_name
        self._ui_settings.setValue("ui_theme", theme_name)
        self._apply_modern_theme(theme_name)
        self.highlight_selected_card(self.selected_client_index if self.selected_client_index is not None else -1)

    def _apply_button_icons(self):
        s = self.style()
        self.ui.btn_chat.setIcon(s.standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation))
        self.ui.btn_chat_notify.setIcon(s.standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning))
        self.btn_chat_history.setIcon(s.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self.btn_order_history.setIcon(s.standardIcon(QStyle.StandardPixmap.SP_FileDialogListView))
        self.ui.btn_refresh.setIcon(s.standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.ui.btn_add_client.setIcon(s.standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        
        # ===== THÊM NÚT XÓA MÁY =====
        # Tạo nút xóa máy nếu chưa tồn tại
        if not hasattr(self.ui, "btn_delete_client"):
            self.ui.btn_delete_client = QPushButton("🗑️ Xóa máy")
            self.ui.btn_delete_client.setMinimumHeight(36)
            self.ui.btn_delete_client.setCursor(Qt.CursorShape.PointingHandCursor)
            self.ui.btn_delete_client.setIcon(s.standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
            
            # Thêm nút vào cùng layout với btn_add_client
            # Tìm parent layout của btn_add_client
            parent = self.ui.btn_add_client.parent()
            if parent and hasattr(parent, "layout"):
                layout = parent.layout()
                if layout:
                    # Tìm vị trí của btn_add_client trong layout
                    index = layout.indexOf(self.ui.btn_add_client)
                    if index >= 0:
                        # Chèn nút xóa ngay sau nút thêm
                        layout.insertWidget(index + 1, self.ui.btn_delete_client)
        
        self.ui.btn_lock.setIcon(s.standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton))
        self.ui.btn_unlock.setIcon(s.standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        self.ui.btn_shutdown.setIcon(s.standardIcon(QStyle.StandardPixmap.SP_TitleBarCloseButton))

    def _make_detail_panel_scrollable(self):
        """Bọc panel chi tiết vào scroll để tránh chồng lấn khi nhiều nút."""
        old_layout = self.ui.verticalLayout_3
        old_layout.setSpacing(8)
        old_layout.setContentsMargins(8, 8, 8, 8)

        items = []
        while old_layout.count():
            items.append(old_layout.takeAt(0))

        content = QWidget(self.ui.frame_detail)
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(8)
        content_layout.setContentsMargins(4, 4, 4, 4)

        for it in items:
            w = it.widget()
            l = it.layout()
            s = it.spacerItem()
            if w is not None:
                content_layout.addWidget(w)
            elif l is not None:
                content_layout.addLayout(l)
            elif s is not None:
                content_layout.addItem(s)

        scroll = QScrollArea(self.ui.frame_detail)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        old_layout.addWidget(scroll)

    def _on_server_price_changed(self, _value=None):
        self._ui_settings.setValue("price_per_hour", self.ui.spin_price_per_hour.value())
        if self.controller:
            self.controller.broadcast_hourly_rate_to_clients()

    def _install_card_hover_animation(self, card):
        eff = QGraphicsOpacityEffect(card)
        eff.setOpacity(0.92)
        card.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", card)
        anim.setDuration(160)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._card_anims[card] = (eff, anim)
        card.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj in self._card_anims:
            eff, anim = self._card_anims[obj]
            if event.type() == QEvent.Type.Enter:
                anim.stop()
                anim.setStartValue(eff.opacity())
                anim.setEndValue(1.0)
                anim.start()
            elif event.type() == QEvent.Type.Leave:
                anim.stop()
                anim.setStartValue(eff.opacity())
                anim.setEndValue(0.92)
                anim.start()
            elif event.type() == QEvent.Type.MouseButtonDblClick:
                client = getattr(obj, "_client_snapshot", None)
                if isinstance(client, dict):
                    self._show_order_notice_for_client(client)
                return True
        return super().eventFilter(obj, event)

    def _open_user_management_dialog(self):
        if self.controller:
            self.controller.open_user_management_dialog()

    def _open_order_menu_manage(self):
        if self.controller:
            self.controller.open_order_menu_manage()

    def _open_pending_orders_dialog(self):
        if self.controller:
            self.controller.open_pending_orders_dialog()

    def _open_revenue_stats_dialog(self):
        if self.controller:
            self.controller.open_revenue_stats_dialog()

    def _open_ai_analysis_dialog(self):
        """Mở dialog phân tích AI."""
        if self.controller:
            self.controller.open_ai_analysis_dialog()

    def _on_order_from_client(self, pc_index: int, notice: str):
        """Đơn chỉ lưu trên máy chủ (luồng chat với PC đó); cập nhật badge + cửa sổ chat nếu đang mở."""
        self._refresh_chat_badge()
        if not self.controller or not notice:
            return
        sock = self.controller.server.get_client_socket_by_pc_index(pc_index - 1)
        if sock and sock in self._chat_dialogs:
            self._chat_dialogs[sock].append_line("Đơn hàng", notice)

    def _connect_signals(self):
        """Kết nối tất cả signals với controller"""
        self.ui.btn_start.clicked.connect(self.controller.start_server)
        self.ui.btn_refresh.clicked.connect(self.controller.update_clients_list)
        self.ui.btn_add_client.clicked.connect(
            self.controller.launch_extra_client_machine
        )
        # Kết nối nút xóa máy
        if hasattr(self.ui, "btn_delete_client"):
            self.ui.btn_delete_client.clicked.connect(
                self.controller.delete_pc_machine
            )
        self.ui.btn_disconnect_client.clicked.connect(
            self.controller.disconnect_selected_client
        )
        self.ui.btn_lock.clicked.connect(self.controller.lock_selected)
        self.ui.btn_unlock.clicked.connect(self.controller.unlock_selected)
        self.ui.btn_shutdown.clicked.connect(self.controller.shutdown_selected)
        if hasattr(self.ui, "btn_screenshot"):
            self.ui.btn_screenshot.clicked.connect(
                self.controller.request_screenshot_selected
            )
        if hasattr(self.ui, "btn_kill_process"):
            self.ui.btn_kill_process.clicked.connect(
                self.controller.kill_process_on_selected
            )
        if hasattr(self.ui, "btn_launch_app"):
            self.ui.btn_launch_app.clicked.connect(
                self.controller.launch_app_on_selected
            )

    def _update_pc_buttons_state(self):
        """Cập nhật trạng thái nút thêm/xóa máy dựa trên giới hạn."""
        if not self.controller or not self.controller.server:
            return
        
        can_add = self.controller.server.can_add_pc()
        
        # Disable nút thêm nếu đạt giới hạn
        self.ui.btn_add_client.setEnabled(can_add)
        
        # Cập nhật text nút với thông tin số máy
        current = self.controller.server.max_pc_slots
        max_pc = self.controller.server.MAX_PC_SLOTS
        self.ui.btn_add_client.setText(f"➕ Thêm PC ({current}/{max_pc})")
        
        # Enable nút xóa nếu có thể xóa
        if hasattr(self.ui, "btn_delete_client"):
            can_delete = current > 1
            self.ui.btn_delete_client.setEnabled(can_delete)
            self.ui.btn_delete_client.setText(f"🗑️ Xóa máy ({current}/{max_pc})")

    def update_status(self, status):
        self.ui.lbl_status.setText(f"Máy chủ: {status}")

    def set_start_button_text(self, text, command):
        self.ui.btn_start.setText(text)
        self.ui.btn_start.clicked.disconnect()
        self.ui.btn_start.clicked.connect(command)

    def update_clients_grid(self, clients):
        try:
            # Cập nhật trạng thái nút thêm/xóa máy dựa trên giới hạn
            self._update_pc_buttons_state()
            
            order_counts = (
                self.controller.server.get_pending_order_counts_by_pc()
                if self.controller
                else {}
            )
            # Tạo QWidget mới cho scrollArea để tránh vấn đề layout cũ
            scroll_area = self.ui.scrollArea_clients
            
            # Tạo QWidget mới
            new_widget = QWidget()
            layout = QVBoxLayout()
            layout.setSpacing(10)
            layout.setContentsMargins(5, 5, 5, 5)
            new_widget.setLayout(layout)
            
            # Set QWidget mới cho scrollArea
            scroll_area.setWidget(new_widget)
            
            self.client_cards = []
            self._card_anims = {}
            
            if not clients:
                self.show_client_detail(None)
                if self.controller:
                    self.controller.sync_detail_after_grid([])
                return
            
            # Tạo layout theo hàng (rows)
            max_columns = 6
            current_row_layout = None
            
            for index, client in enumerate(clients):
                column = index % max_columns
                
                # Tạo hàng mới nếu cần
                if column == 0:
                    current_row_layout = QHBoxLayout()
                    current_row_layout.setSpacing(10)
                    layout.addLayout(current_row_layout)
                
                status_color = self._status_color(client["status"])
                is_vip = (client.get("user_type") or "").lower() == "vip"
                pending_orders = int(order_counts.get(int(client["id"]), 0) or 0)

                card = QPushButton()
                card.setFixedSize(100, 100)
                card.setCursor(Qt.CursorShape.PointingHandCursor)
                lay = QVBoxLayout(card)
                lay.setContentsMargins(6, 6, 6, 6)
                lay.setSpacing(0)

                top_row = QHBoxLayout()
                top_row.setSpacing(0)
                if pending_orders > 0:
                    order_lbl = QLabel(str(pending_orders))
                    order_lbl.setStyleSheet(
                        "font-size: 10px; font-weight: bold; color: white; background: #ef6c00; "
                        "padding: 2px 6px; border-radius: 8px; border: none;"
                    )
                    order_lbl.setToolTip("Số lần máy này gọi món chưa xử lý")
                    order_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                    top_row.addWidget(order_lbl, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                else:
                    top_row.addStretch()
                top_row.addStretch()
                if is_vip:
                    vip_lbl = QLabel("VIP")
                    vip_lbl.setStyleSheet(
                        "font-size: 9px; font-weight: bold; color: #1b5e20; background: #e8f5e9; "
                        "padding: 2px 6px; border-radius: 4px; border: none;"
                    )
                    vip_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                    top_row.addWidget(vip_lbl, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
                lay.addLayout(top_row)

                # Hiển thị hostname nếu có, nếu không thì hiển thị PC số
                hostname = client.get('hostname', '').strip()
                if hostname:
                    pc_display = f"🖥️\n{hostname}"
                else:
                    pc_display = f"🖥️\nPC {client['id']}"
                mid = QLabel(pc_display)
                mid.setAlignment(Qt.AlignmentFlag.AlignCenter)
                mid.setStyleSheet(
                    "color: white; font-weight: bold; font-size: 11px; background: transparent; border: none; word-wrap: break-word;"
                )
                mid.setWordWrap(True)
                mid.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                lay.addStretch()
                lay.addWidget(mid)
                lay.addStretch()

                card._bg_color = status_color
                card._client_snapshot = dict(client)
                card.setStyleSheet(self._pc_card_stylesheet(status_color, selected=False))
                card.clicked.connect(lambda checked, idx=index: self.controller.select_client(idx))
                self._install_card_hover_animation(card)
                
                current_row_layout.addWidget(card)
                self.client_cards.append(card)
                
                # Thêm stretch để các cột co giãn đều
                current_row_layout.addStretch()
            
            # Thêm spacer ở cuối để không duỗi ra
            layout.addStretch()

            if self.controller:
                self.controller.sync_detail_after_grid(clients)

        except Exception as e:
            print(f"Error updating grid: {e}")
            import traceback
            traceback.print_exc()

    def show_client_detail(self, client):
        if client is None:
            self.selected_client_index = None
            self.ui.btn_chat.setEnabled(False)
            self.btn_chat_history.setEnabled(False)
            self.btn_order_history.setEnabled(False)
            self.ui.lbl_detail_title.setText("Chi tiết máy")
            self.ui.lbl_selected_id.setText("Máy: -")
            self.ui.lbl_selected_status.setText("Trạng thái: -")
            self.ui.lbl_selected_usage.setText("Thời gian: -")
            self.ui.lbl_selected_seen.setText("Lần cuối: -")
            self.ui.lbl_selected_ip.setText("IP: -")
            if hasattr(self.ui, "lbl_selected_hostname"):
                self.ui.lbl_selected_hostname.setText("Tên máy: -")
            self.ui.btn_disconnect_client.setEnabled(False)
            self.ui.btn_lock.setEnabled(False)
            self.ui.btn_unlock.setEnabled(False)
            self.ui.btn_shutdown.setEnabled(False)
            if hasattr(self.ui, "btn_screenshot"):
                self.ui.btn_screenshot.setEnabled(False)
            if hasattr(self.ui, "btn_kill_process"):
                self.ui.btn_kill_process.setEnabled(False)
            if hasattr(self.ui, "btn_launch_app"):
                self.ui.btn_launch_app.setEnabled(False)
            if hasattr(self.ui, "edt_launch_path"):
                self.ui.edt_launch_path.setEnabled(False)
            if self.detail_window is not None:
                self.detail_window.close()
                self.detail_window = None
            return

        status_text = self._status_display(client['status'])
        self.selected_client_index = client['id'] - 1
        user = client.get("user") or "—"
        vip_note = " · VIP" if (client.get("user_type") or "").lower() == "vip" else ""
        hostname = client.get('hostname', '').strip() or f"PC {client['id']}"
        hostname_display = hostname if hostname.startswith("PC ") else hostname
        self.ui.lbl_detail_title.setText(f"Chi tiết máy {hostname_display} (TK: {user}{vip_note})")
        self.ui.lbl_selected_id.setText(f"Máy: {client['id']}")
        self.ui.lbl_selected_status.setText(f"Trạng thái: {status_text}")
        self.ui.lbl_selected_usage.setText(f"Thời gian: {self._format_duration(client['usage'])}")
        self.ui.lbl_selected_seen.setText(f"Lần cuối: {client['last_seen']:.1f} giây trước")
        ip = client.get("ip") or "—"
        self.ui.lbl_selected_ip.setText(f"IP: {ip}")
        if hasattr(self.ui, "lbl_selected_hostname"):
            self.ui.lbl_selected_hostname.setText(f"Tên máy: {client.get('hostname', '—').strip() or '—'}")
        self.ui.btn_disconnect_client.setEnabled(True)
        self.ui.btn_lock.setEnabled(True)
        self.ui.btn_unlock.setEnabled(True)
        self.ui.btn_shutdown.setEnabled(True)
        self.ui.btn_chat.setEnabled(True)
        self.btn_chat_history.setEnabled(True)
        self.btn_order_history.setEnabled(True)
        if hasattr(self.ui, "btn_screenshot"):
            self.ui.btn_screenshot.setEnabled(True)
        if hasattr(self.ui, "btn_kill_process"):
            self.ui.btn_kill_process.setEnabled(True)
        if hasattr(self.ui, "btn_launch_app"):
            self.ui.btn_launch_app.setEnabled(True)
        if hasattr(self.ui, "edt_launch_path"):
            self.ui.edt_launch_path.setEnabled(True)

    def _on_screenshot_ready(self, pc_index: int, data: QByteArray):
        raw = bytes(data)
        img = QImage.fromData(raw, "JPEG")
        if img.isNull():
            QMessageBox.warning(self, "Chụp màn hình", "Không đọc được ảnh từ máy trạm.")
            return
        pm = QPixmap.fromImage(img)
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Màn hình — PC {pc_index + 1}")
        v = QVBoxLayout(dlg)
        scroll = QScrollArea()
        lbl = QLabel()
        lbl.setPixmap(pm)
        lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        scroll.setWidget(lbl)
        scroll.setWidgetResizable(True)
        v.addWidget(scroll)
        w = min(pm.width() + 48, 1280)
        h = min(pm.height() + 72, 900)
        dlg.resize(max(w, 400), max(h, 300))
        dlg.exec()

    def _on_admin_feedback(self, title: str, message: str):
        QMessageBox.information(self, title, message)

    def close_all_chat_dialogs(self):
        for d in list(self._chat_dialogs.values()):
            d.close()
        self._chat_dialogs.clear()

    def close_chat_for_socket(self, sock):
        d = self._chat_dialogs.pop(sock, None)
        if d:
            d.close()

    def _refresh_chat_badge(self):
        if not self.controller:
            return
        n = self.controller.server.get_total_chat_unread()
        if n > 0:
            self.ui.lbl_chat_badge.setText(str(n))
            self.ui.lbl_chat_badge.show()
        else:
            self.ui.lbl_chat_badge.setText("")
            self.ui.lbl_chat_badge.hide()

    def _on_chat_incoming(self, pc_index: int, text: str):
        self._refresh_chat_badge()
        sock = self.controller.server.get_client_socket_by_pc_index(pc_index)
        if sock and sock in self._chat_dialogs and text:
            self._chat_dialogs[sock].append_line("Máy trạm", text)

    def _open_chat_selected_machine(self):
        if not self.controller:
            return
        idx = self.controller.selected_client_index
        if idx is None:
            QMessageBox.information(
                self,
                "Chat",
                "Chọn một máy trên lưới (ô PC) trước khi mở chat.",
            )
            return
        self._open_chat_for_pc_index(idx)

    def _open_chat_history_selected_machine(self):
        if not self.controller:
            return
        idx = self.controller.selected_client_index
        if idx is None:
            QMessageBox.information(
                self,
                "Lịch sử trò chuyện",
                "Chọn một máy trên lưới (ô PC) trước khi xem lịch sử.",
            )
            return
        sock = self.controller.server.get_client_socket_by_pc_index(idx)
        dlg = HistoryDialog(
            f"Lịch sử trò chuyện — PC {idx + 1}",
            f"Toàn bộ lịch sử chat của PC {idx + 1}",
            self,
        )
        lines = self.controller.server.get_persisted_chat_history_lines(idx + 1)
        if not lines and sock is not None:
            lines = self.controller.server.get_chat_history_lines(sock)
        dlg.load_history_lines(lines)
        dlg.exec()

    def _open_order_history_selected_machine(self):
        if not self.controller:
            return
        idx = self.controller.selected_client_index
        if idx is None:
            QMessageBox.information(
                self,
                "Lịch sử order",
                "Chọn một máy trên lưới (ô PC) trước khi xem lịch sử.",
            )
            return
        sock = self.controller.server.get_client_socket_by_pc_index(idx)
        dlg = HistoryDialog(
            f"Lịch sử order — PC {idx + 1}",
            f"Toàn bộ order của PC {idx + 1}",
            self,
        )
        lines = self.controller.server.get_persisted_order_history_lines(idx + 1)
        if not lines and sock is not None:
            lines = self.controller.server.get_order_history_lines(sock)
        dlg.load_history_lines(lines)
        dlg.exec()

    def _open_persisted_pc_history_dialog(self):
        if not self.controller:
            return
        rows = self.controller.server.list_persisted_history_pc_indices()
        if not rows:
            QMessageBox.information(
                self,
                "Lịch sử đã lưu",
                "Chưa có lịch sử lưu trên máy chủ.",
            )
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Lịch sử đã lưu theo PC")
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("Chọn PC để mở lịch sử đã lưu (kể cả máy đã ngắt kết nối)."))
        lw = QListWidget()
        lw.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        def _reload_pc_list():
            lw.clear()
            for pc_id in self.controller.server.list_persisted_history_pc_indices():
                it = QListWidgetItem(f"PC {pc_id}")
                it.setData(Qt.ItemDataRole.UserRole, int(pc_id))
                lw.addItem(it)

        _reload_pc_list()
        v.addWidget(lw)

        def _selected_pc():
            item = lw.currentItem()
            if not item:
                return None
            return int(item.data(Qt.ItemDataRole.UserRole))

        def _open_chat():
            pc_id = _selected_pc()
            if pc_id is None:
                return
            hd = HistoryDialog(
                f"Lịch sử trò chuyện — PC {pc_id}",
                f"Dữ liệu lưu bền vững của PC {pc_id}",
                self,
            )
            hd.load_history_lines(
                self.controller.server.get_persisted_chat_history_lines(pc_id)
            )
            hd.exec()

        def _open_order():
            pc_id = _selected_pc()
            if pc_id is None:
                return
            hd = HistoryDialog(
                f"Lịch sử order — PC {pc_id}",
                f"Dữ liệu lưu bền vững của PC {pc_id}",
                self,
            )
            hd.load_history_lines(
                self.controller.server.get_persisted_order_history_lines(pc_id)
            )
            hd.exec()

        def _delete_pc_history():
            pc_id = _selected_pc()
            if pc_id is None:
                QMessageBox.information(
                    dlg, "Xóa lịch sử", "Chọn một PC trong danh sách trước."
                )
                return
            r = QMessageBox.question(
                dlg,
                "Xóa lịch sử theo PC",
                f"Bạn có chắc muốn xóa toàn bộ lịch sử đã lưu của PC {pc_id}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if r != QMessageBox.StandardButton.Yes:
                return
            deleted = self.controller.server.clear_persisted_history_for_pc(pc_id)
            QMessageBox.information(
                dlg,
                "Xóa lịch sử",
                f"Đã xóa {deleted} bản ghi của PC {pc_id}.",
            )
            _reload_pc_list()

        def _delete_all_history():
            r = QMessageBox.question(
                dlg,
                "Xóa toàn bộ lịch sử",
                "Bạn có chắc muốn xóa toàn bộ lịch sử đã lưu của tất cả PC?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if r != QMessageBox.StandardButton.Yes:
                return
            deleted = self.controller.server.clear_all_persisted_history()
            QMessageBox.information(
                dlg,
                "Xóa toàn bộ lịch sử",
                f"Đã xóa {deleted} bản ghi.",
            )
            _reload_pc_list()

        row_btn = QHBoxLayout()
        b1 = QPushButton("Xem chat")
        b1.clicked.connect(_open_chat)
        b2 = QPushButton("Xem order")
        b2.clicked.connect(_open_order)
        b_del_pc = QPushButton("Xóa lịch sử PC đã chọn")
        b_del_pc.clicked.connect(_delete_pc_history)
        b_del_all = QPushButton("Xóa toàn bộ lịch sử")
        b_del_all.clicked.connect(_delete_all_history)
        b3 = QPushButton("Đóng")
        b3.clicked.connect(dlg.accept)
        row_btn.addWidget(b1)
        row_btn.addWidget(b2)
        row_btn.addWidget(b_del_pc)
        row_btn.addWidget(b_del_all)
        row_btn.addStretch()
        row_btn.addWidget(b3)
        v.addLayout(row_btn)
        lw.itemDoubleClicked.connect(lambda _i: _open_chat())
        dlg.exec()

    def _open_chat_for_pc_index(self, pc_index_zero: int):
        sock = self.controller.server.get_client_socket_by_pc_index(pc_index_zero)
        if sock is None:
            QMessageBox.warning(self, "Chat", "Máy không còn kết nối.")
            return
        if sock in self._chat_dialogs:
            d = self._chat_dialogs[sock]
            d.raise_()
            d.activateWindow()
            self.controller.server.clear_chat_unread(sock)
            self._refresh_chat_badge()
            return
        dlg = ChatDialog(f"Chat — PC {pc_index_zero + 1}", f"PC {pc_index_zero + 1}", self)
        dlg.load_history_lines(self.controller.server.get_chat_history_lines(sock))
        dlg.send_requested.connect(
            lambda t, s=sock, d=dlg: self._server_send_chat(s, t, d)
        )
        dlg.finished.connect(partial(self._chat_dialog_closed, sock))
        self._chat_dialogs[sock] = dlg
        self.controller.server.clear_chat_unread(sock)
        self._refresh_chat_badge()
        dlg.show()

    def _server_send_chat(self, sock, text, dlg):
        if self.controller.server.send_chat_to_client(sock, text):
            dlg.append_line("Bạn", text)
            if self._auto_reply is not None:
                self._auto_reply.on_staff_sent(sock)
        else:
            QMessageBox.warning(self, "Chat", "Không gửi được tin (mất kết nối).")

    def on_ai_chat_sent(self, sock, text: str):
        """Cập nhật cửa sổ chat đang mở khi Trợ lý AI gửi tin."""
        dlg = self._chat_dialogs.get(sock)
        if dlg:
            dlg.append_line("Trợ lý AI", text)

    def _chat_dialog_closed(self, sock, _result=None):
        self._chat_dialogs.pop(sock, None)

    def _open_chat_notifications(self):
        if not self.controller or not self.controller.server.clients:
            QMessageBox.information(
                self,
                "Thông báo",
                "Không có máy trạm kết nối hoặc chưa bật server.",
            )
            return
        rows = self.controller.server.list_chat_unread_machines()
        if not rows:
            QMessageBox.information(
                self,
                "Thông báo",
                "Không có tin nhắn mới từ máy trạm.",
            )
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Thông báo — tin chưa đọc")
        v = QVBoxLayout(dlg)
        total = sum(r[1] for r in rows)
        v.addWidget(
            QLabel(
                f"Tổng {total} tin chưa đọc từ {len(rows)} máy.\n"
                "Chọn một dòng rồi bấm «Mở chat» hoặc double-click."
            )
        )
        lw = QListWidget()
        for pc_id, cnt, _sock in rows:
            it = QListWidgetItem(f"PC {pc_id} — {cnt} tin nhắn mới")
            it.setData(Qt.ItemDataRole.UserRole, pc_id - 1)
            lw.addItem(it)
        v.addWidget(lw)

        def open_selected():
            item = lw.currentItem()
            if not item:
                return
            idx = int(item.data(Qt.ItemDataRole.UserRole))
            dlg.accept()
            self._open_chat_for_pc_index(idx)

        btn = QPushButton("Mở chat với máy đã chọn")
        btn.clicked.connect(open_selected)
        v.addWidget(btn)
        lw.itemDoubleClicked.connect(lambda _i: open_selected())
        dlg.exec()

    def highlight_selected_card(self, index):
        for idx, card in enumerate(self.client_cards):
            bg = getattr(card, "_bg_color", "#444444")
            card.setStyleSheet(self._pc_card_stylesheet(bg, selected=(idx == index)))

    def _pc_card_stylesheet(self, bg_hex: str, selected: bool) -> str:
        border = "#4d7cff" if selected else bg_hex
        return (
            f"QPushButton {{ background-color: {bg_hex}; border-radius: 8px; "
            f"border: 2px solid {border}; font-weight: bold; color: white; }}"
            f"QPushButton:hover {{ border-color: #93c5fd; }}"
        )

    def _show_order_notice_for_client(self, client: dict):
        if not self.controller:
            return
        pc_id = int(client.get("id", 0) or 0)
        if pc_id <= 0:
            return
        if not client.get("connected"):
            QMessageBox.information(self, "Order", f"PC {pc_id} chưa kết nối.")
            return
        username = (client.get("user") or "").strip()
        if not username:
            QMessageBox.information(self, "Order", f"PC {pc_id} chưa đăng nhập tài khoản.")
            return
        orders = self.controller.server.get_pending_orders_for_pc(pc_id)
        if not orders:
            QMessageBox.information(self, "Order", f"PC {pc_id} không có order.")
            return
        QMessageBox.information(
            self,
            "Order",
            f"PC {pc_id} có {len(orders)} order mới. Đang mở «Đơn khách oder».",
        )
        self._open_pending_orders_dialog()

    def open_machine_detail(self, client):
        if self.detail_window is not None:
            self.detail_window.activateWindow()
            self.detail_window.raise_()
            return

        self.detail_window = QMainWindow()
        self.detail_window.setWindowTitle(f"Chi tiết máy {client['id']}")
        self.detail_window.setGeometry(100, 100, 360, 320)
        self.detail_window.setMinimumSize(360, 320)
        
        central = QWidget()
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(16, 16, 16, 16)
        self.detail_window.setCentralWidget(central)

        self.detail_window.show()
        self.update_detail_window(client)

    def update_detail_window(self, client):
        pass

    def _status_color(self, status):
        # Xanh lá: đã mở khóa / đang tính giờ (AVAILABLE). Đỏ: các trạng thái còn lại.
        if status == "AVAILABLE":
            return "#2e7d32"
        if status == "STARTING":
            return "#1d4ed8"
        if status == "OFFLINE":
            return "#475569"
        return "#c62828"

    def _status_display(self, status):
        display_map = {
            'WAITING': 'Chờ mở khóa',
            'AVAILABLE': 'Đang tính giờ',
            'LOCKED': 'Tạm khóa / dừng giờ',
            'CONNECTED': 'Đang kết nối',
            'ENDED': 'Đã kết phiên',
            'STARTING': 'Đang mở form client',
            'OFFLINE': 'Chưa có client',
        }
        return display_map.get(status, status)

    def _format_duration(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def show_message(self, title, message):
        QMessageBox.information(self, title, message)
