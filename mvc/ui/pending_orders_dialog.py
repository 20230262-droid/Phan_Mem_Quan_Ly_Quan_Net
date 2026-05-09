"""Máy chủ: danh sách đơn order bếp/quầy."""

import time
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class PendingOrdersDialog(QDialog):
    def __init__(self, parent, server, on_changed=None):
        super().__init__(parent)
        self._server = server
        self._on_changed = on_changed
        self._deliver_ready_seconds = 60
        self.setWindowTitle("Đơn bếp/quầy")
        self.setMinimumSize(620, 400)

        v = QVBoxLayout(self)
        v.addWidget(
            QLabel(
                "❌ Đơn mới: chờ quầy xác nhận. "
                "✅ Sau khi xác nhận, chờ tới thời điểm ra đồ rồi bấm «Đã ra đồ» hoặc «Chưa ra được»."
            )
        )
        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.list.itemSelectionChanged.connect(self._on_selection_changed)
        v.addWidget(self.list)

        row = QHBoxLayout()
        self.btn_confirm = QPushButton("Xác nhận đơn")
        self.btn_cancel = QPushButton("Hủy đơn")
        self.btn_delivered = QPushButton("✅ Đã ra đồ")
        self.btn_failed = QPushButton("❌ Chưa ra được")
        self.btn_refresh = QPushButton("Tải lại")
        self.btn_confirm.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.btn_delivered.setEnabled(False)
        self.btn_failed.setEnabled(False)
        self.btn_confirm.clicked.connect(self._confirm)
        self.btn_cancel.clicked.connect(self._cancel)
        self.btn_delivered.clicked.connect(self._mark_delivered)
        self.btn_failed.clicked.connect(self._mark_failed)
        self.btn_refresh.clicked.connect(self._reload)
        row.addWidget(self.btn_confirm)
        row.addWidget(self.btn_cancel)
        row.addWidget(self.btn_delivered)
        row.addWidget(self.btn_failed)
        row.addStretch()
        row.addWidget(self.btn_refresh)
        v.addLayout(row)

        btn_close = QPushButton("Đóng")
        btn_close.clicked.connect(self.accept)
        v.addWidget(btn_close)

        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._auto_refresh)
        self._refresh_timer.start(1000)

        self._reload()

    def _selected_order(self):
        it = self.list.currentItem()
        data = it.data(Qt.ItemDataRole.UserRole) if it else None
        return data if isinstance(data, dict) else None

    def _selected_order_id(self):
        info = self._selected_order()
        return int(info.get("id", 0)) if info else None

    def _on_selection_changed(self):
        info = self._selected_order()
        self.btn_confirm.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.btn_delivered.setEnabled(False)
        self.btn_failed.setEnabled(False)
        if not info:
            return
        stage = info.get("stage")
        if stage == "pending_confirm":
            self.btn_confirm.setEnabled(True)
            self.btn_cancel.setEnabled(True)
            return
        if stage == "confirmed_wait_delivery":
            elapsed = int(time.time() - float(info.get("confirmed_at", time.time())))
            if elapsed >= self._deliver_ready_seconds:
                self.btn_delivered.setEnabled(True)
                self.btn_failed.setEnabled(True)

    def _reload(self):
        selected_order_id = self._selected_order_id()
        self.list.clear()
        orders = self._server.list_kitchen_orders()
        now = time.time()
        for o in orders:
            created_at = float(o.get("created_at", now) or now)
            prep_minutes = int(o.get("prep_minutes", 15) or 15)
            base = (
                f"#{o['id']}  ·  PC {o['pc_index']}  ·  "
                f"{o['username'] or '—'}  ·  {int(o['total_vnd']):,} đ\n"
                f"⏰ Dự kiến: ~{prep_minutes} phút  ·  Chờ: {max(0, int((now - created_at) // 60))} phút"
            )
            if o.get("stage") == "pending_confirm":
                status = "  ·  ❌ Chưa xác nhận"
            else:
                confirmed_at = float(o.get("confirmed_at", now) or now)
                since_confirm = max(0, int((now - confirmed_at) // 60))
                status = f"  ·  ✅ Đã xác nhận {since_confirm} phút trước"
            it = QListWidgetItem(base + status)
            it.setData(Qt.ItemDataRole.UserRole, dict(o))
            it.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.list.addItem(it)

        if selected_order_id is not None:
            for i in range(self.list.count()):
                item = self.list.item(i)
                data = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(data, dict) and int(data.get("id", 0)) == int(selected_order_id):
                    self.list.setCurrentItem(item)
                    item.setSelected(True)
                    break
        self._on_selection_changed()

    def _auto_refresh(self):
        try:
            self._reload()
        except Exception:
            pass

    def _confirm(self):
        oid = self._selected_order_id()
        if oid is None:
            QMessageBox.information(self, "Xác nhận", "Chọn một đơn trong danh sách.")
            return
        ok, msg = self._server.confirm_pending_order(int(oid))
        if not ok:
            QMessageBox.warning(self, "Không xác nhận được", msg)
        else:
            QMessageBox.information(self, "Đã xác nhận", "Đơn đã xác nhận, chờ ra món.")
        self._reload()
        if self._on_changed:
            self._on_changed()

    def _cancel(self):
        oid = self._selected_order_id()
        if oid is None:
            QMessageBox.information(self, "Hủy", "Chọn một đơn trong danh sách.")
            return
        r = QMessageBox.question(
            self,
            "Hủy đơn",
            "Hủy đơn này? Máy trạm sẽ nhận thông báo (không trừ tiền).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        ok, err = self._server.cancel_pending_order(int(oid))
        if not ok:
            QMessageBox.warning(self, "Lỗi", err)
        self._reload()
        if self._on_changed:
            self._on_changed()

    def _mark_delivered(self):
        oid = self._selected_order_id()
        if oid is None:
            QMessageBox.information(self, "Đã ra đồ", "Chọn một đơn trong danh sách.")
            return
        ok, err = self._server.mark_order_delivered(int(oid))
        if not ok:
            QMessageBox.warning(self, "Lỗi", err)
        self._reload()
        if self._on_changed:
            self._on_changed()

    def _mark_failed(self):
        oid = self._selected_order_id()
        if oid is None:
            QMessageBox.information(self, "Chưa ra được", "Chọn một đơn trong danh sách.")
            return
        ok, err = self._server.mark_order_failed(int(oid))
        if not ok:
            QMessageBox.warning(self, "Lỗi", err)
        self._reload()
        if self._on_changed:
            self._on_changed()

    def closeEvent(self, event):
        self._refresh_timer.stop()
        super().closeEvent(event)
        if self._on_changed:
            self._on_changed()