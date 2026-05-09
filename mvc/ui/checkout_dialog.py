"""Kết phiên: tách phí chơi máy và công nợ đồ ăn — mỗi loại có nút VietQR riêng."""

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QFrame,
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from config.vietqr_settings import is_vietqr_configured
from mvc.ui.vietqr_payment_dialog import VietQRPaymentDialog


class CheckoutDialog(QDialog):
    def __init__(
        self,
        parent,
        *,
        total_seconds: int,
        hourly_rate_vnd: int,
        food_tab_vnd: float,
        username_hint: str = "",
    ):
        super().__init__(parent)
        self.setWindowTitle("💳 Kết phiên — Thanh toán")
        self.setMinimumWidth(550)
        self.setMinimumHeight(400)
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
                font-size: 13px;
            }
            QLabel.title {
                font-size: 18px;
                font-weight: bold;
                color: #1e293b;
            }
            QLabel.amount {
                font-size: 16px;
                font-weight: bold;
                color: #059669;
            }
            QFrame {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3b82f6, stop:1 #2563eb);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 20px;
                font-size: 13px;
                font-weight: 600;
                min-width: 150px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2563eb, stop:1 #1d4ed8);
            }
            QPushButton:pressed {
                background: #1d4ed8;
            }
            QPushButton:disabled {
                background: #94a3b8;
                color: #e2e8f0;
            }
        """)

        price_per_hour = float(max(0, int(hourly_rate_vnd)))
        hours = total_seconds / 3600.0
        play_amount = hours * price_per_hour
        food_amt = max(0.0, float(food_tab_vnd))

        v = QVBoxLayout(self)
        v.setContentsMargins(25, 25, 25, 25)
        v.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()
        icon_label = QLabel("💳")
        icon_label.setFont(QFont("Segoe UI", 28))
        header_layout.addWidget(icon_label)

        title_label = QLabel("Kết phiên — Thanh toán")
        title_label.setObjectName("title")
        title_font = QFont("Segoe UI", 20, QFont.Weight.Bold)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        v.addLayout(header_layout)

        # Info text
        info_label = QLabel(
            "Phiên chơi của bạn đã kết thúc. Vui lòng thanh toán các khoản phí dưới đây:"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #64748b; font-size: 14px; padding: 5px 0;")
        v.addWidget(info_label)

        # Play time section
        play_frame = QFrame()
        play_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f0f9ff, stop:1 #e0f2fe);
                border: 2px solid #0ea5e9;
                border-radius: 12px;
            }
        """)
        play_layout = QVBoxLayout(play_frame)
        play_layout.setContentsMargins(15, 15, 15, 15)

        play_title = QLabel("🕒 Phí chơi máy (theo giờ)")
        play_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #0c4a6e;")
        play_layout.addWidget(play_title)

        self._lbl_play = QLabel()
        self._lbl_play.setWordWrap(True)
        self._lbl_play.setStyleSheet("color: #374151; font-size: 14px; padding: 5px 0;")
        play_layout.addWidget(self._lbl_play)

        self._btn_qr_play = QPushButton("📱 Mã VietQR — Phí chơi máy")
        self._btn_qr_play.setEnabled(play_amount > 0 and is_vietqr_configured())
        self._btn_qr_play.clicked.connect(
            lambda: self._open_qr(
                "Phí chơi máy",
                int(round(play_amount)),
                f"NET {username_hint}"[:50] if username_hint else "PHI NET",
                "Chuyển khoản ghi nhớ nội dung để quầy đối soát phí giờ chơi.",
            )
        )
        play_layout.addWidget(self._btn_qr_play)
        v.addWidget(play_frame)

        # Food section
        if food_amt > 0:
            food_frame = QFrame()
            food_frame.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #fefce8, stop:1 #fef3c7);
                    border: 2px solid #d97706;
                    border-radius: 12px;
                }
            """)
            food_layout = QVBoxLayout(food_frame)
            food_layout.setContentsMargins(15, 15, 15, 15)

            food_title = QLabel("🍽️ Đồ ăn / nước uống")
            food_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #92400e;")
            food_layout.addWidget(food_title)

            self._lbl_food = QLabel()
            self._lbl_food.setWordWrap(True)
            self._lbl_food.setStyleSheet("color: #374151; font-size: 14px; padding: 5px 0;")
            food_layout.addWidget(self._lbl_food)

            self._btn_qr_food = QPushButton("📱 Mã VietQR — Đồ ăn / nước")
            self._btn_qr_food.setEnabled(food_amt > 0 and is_vietqr_configured())
            self._btn_qr_food.clicked.connect(
                lambda: self._open_qr(
                    "Đồ ăn / nước (quầy)",
                    int(round(food_amt)),
                    f"DOAN {username_hint}"[:50] if username_hint else "DOAN QUAY",
                    "Thanh toán công nợ đặt món — không liên quan ví phí giờ chơi máy.",
                )
            )
            food_layout.addWidget(self._btn_qr_food)
            v.addWidget(food_frame)

        # VietQR config warning
        if not is_vietqr_configured():
            warning_frame = QFrame()
            warning_frame.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #fef2f2, stop:1 #fee2e2);
                    border: 2px solid #dc2626;
                    border-radius: 12px;
                }
            """)
            warning_layout = QVBoxLayout(warning_frame)
            warning_layout.setContentsMargins(15, 15, 15, 15)

            warning_label = QLabel("⚠️ Chưa cấu hình VietQR")
            warning_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #991b1b;")
            warning_layout.addWidget(warning_label)

            config_label = QLabel(
                "Hệ thống VietQR chưa được cấu hình (config/vietqr.json). "
                "Vui lòng thanh toán trực tiếp tại quầy."
            )
            config_label.setWordWrap(True)
            config_label.setStyleSheet("color: #7f1d1d; font-size: 13px;")
            warning_layout.addWidget(config_label)
            v.addWidget(warning_frame)

        # Close button
        close_btn = QPushButton("✅ Hoàn thành")
        close_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #10b981, stop:1 #059669);
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 30px;
                font-size: 14px;
                font-weight: 600;
                min-width: 150px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #059669, stop:1 #047857);
            }
        """)
        close_btn.clicked.connect(self.accept)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        button_layout.addStretch()
        v.addLayout(button_layout)

        self._set_play_text(total_seconds, price_per_hour, play_amount)
        self._set_food_text(food_amt)

    def _set_play_text(self, total_seconds: int, price_per_hour: float, play_amount: float):
        def fmt_dur(s):
            h = int(s // 3600)
            m = int((s % 3600) // 60)
            sec = int(s % 60)
            return f"{h:02d}:{m:02d}:{sec:02d}"

        self._lbl_play.setText(
            f"Phí chơi máy\n"
            f"Thời gian: {fmt_dur(total_seconds)}\n"
            f"Đơn giá: {price_per_hour:,.0f} VNĐ/giờ\n"
            f"Tạm tính: {play_amount:,.0f} VNĐ".replace(",", ".")
        )

    def _set_food_text(self, food_amt: float):
        if food_amt <= 0:
            self._lbl_food.setText(
                "Đồ ăn / nước\nChưa có công nợ (hoặc chưa xác nhận đơn)."
            )
        else:
            self._lbl_food.setText(
                "Đồ ăn / nước (công nợ quầy)\n"
                f"Tổng cần thanh toán khi ra: {food_amt:,.0f} VNĐ".replace(",", ".")
            )

    def _open_qr(self, title: str, amount_vnd: int, note: str, help_text: str):
        dlg = VietQRPaymentDialog(
            self,
            title=f"VietQR — {title}",
            amount_vnd=amount_vnd,
            transfer_note=note,
            help_text=help_text,
        )
        dlg.exec()
