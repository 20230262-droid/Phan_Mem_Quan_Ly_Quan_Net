"""Hộp thoại quản lý tài khoản: tìm kiếm, thêm, sửa, xóa."""

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class UserEditDialog(QDialog):
    def __init__(self, parent, user_model, mode="add", username=None):
        super().__init__(parent)
        self.user_model = user_model
        self.mode = mode
        self.setWindowTitle("Thêm tài khoản" if mode == "add" else "Sửa tài khoản")
        self.setMinimumWidth(380)

        self.edt_username = QLineEdit()
        self.edt_password = QLineEdit()
        self.edt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.spin_balance = QDoubleSpinBox()
        self.spin_balance.setRange(0, 1_000_000_000)
        self.spin_balance.setDecimals(0)
        self.spin_balance.setSingleStep(10000)
        self.spin_food_tab = QDoubleSpinBox()
        self.spin_food_tab.setRange(0, 1_000_000_000)
        self.spin_food_tab.setDecimals(0)
        self.spin_food_tab.setSingleStep(10000)
        self.cmb_type = QComboBox()
        self.cmb_type.addItem("Thường", "normal")
        self.cmb_type.addItem("VIP", "vip")

        form = QFormLayout()
        form.addRow("Tên đăng nhập:", self.edt_username)
        form.addRow("Mật khẩu:", self.edt_password)
        form.addRow("Tiền chơi máy (VNĐ):", self.spin_balance)
        form.addRow("Công nợ đồ ăn (VNĐ):", self.spin_food_tab)
        form.addRow("Loại:", self.cmb_type)

        if mode == "edit" and username:
            self.edt_username.setText(username)
            self.edt_username.setReadOnly(True)
            self.edt_password.setPlaceholderText("Để trống nếu không đổi mật khẩu")
            u = user_model.get_user(username)
            if u:
                self.spin_balance.setValue(int(float(u.get("balance", 0) or 0)))
                self.spin_food_tab.setValue(int(float(u.get("food_tab_vnd", 0) or 0)))
                t = (u.get("type") or "normal").lower()
                self.cmb_type.setCurrentIndex(1 if t == "vip" else 0)
        else:
            self.edt_password.setPlaceholderText("Bắt buộc khi thêm mới")
            self.spin_food_tab.setValue(0)
            self.spin_food_tab.setEnabled(False)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(buttons)

    def _on_accept(self):
        name = self.edt_username.text().strip()
        pw = self.edt_password.text()
        bal = float(self.spin_balance.value())
        ftab = float(self.spin_food_tab.value())
        ut = self.cmb_type.currentData()

        if not name:
            QMessageBox.warning(self, "Lỗi", "Nhập tên đăng nhập.")
            return
        if self.mode == "add":
            if not pw:
                QMessageBox.warning(self, "Lỗi", "Nhập mật khẩu cho tài khoản mới.")
                return
            ok, msg = self.user_model.register(name, pw, ut, balance=bal)
            if not ok:
                QMessageBox.warning(self, "Lỗi", msg)
                return
        else:
            pw_arg = pw if pw else None
            ok, msg = self.user_model.update_user(
                name,
                password=pw_arg,
                balance=bal,
                user_type=ut,
                food_tab_vnd=ftab,
            )
            if not ok:
                QMessageBox.warning(self, "Lỗi", msg)
                return
        self.accept()


class UserManagementDialog(QDialog):
    def __init__(self, user_model, parent=None):
        super().__init__(parent)
        self.user_model = user_model
        self.setWindowTitle("Quản lý người dùng")
        self.resize(640, 420)

        self.edt_search = QLineEdit()
        self.edt_search.setPlaceholderText("Tìm theo tên đăng nhập…")
        btn_search = QPushButton("Tìm kiếm")
        btn_search.clicked.connect(self._reload_table)
        self.edt_search.returnPressed.connect(self._reload_table)

        row_search = QHBoxLayout()
        row_search.addWidget(QLabel("Tìm:"))
        row_search.addWidget(self.edt_search, 1)
        row_search.addWidget(btn_search)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Tên đăng nhập", "Tiền chơi máy", "Công nợ đồ ăn", "Loại"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)

        btn_add = QPushButton("Thêm")
        btn_add.clicked.connect(self._add)
        btn_edit = QPushButton("Sửa")
        btn_edit.clicked.connect(self._edit)
        btn_del = QPushButton("Xóa")
        btn_del.clicked.connect(self._delete)
        btn_close = QPushButton("Đóng")
        btn_close.clicked.connect(self.accept)

        row_btns = QHBoxLayout()
        row_btns.addWidget(btn_add)
        row_btns.addWidget(btn_edit)
        row_btns.addWidget(btn_del)
        row_btns.addStretch()
        row_btns.addWidget(btn_close)

        lay = QVBoxLayout(self)
        lay.addLayout(row_search)
        lay.addWidget(self.table, 1)
        lay.addLayout(row_btns)

        self._reload_table()

    def _search_text(self):
        return self.edt_search.text().strip()

    def _reload_table(self):
        rows = self.user_model.list_users(self._search_text())
        self.table.setRowCount(0)
        for r in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(r["username"]))
            self.table.setItem(row, 1, QTableWidgetItem(f"{r['balance']:,.0f}"))
            self.table.setItem(
                row, 2, QTableWidgetItem(f"{r.get('food_tab_vnd', 0):,.0f}")
            )
            self.table.setItem(row, 3, QTableWidgetItem(str(r.get("type", ""))))
        self.table.resizeColumnsToContents()

    def _selected_username(self):
        r = self.table.currentRow()
        if r < 0:
            return None
        it = self.table.item(r, 0)
        return it.text().strip() if it else None

    def _add(self):
        dlg = UserEditDialog(self, self.user_model, mode="add")
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._reload_table()

    def _edit(self):
        name = self._selected_username()
        if not name:
            QMessageBox.information(self, "Chọn tài khoản", "Chọn một dòng trong bảng trước.")
            return
        dlg = UserEditDialog(self, self.user_model, mode="edit", username=name)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._reload_table()

    def _delete(self):
        name = self._selected_username()
        if not name:
            QMessageBox.information(self, "Chọn tài khoản", "Chọn một dòng trong bảng trước.")
            return
        if (
            QMessageBox.question(
                self,
                "Xác nhận",
                f"Xóa tài khoản «{name}»? Lịch sử dùng máy (nếu có) cũng sẽ bị xóa.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        ok, msg = self.user_model.delete_user(name)
        if ok:
            QMessageBox.information(self, "OK", msg)
            self._reload_table()
        else:
            QMessageBox.warning(self, "Lỗi", msg)
