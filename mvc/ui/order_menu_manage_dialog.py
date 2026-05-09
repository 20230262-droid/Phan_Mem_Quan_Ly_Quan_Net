"""Máy chủ: thêm / sửa / xóa sản phẩm trong danh mục order (JSON hoặc SQL Server)."""

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class OrderMenuManageDialog(QDialog):
    def __init__(self, parent, menu_model):
        super().__init__(parent)
        self._model = menu_model
        self.setWindowTitle("Danh mục order — sản phẩm")
        self.setMinimumSize(560, 400)

        v = QVBoxLayout(self)
        v.addWidget(QLabel(self._model.storage_hint + " Máy trạm chỉ thấy món đang bật «Hiển thị»."))

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Mã", "Tên", "Giá (đ)", "Hiển thị"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        v.addWidget(self.table)

        row_btn = QHBoxLayout()
        self.btn_add = QPushButton("Thêm")
        self.btn_edit = QPushButton("Sửa")
        self.btn_del = QPushButton("Xóa")
        self.btn_refresh = QPushButton("Tải lại")
        self.btn_add.clicked.connect(self._add)
        self.btn_edit.clicked.connect(self._edit)
        self.btn_del.clicked.connect(self._delete)
        self.btn_refresh.clicked.connect(self._reload)
        row_btn.addWidget(self.btn_add)
        row_btn.addWidget(self.btn_edit)
        row_btn.addWidget(self.btn_del)
        row_btn.addStretch()
        row_btn.addWidget(self.btn_refresh)
        v.addLayout(row_btn)

        btn_close = QPushButton("Đóng")
        btn_close.clicked.connect(self.accept)
        v.addWidget(btn_close)

        self._reload()

    def _reload(self):
        rows = self._model.list_all()
        self.table.setRowCount(len(rows))
        for r, p in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(str(p["id"])))
            self.table.setItem(r, 1, QTableWidgetItem(p["name"]))
            self.table.setItem(r, 2, QTableWidgetItem(f'{int(p["price"]):,}'))
            self.table.setItem(
                r, 3, QTableWidgetItem("Có" if p.get("active", True) else "Không")
            )
        self.table.resizeColumnsToContents()

    def _selected_id(self):
        r = self.table.currentRow()
        if r < 0:
            return None
        it = self.table.item(r, 0)
        if not it:
            return None
        try:
            return int(it.text())
        except ValueError:
            return None

    def _add(self):
        d = QDialog(self)
        d.setWindowTitle("Thêm sản phẩm")
        f = QFormLayout(d)
        ed_name = QLineEdit()
        sp_price = QDoubleSpinBox()
        sp_price.setRange(0, 1_000_000_000)
        sp_price.setDecimals(0)
        sp_price.setSingleStep(1000)
        sp_price.setValue(10000)
        cb = QCheckBox("Hiển thị trên máy trạm")
        cb.setChecked(True)
        f.addRow("Tên:", ed_name)
        f.addRow("Giá (đ):", sp_price)
        f.addRow(cb)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        f.addRow(bb)
        if d.exec() != 1:
            return
        ok, msg = self._model.add_product(
            ed_name.text(), sp_price.value(), cb.isChecked()
        )
        if not ok:
            QMessageBox.warning(self, "Lỗi", msg)
            return
        self._reload()

    def _edit(self):
        pid = self._selected_id()
        if pid is None:
            QMessageBox.information(self, "Sửa", "Chọn một dòng trong bảng.")
            return
        rows = self._model.list_all()
        cur = next((x for x in rows if x["id"] == pid), None)
        if not cur:
            return
        d = QDialog(self)
        d.setWindowTitle(f"Sửa sản phẩm #{pid}")
        f = QFormLayout(d)
        ed_name = QLineEdit(cur["name"])
        sp_price = QDoubleSpinBox()
        sp_price.setRange(0, 1_000_000_000)
        sp_price.setDecimals(0)
        sp_price.setSingleStep(1000)
        sp_price.setValue(float(cur["price"]))
        cb = QCheckBox("Hiển thị trên máy trạm")
        cb.setChecked(bool(cur.get("active", True)))
        f.addRow("Tên:", ed_name)
        f.addRow("Giá (đ):", sp_price)
        f.addRow(cb)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        f.addRow(bb)
        if d.exec() != 1:
            return
        ok, msg = self._model.update_product(
            pid, ed_name.text(), sp_price.value(), cb.isChecked()
        )
        if not ok:
            QMessageBox.warning(self, "Lỗi", msg)
            return
        self._reload()

    def _delete(self):
        pid = self._selected_id()
        if pid is None:
            QMessageBox.information(self, "Xóa", "Chọn một dòng trong bảng.")
            return
        r = QMessageBox.question(
            self,
            "Xóa",
            f"Xóa sản phẩm mã {pid}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        ok, msg = self._model.delete_product(pid)
        if not ok:
            QMessageBox.warning(self, "Lỗi", msg)
            return
        self._reload()
