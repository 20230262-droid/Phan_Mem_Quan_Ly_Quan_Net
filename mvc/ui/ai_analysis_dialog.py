"""
Dialog hiển thị báo cáo phân tích AI.
"""

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QLabel,
    QStyle,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont


class AIAnalysisDialog(QDialog):
    """Dialog hiển thị báo cáo phân tích AI."""

    def __init__(self, parent, analysis_fn):
        """
        Khởi tạo dialog.
        
        Args:
            parent: Widget cha
            analysis_fn: Hàm trả về báo cáo text từ AI module
        """
        super().__init__(parent)
        self.analysis_fn = analysis_fn
        self.setWindowTitle("📊 Phân tích AI - Quản lý Quán Net")
        self.setGeometry(100, 100, 900, 700)
        self.init_ui()
        self.load_analysis()

    def init_ui(self):
        """Khởi tạo giao diện."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Tiêu đề
        title = QLabel("📊 BÁO CÁO PHÂN TÍCH QUẢN LÝ QUÁN NET")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title.setFont(title_font)
        layout.addWidget(title)

        # Text edit hiển thị báo cáo
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setFont(QFont("Courier", 10))
        layout.addWidget(self.report_text)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        # Nút làm mới
        btn_refresh = QPushButton("🔄 Làm mới")
        btn_refresh.setMinimumHeight(36)
        btn_refresh.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        btn_refresh.clicked.connect(self.load_analysis)
        button_layout.addWidget(btn_refresh)

        # Nút copy
        btn_copy = QPushButton("📋 Copy")
        btn_copy.setMinimumHeight(36)
        btn_copy.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogYesButton))
        btn_copy.clicked.connect(self.copy_to_clipboard)
        button_layout.addWidget(btn_copy)

        # Spacer
        button_layout.addStretch()

        # Nút đóng
        btn_close = QPushButton("✕ Đóng")
        btn_close.setMinimumHeight(36)
        btn_close.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton))
        btn_close.clicked.connect(self.accept)
        button_layout.addWidget(btn_close)

        layout.addLayout(button_layout)

    def load_analysis(self):
        """Tải và hiển thị báo cáo phân tích."""
        try:
            # Gọi hàm phân tích từ controller/ai_module
            report = self.analysis_fn()
            self.report_text.setText(report)
        except Exception as e:
            error_message = f"❌ Lỗi khi phân tích dữ liệu:\n{str(e)}"
            self.report_text.setText(error_message)

    def copy_to_clipboard(self):
        """Sao chép báo cáo vào clipboard."""
        try:
            from PyQt6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText(self.report_text.toPlainText())
            
            # Hiển thị thông báo tạm thời
            old_text = self.report_text.toPlainText()
            self.report_text.setText("✓ Đã sao chép vào clipboard!")
            QTimer.singleShot(1500, lambda: self.report_text.setText(old_text))
        except Exception as e:
            print(f"Lỗi copy clipboard: {e}")
            self.report_text.setText(f"❌ Lỗi khi copy: {str(e)}")
