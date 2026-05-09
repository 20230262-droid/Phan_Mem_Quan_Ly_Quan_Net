"""Máy trạm: chọn sản phẩm và số lượng, gửi đơn lên máy chủ."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QPushButton,
)
from PyQt6.QtGui import QFont, QIcon


class OrderClientDialog(QDialog):
    def __init__(self, parent, products: list, submit_callback):
        super().__init__(parent)
        self._submit = submit_callback
        self.setWindowTitle("🍽️ Đặt đồ ăn & thức uống")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
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
                font-weight: 500;
            }
            QTableWidget {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                gridline-color: #e2e8f0;
                selection-background-color: #dbeafe;
            }
            QHeaderView::section {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f1f5f9, stop:1 #e2e8f0);
                color: #374151;
                font-weight: 600;
                border: 1px solid #cbd5e1;
                padding: 8px;
                font-size: 13px;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f1f5f9;
                color: #1e293b;
            }
            QSpinBox {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px;
                min-width: 60px;
            }
            QSpinBox:focus {
                border-color: #3b82f6;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #10b981, stop:1 #059669);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 600;
                min-width: 100px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #059669, stop:1 #047857);
            }
            QPushButton:pressed {
                background: #047857;
            }
        """)

        self._products = products or []
        self._spins: list[QSpinBox] = []

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(15)

        # Header
        header_layout = QHBoxLayout()
        icon_label = QLabel("🍽️")
        icon_label.setFont(QFont("Segoe UI", 24))
        header_layout.addWidget(icon_label)

        title_label = QLabel("Đặt đồ ăn & thức uống")
        title_font = QFont("Segoe UI", 18, QFont.Weight.Bold)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        v.addLayout(header_layout)

        # Description
        desc_label = QLabel("Chọn số lượng cho từng món bạn muốn đặt. Quầy sẽ nhận thông báo ngay lập tức!")
        desc_label.setStyleSheet("color: #64748b; font-size: 13px; padding: 5px 0;")
        desc_label.setWordWrap(True)
        v.addWidget(desc_label)

        # Products table
        self.table = QTableWidget(len(self._products), 4)
        self.table.setHorizontalHeaderLabels(["🆔 Mã", "📋 Tên món", "💰 Giá (đ)", "🔢 Số lượng"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(self.table.styleSheet() + """
            QTableWidget {
                alternate-background-color: #f8fafc;
            }
        """)

        for row, p in enumerate(self._products):
            pid = int(p.get("id", 0))
            name = str(p.get("name", ""))
            price = int(p.get("price", 0))

            # ID column
            id_item = QTableWidgetItem(str(pid))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, id_item)

            # Name column
            name_item = QTableWidgetItem(name)
            self.table.setItem(row, 1, name_item)

            # Price column
            price_item = QTableWidgetItem(f"{price:,}")
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 2, price_item)

            # Make first 3 columns non-editable
            for c in range(3):
                it = self.table.item(row, c)
                if it:
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)

            # Quantity spinbox
            sp = QSpinBox()
            sp.setRange(0, 99)
            sp.setValue(0)
            sp.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._spins.append(sp)
            w = QWidget()
            hl = QVBoxLayout(w)
            hl.setContentsMargins(4, 2, 4, 2)
            hl.addWidget(sp)
            self.table.setCellWidget(row, 3, w)

        v.addWidget(self.table)

        # Total display
        self.total_label = QLabel("Tổng tiền: 0 đ")
        self.total_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #059669;
            padding: 10px;
            background: #ecfdf5;
            border-radius: 8px;
            border: 1px solid #a7f3d0;
        """)
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.total_label)

        # Connect spinbox changes to update total
        for spin in self._spins:
            spin.valueChanged.connect(self._update_total)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("❌ Hủy bỏ")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ef4444, stop:1 #dc2626);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 600;
                min-width: 100px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #dc2626, stop:1 #b91c1c);
            }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.send_btn = QPushButton("📤 Gửi đơn hàng")
        self.send_btn.clicked.connect(self._on_send)
        button_layout.addWidget(self.send_btn)

        button_layout.addStretch()
        v.addLayout(button_layout)

        self._update_total()

    def _update_total(self):
        total = 0
        for i, spin in enumerate(self._spins):
            qty = spin.value()
            if qty > 0 and i < len(self._products):
                price = int(self._products[i].get("price", 0))
                total += qty * price
        self.total_label.setText(f"💰 Tổng tiền: {total:,} đ")

    def _on_send(self):
        items = []
        for i, p in enumerate(self._products):
            qty = self._spins[i].value()
            if qty > 0:
                items.append({"id": int(p.get("id", 0)), "qty": qty})
        if not items:
            QMessageBox.warning(self, "Đặt hàng", "Vui lòng chọn ít nhất một món với số lượng > 0.")
            return

        # Confirmation dialog
        total = sum(self._spins[i].value() * int(self._products[i].get("price", 0))
                   for i in range(len(self._products)) if self._spins[i].value() > 0)
        reply = QMessageBox.question(
            self, "Xác nhận đặt hàng",
            f"Bạn có chắc muốn gửi đơn hàng với tổng tiền {total:,} đ không?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._submit(items)
            self.accept()
