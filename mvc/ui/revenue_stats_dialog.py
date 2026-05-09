from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap, QPdfWriter, QPageSize
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class RevenueChartWidget(QWidget):
    def __init__(self, color: str, chart_style: str = "bar", parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._style = chart_style
        self._values: list[float] = []
        self._labels: list[str] = []
        self.setMinimumHeight(140)

    def set_series(self, values: list[float], labels: list[str] | None = None):
        self._values = [max(0.0, float(v or 0)) for v in (values or [])]
        self._labels = [str(x) for x in (labels or [])]
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(8, 8, -8, -8)
        p.fillRect(r, QColor("#1f1f1f"))
        axis_left = r.left() + 58
        axis_right = r.right() - 10
        axis_top = r.top() + 10
        axis_bottom = r.bottom() - 26
        if not self._values:
            p.setPen(QColor("#999999"))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "Không có dữ liệu")
            return
        vmax = max(self._values) if self._values else 0.0
        if vmax <= 0:
            p.setPen(QColor("#999999"))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "Không có doanh thu")
            return
        # Vẽ trục Y và các mốc giá trị.
        p.setPen(QColor("#666666"))
        p.drawLine(axis_left, axis_top, axis_left, axis_bottom)
        p.drawLine(axis_left, axis_bottom, axis_right, axis_bottom)
        tick_count = 4
        for i in range(tick_count + 1):
            ratio = i / tick_count
            y = axis_bottom - int((axis_bottom - axis_top) * ratio)
            val = vmax * ratio
            p.setPen(QColor("#3f3f3f"))
            p.drawLine(axis_left, y, axis_right, y)
            p.setPen(QColor("#c9c9c9"))
            p.drawText(r.left() + 2, y - 2, f"{int(val):,}")
        n = len(self._values)
        bottom = axis_bottom
        left = axis_left + 6
        right = axis_right - 4
        width = max(1, right - left)
        step = width / max(1, n)
        if self._style == "line":
            points = []
            for i, v in enumerate(self._values):
                x = left + int((i + 0.5) * step)
                h = int((v / vmax) * max(1, axis_bottom - axis_top))
                y = bottom - h
                points.append((x, y))
            p.setPen(QPen(self._color, 2))
            for i in range(1, len(points)):
                p.drawLine(points[i - 1][0], points[i - 1][1], points[i][0], points[i][1])
            p.setPen(QPen(self._color, 1))
            for x, y in points:
                p.drawEllipse(x - 2, y - 2, 4, 4)
        else:
            bar_w = max(2, int(step * 0.65))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self._color)
            for i, v in enumerate(self._values):
                x = left + int(i * step + (step - bar_w) / 2)
                h = int((v / vmax) * max(1, axis_bottom - axis_top))
                y = bottom - h
                p.drawRoundedRect(x, y, bar_w, h, 2, 2)
        # Vẽ nhãn trục X dạng mốc chính để dễ đọc.
        p.setPen(QColor("#bdbdbd"))
        if n <= 12:
            label_indices = set(range(n))
        else:
            label_indices = {0, n // 2, n - 1}
        for i in sorted(label_indices):
            if i < 0 or i >= n:
                continue
            x = left + int((i + 0.5) * step)
            p.drawLine(x, axis_bottom, x, axis_bottom + 3)
            if i < len(self._labels) and self._labels[i]:
                txt = self._labels[i]
            else:
                txt = str(i + 1)
            p.drawText(x - 14, axis_bottom + 16, txt)


class RevenueStatsDialog(QDialog):
    def __init__(self, parent, fetch_summary_fn):
        super().__init__(parent)
        self._fetch_summary = fetch_summary_fn
        self.setWindowTitle("Thống kê doanh thu")
        self.setMinimumSize(900, 620)

        v = QVBoxLayout(self)
        v.addWidget(QLabel("Chọn kỳ thống kê doanh thu:"))

        row = QHBoxLayout()
        self.cbo_period = QComboBox()
        self.cbo_period.addItem("Theo ngày", "day")
        self.cbo_period.addItem("Theo tuần", "week")
        self.cbo_period.addItem("Theo tháng", "month")
        self.cbo_period.addItem("Theo năm", "year")
        row.addWidget(self.cbo_period, 1)
        self.btn_refresh = QPushButton("Xem thống kê")
        self.btn_refresh.clicked.connect(self._reload)
        row.addWidget(self.btn_refresh)
        v.addLayout(row)

        self.lbl_range = QLabel("Khoảng thời gian: -")
        self.lbl_usage = QLabel("Doanh thu tiền giờ: 0 đ")
        self.lbl_order = QLabel("Doanh thu order: 0 đ")
        self.lbl_total = QLabel("Tổng doanh thu: 0 đ")
        self.lbl_count = QLabel("Số giao dịch: 0")
        self.lbl_total.setStyleSheet("font-weight: bold; font-size: 15px;")
        for w in (self.lbl_range, self.lbl_usage, self.lbl_order, self.lbl_total, self.lbl_count):
            v.addWidget(w)

        self._cards = {}
        self._charts_container = QWidget()
        grid = QGridLayout()
        grid.setSpacing(8)
        chart_specs = [
            ("day", "Biểu đồ theo ngày", "#1976d2", "bar"),
            ("week", "Biểu đồ theo tuần", "#2e7d32", "line"),
            ("month", "Biểu đồ theo tháng", "#ef6c00", "bar"),
            ("year", "Biểu đồ theo năm", "#8e24aa", "line"),
        ]
        for i, (period, title, color, shape) in enumerate(chart_specs):
            box = QWidget()
            bv = QVBoxLayout(box)
            bv.setContentsMargins(4, 4, 4, 4)
            lbl_title = QLabel(title)
            lbl_title.setStyleSheet("font-weight: bold;")
            bv.addWidget(lbl_title)
            chart = RevenueChartWidget(color=color, chart_style=shape)
            bv.addWidget(chart)
            legend = QLabel(
                f"Legend: Tổng doanh thu ({'đường' if shape == 'line' else 'cột'})"
            )
            legend.setStyleSheet(f"color: {color}; font-size: 11px;")
            bv.addWidget(legend)
            lbl_sum = QLabel("Tổng: 0 đ")
            bv.addWidget(lbl_sum)
            self._cards[period] = {"chart": chart, "sum": lbl_sum, "legend": legend}
            grid.addWidget(box, i // 2, i % 2)
        self._charts_container.setLayout(grid)
        v.addWidget(self._charts_container)

        row_export = QHBoxLayout()
        self.btn_export_image = QPushButton("Xuất ảnh biểu đồ")
        self.btn_export_image.clicked.connect(self._export_chart_image)
        row_export.addWidget(self.btn_export_image)
        self.btn_export_pdf = QPushButton("Xuất PDF báo cáo")
        self.btn_export_pdf.clicked.connect(self._export_report_pdf)
        row_export.addWidget(self.btn_export_pdf)
        row_export.addStretch()
        btn_close = QPushButton("Đóng")
        btn_close.clicked.connect(self.accept)
        row_export.addWidget(btn_close)
        v.addLayout(row_export)

        self.cbo_period.currentIndexChanged.connect(self._reload)
        self._reload()

    def _reload(self):
        period = self.cbo_period.currentData()
        data = self._fetch_summary(period) if self._fetch_summary else {}
        start = str(data.get("start") or "-")
        end = str(data.get("end") or "-")
        usage = int(data.get("usage_vnd", 0) or 0)
        order = int(data.get("order_vnd", 0) or 0)
        total = int(data.get("total_vnd", 0) or 0)
        count = int(data.get("transactions", 0) or 0)
        self.lbl_range.setText(f"Khoảng thời gian: {start}  ->  {end}")
        self.lbl_usage.setText(f"Doanh thu tiền giờ: {usage:,} đ")
        self.lbl_order.setText(f"Doanh thu order: {order:,} đ")
        self.lbl_total.setText(f"Tổng doanh thu: {total:,} đ")
        self.lbl_count.setText(f"Số giao dịch: {count}")
        for p in ("day", "week", "month", "year"):
            d = self._fetch_summary(p) if self._fetch_summary else {}
            vals = d.get("series_total_vnd") or []
            labels = d.get("labels") or []
            card = self._cards.get(p)
            if not card:
                continue
            card["chart"].set_series(vals, labels)
            card["sum"].setText(f"Tổng: {int(d.get('total_vnd', 0) or 0):,} đ")

    def _export_chart_image(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu ảnh biểu đồ",
            "revenue_charts.png",
            "PNG Image (*.png)",
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        pix = self._charts_container.grab()
        ok = pix.save(path, "PNG")
        if ok:
            QMessageBox.information(self, "Xuất ảnh", f"Đã lưu ảnh biểu đồ:\n{path}")
        else:
            QMessageBox.warning(self, "Xuất ảnh", "Không lưu được ảnh biểu đồ.")

    def _export_report_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu PDF báo cáo",
            "revenue_report.pdf",
            "PDF Files (*.pdf)",
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        writer = QPdfWriter(path)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setResolution(150)
        painter = QPainter(writer)
        try:
            painter.setPen(QColor("#111111"))
            painter.drawText(80, 120, "BAO CAO THONG KE DOANH THU")
            period = self.cbo_period.currentText()
            painter.drawText(80, 165, f"Ky dang xem: {period}")
            painter.drawText(80, 205, self.lbl_range.text())
            painter.drawText(80, 245, self.lbl_usage.text())
            painter.drawText(80, 285, self.lbl_order.text())
            painter.drawText(80, 325, self.lbl_total.text())
            painter.drawText(80, 365, self.lbl_count.text())

            charts_pix = self._charts_container.grab()
            target_w = writer.width() - 160
            src_w = max(1, charts_pix.width())
            src_h = max(1, charts_pix.height())
            target_h = int(src_h * (target_w / src_w))
            if target_h > writer.height() - 450:
                target_h = writer.height() - 450
                target_w = int(src_w * (target_h / src_h))
            scaled = charts_pix.scaled(
                target_w,
                target_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(80, 420, scaled)
        finally:
            painter.end()
        QMessageBox.information(self, "Xuất PDF", f"Đã lưu báo cáo PDF:\n{path}")
