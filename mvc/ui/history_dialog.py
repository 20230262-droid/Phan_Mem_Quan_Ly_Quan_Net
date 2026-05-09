from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QTextBrowser, QVBoxLayout


class HistoryDialog(QDialog):
    """Dialog chỉ đọc dùng để xem lịch sử chat/order."""

    def __init__(self, title: str, header: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(560, 420)

        layout = QVBoxLayout(self)
        self._header = QLabel(header)
        layout.addWidget(self._header)

        self._browser = QTextBrowser()
        self._browser.setReadOnly(True)
        self._browser.setPlaceholderText("Chưa có dữ liệu.")
        layout.addWidget(self._browser)

        self._btn_close = QPushButton("Đóng")
        self._btn_close.clicked.connect(self.accept)
        layout.addWidget(self._btn_close, alignment=Qt.AlignmentFlag.AlignRight)

    def load_history_lines(self, lines: list[tuple[str, str]]):
        self._browser.clear()
        for who, text in lines:
            who_safe = (
                str(who).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )
            safe = (
                str(text)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br/>")
            )
            self._browser.append(f"<b>{who_safe}</b>: {safe}")
        self._browser.verticalScrollBar().setValue(
            self._browser.verticalScrollBar().maximum()
        )
