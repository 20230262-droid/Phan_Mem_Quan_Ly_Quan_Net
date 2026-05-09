from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTextBrowser,
    QLineEdit,
    QPushButton,
    QLabel,
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QIcon, QPixmap


class ChatDialog(QDialog):
    """Hộp thoại chat: lịch sử + ô nhập + Gửi. Tin gửi đi do bên gọi append_line sau khi gửi thành công."""

    send_requested = pyqtSignal(str)

    def __init__(self, title: str, peer_label: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(500, 600)
        self.setMaximumSize(600, 800)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        # Apply modern styling
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f8fafc, stop:1 #e2e8f0);
                border: 1px solid #cbd5e1;
                border-radius: 15px;
            }
            QLabel {
                color: #334155;
                font-size: 14px;
                font-weight: 600;
            }
            QTextBrowser {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                padding: 10px;
                font-size: 13px;
                color: #1e293b;
            }
            QLineEdit {
                background: #ffffff;
                border: 2px solid #e2e8f0;
                border-radius: 20px;
                padding: 8px 15px;
                font-size: 13px;
                color: #1e293b;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
                background: #f8fafc;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3b82f6, stop:1 #2563eb);
                color: white;
                border: none;
                border-radius: 20px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
                min-width: 80px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2563eb, stop:1 #1d4ed8);
            }
            QPushButton:pressed {
                background: #1d4ed8;
            }
            QPushButton#closeBtn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ef4444, stop:1 #dc2626);
                min-width: 70px;
            }
            QPushButton#closeBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #dc2626, stop:1 #b91c1c);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header with icon
        header_layout = QHBoxLayout()
        chat_icon = QLabel()
        chat_icon.setPixmap(QPixmap())  # Could add a chat icon here
        chat_icon.setFixedSize(32, 32)
        header_layout.addWidget(chat_icon)

        self._hint = QLabel(f"💬 Trò chuyện với: {peer_label}")
        hint_font = QFont()
        hint_font.setPointSize(16)
        hint_font.setBold(True)
        self._hint.setFont(hint_font)
        header_layout.addWidget(self._hint)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Chat history area
        self._browser = QTextBrowser()
        self._browser.setReadOnly(True)
        self._browser.setPlaceholderText("Chưa có tin nhắn nào. Hãy bắt đầu cuộc trò chuyện!")
        self._browser.setFont(QFont("Segoe UI", 11))
        layout.addWidget(self._browser)

        # Input area
        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Nhập tin nhắn của bạn...")
        self._input.setFont(QFont("Segoe UI", 11))
        self._input.returnPressed.connect(self._on_send)
        input_layout.addWidget(self._input, stretch=1)

        self._btn_send = QPushButton("📤 Gửi")
        self._btn_send.setFont(QFont("Segoe UI", 11))
        self._btn_send.clicked.connect(self._on_send)
        input_layout.addWidget(self._btn_send)

        layout.addLayout(input_layout)

        # Close button
        self._btn_close = QPushButton("❌ Đóng")
        self._btn_close.setObjectName("closeBtn")
        self._btn_close.setFont(QFont("Segoe UI", 11))
        self._btn_close.clicked.connect(self.accept)
        layout.addWidget(self._btn_close, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_peer_label(self, text: str):
        self._hint.setText(f"💬 Trò chuyện với: {text}")

    def append_line(self, who: str, text: str):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Escape HTML
        who_safe = (
            who.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        safe = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br/>")
        )

        # Different styling for different senders
        if "AI" in who or "🤖" in who:
            # AI messages - blue theme
            html = f"""
            <div style="margin: 8px 0; padding: 10px 15px; background: #dbeafe;
                        border-left: 4px solid #3b82f6; border-radius: 8px;">
                <div style="font-weight: bold; color: #1e40af; font-size: 12px;">
                    🤖 {who_safe} <span style="color: #64748b;">{timestamp}</span>
                </div>
                <div style="color: #1e293b; margin-top: 5px; line-height: 1.4;">
                    {safe}
                </div>
            </div>
            """
        elif "Server" in who or "Nhân viên" in who:
            # Server/Admin messages - green theme
            html = f"""
            <div style="margin: 8px 0; padding: 10px 15px; background: #dcfce7;
                        border-left: 4px solid #10b981; border-radius: 8px;">
                <div style="font-weight: bold; color: #047857; font-size: 12px;">
                    👨‍💼 {who_safe} <span style="color: #64748b;">{timestamp}</span>
                </div>
                <div style="color: #1e293b; margin-top: 5px; line-height: 1.4;">
                    {safe}
                </div>
            </div>
            """
        else:
            # Client messages - gray theme
            html = f"""
            <div style="margin: 8px 0; padding: 10px 15px; background: #f1f5f9;
                        border-left: 4px solid #64748b; border-radius: 8px;">
                <div style="font-weight: bold; color: #374151; font-size: 12px;">
                    👤 {who_safe} <span style="color: #64748b;">{timestamp}</span>
                </div>
                <div style="color: #1e293b; margin-top: 5px; line-height: 1.4;">
                    {safe}
                </div>
            </div>
            """

        self._browser.append(html)
        # Auto scroll to bottom with smooth animation
        QTimer.singleShot(100, lambda: self._browser.verticalScrollBar().setValue(
            self._browser.verticalScrollBar().maximum()))

    def load_history_lines(self, lines: list[tuple[str, str]]):
        self._browser.clear()
        for who, text in lines:
            self.append_line(who, text)

    def _on_send(self):
        t = self._input.text().strip()
        if not t:
            return
        self.send_requested.emit(t)
        self._input.clear()
