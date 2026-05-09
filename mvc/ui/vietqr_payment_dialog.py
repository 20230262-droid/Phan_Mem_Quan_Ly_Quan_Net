"""Hộp thoại thanh toán VietQR: STK + mã QR (ảnh từ img.vietqr.io)."""

import urllib.request

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
)

from config.vietqr_settings import build_vietqr_image_url, is_vietqr_configured, load_vietqr_config


class VietQRPaymentDialog(QDialog):
    def __init__(
        self,
        parent,
        *,
        title: str,
        amount_vnd: int,
        transfer_note: str,
        help_text: str = "",
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self._amount_vnd = max(0, int(amount_vnd))
        self._note = (transfer_note or "").strip()
        self._help = (help_text or "").strip()

        c = load_vietqr_config()
        self._bank_bin = c["bank_bin"]
        self._account_no = c["account_no"]
        self._account_name = c["account_name"]

        v = QVBoxLayout(self)

        if self._help:
            lbl_h = QLabel(self._help)
            lbl_h.setWordWrap(True)
            lbl_h.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            v.addWidget(lbl_h)

        row_acc = QHBoxLayout()
        self._lbl_stk = QLabel()
        self._lbl_stk.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        btn_copy_stk = QPushButton("Sao chép STK")
        btn_copy_stk.clicked.connect(self._copy_stk)
        row_acc.addWidget(self._lbl_stk, 1)
        row_acc.addWidget(btn_copy_stk)
        v.addLayout(row_acc)

        if self._amount_vnd > 0:
            v.addWidget(QLabel(f"Số tiền: {self._amount_vnd:,} VNĐ".replace(",", ".")))

        self._qr_label = QLabel()
        self._qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_label.setMinimumSize(280, 280)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._qr_label)
        v.addWidget(scroll, 1)

        self._err_label = QLabel("")
        self._err_label.setWordWrap(True)
        self._err_label.setStyleSheet("color: #b91c1c;")
        v.addWidget(self._err_label)

        row_close = QHBoxLayout()
        row_close.addStretch()
        btn_close = QPushButton("Đóng")
        btn_close.clicked.connect(self.accept)
        row_close.addWidget(btn_close)
        v.addLayout(row_close)

        self._apply_account_labels()
        self._load_qr()

    def _apply_account_labels(self):
        if not is_vietqr_configured():
            self._lbl_stk.setText(
                "Chưa cấu hình VietQR. Sửa file config/vietqr.json (bank_bin, account_no)."
            )
            return
        name = self._account_name or "—"
        self._lbl_stk.setText(
            f"Ngân hàng (BIN): {self._bank_bin}\n"
            f"Số tài khoản: {self._account_no}\n"
            f"Chủ TK: {name}"
        )

    def _load_qr(self):
        if not is_vietqr_configured():
            self._err_label.setText("Không tải được QR — thiếu cấu hình ngân hàng.")
            return
        url = build_vietqr_image_url(self._amount_vnd, self._note)
        if not url:
            self._err_label.setText("Không tạo được URL VietQR.")
            return
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "QuanNetClient/1.0"},
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = resp.read()
            pix = QPixmap()
            if not pix.loadFromData(data):
                self._err_label.setText("Tải ảnh QR thất bại (định dạng không hợp lệ).")
                return
            self._qr_label.setPixmap(
                pix.scaled(
                    320,
                    320,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            self._err_label.setText("")
        except Exception as e:
            self._err_label.setText(f"Không tải được mã QR: {str(e)[:200]}")

    def _copy_stk(self):
        if not self._account_no:
            QMessageBox.information(self, "Sao chép", "Chưa có số tài khoản trong cấu hình.")
            return
        from PyQt6.QtWidgets import QApplication

        QApplication.clipboard().setText(self._account_no)
        QMessageBox.information(self, "Đã sao chép", "Đã copy số tài khoản vào clipboard.")
