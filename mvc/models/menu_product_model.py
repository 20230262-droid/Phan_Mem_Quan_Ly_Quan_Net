"""Danh mục sản phẩm order: JSON hoặc SQL Server (theo config/database.json)."""

from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from copy import deepcopy

from config.database import (
    build_sqlserver_connection_string,
    get_menu_products_json_path,
    resolve_storage_backend,
)

try:
    import pyodbc
except ImportError:
    pyodbc = None


class MenuProductModel:
    def __init__(self, path: str | None = None):
        self._mode = resolve_storage_backend()
        self._path = path or get_menu_products_json_path()
        self._lock = threading.Lock()
        self._products: list[dict] = []
        self._conn_str: str | None = None
        if self._mode == "json":
            self._load()
        else:
            if pyodbc is None:
                raise RuntimeError("Cần cài pyodbc để dùng SQL Server: pip install pyodbc")
            self._conn_str = build_sqlserver_connection_string()
            self._ensure_sql_connection()
            self._import_menu_json_if_sql_empty()

    @property
    def storage_hint(self) -> str:
        if self._mode == "sqlserver":
            return (
                "Dữ liệu lưu trên SQL Server: dbo.menu_products. "
                "Đơn hàng ghi vào dbo.orders và dbo.order_items."
            )
        return (
            "Dữ liệu lưu trong menu_products.json (cùng thư mục dự án). "
            "Máy trạm chỉ thấy sản phẩm đang bật «Hiển thị»."
        )

    def _load(self):
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._products = [self._normalize_row(x) for x in data if isinstance(x, dict)]
            else:
                self._products = []
        except (OSError, json.JSONDecodeError):
            self._products = []

    def _normalize_row(self, x: dict) -> dict:
        pid = int(x.get("id") or 0)
        name = str(x.get("name") or "").strip()
        try:
            price = float(x.get("price") or 0)
        except (TypeError, ValueError):
            price = 0.0
        active = bool(x.get("active", True))
        return {"id": pid, "name": name, "price": max(0.0, price), "active": active}

    def _save_unlocked(self):
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._products, f, ensure_ascii=False, indent=2)

    def _ensure_sql_connection(self):
        assert self._conn_str is not None
        try:
            with pyodbc.connect(self._conn_str, timeout=15) as conn:
                conn.cursor().execute("SELECT 1")
        except Exception as e:
            raise RuntimeError(
                "Không kết nối được SQL Server cho menu/order. Kiểm tra database.json "
                "và đã chạy sql/init_sqlserver.sql (dbo.menu_products, dbo.orders, dbo.order_items)."
            ) from e

    @contextmanager
    def _sql_connect(self):
        assert self._conn_str is not None
        conn = pyodbc.connect(self._conn_str, timeout=15)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _import_menu_json_if_sql_empty(self):
        if not os.path.isfile(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(data, list) or not data:
            return
        rows = [self._normalize_row(x) for x in data if isinstance(x, dict)]
        if not rows:
            return
        with self._sql_connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM dbo.menu_products")
            if cur.fetchone()[0] > 0:
                return
            cur.execute("SET IDENTITY_INSERT dbo.menu_products ON")
            try:
                for p in rows:
                    cur.execute(
                        """
                        INSERT INTO dbo.menu_products (id, name, price, is_active, sort_order)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        int(p["id"]),
                        p["name"],
                        float(p["price"]),
                        1 if p.get("active", True) else 0,
                        int(p["id"]),
                    )
            finally:
                cur.execute("SET IDENTITY_INSERT dbo.menu_products OFF")

    def _row_from_sql(self, r) -> dict:
        return {
            "id": int(r[0]),
            "name": str(r[1]),
            "price": float(r[2]),
            "active": bool(r[3]),
        }

    def list_active_for_menu(self) -> list[dict]:
        if self._mode == "json":
            with self._lock:
                out = []
                for p in self._products:
                    if not p.get("active", True):
                        continue
                    out.append(
                        {"id": p["id"], "name": p["name"], "price": int(p["price"])}
                    )
                return sorted(out, key=lambda x: x["id"])
        with self._sql_connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, name, price, is_active
                FROM dbo.menu_products
                WHERE is_active = 1
                ORDER BY sort_order, id
                """
            )
            return [
                {"id": int(r[0]), "name": str(r[1]), "price": int(float(r[2]))}
                for r in cur.fetchall()
            ]

    def list_all(self) -> list[dict]:
        if self._mode == "json":
            with self._lock:
                return deepcopy(sorted(self._products, key=lambda x: x["id"]))
        with self._sql_connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, name, price, is_active
                FROM dbo.menu_products
                ORDER BY sort_order, id
                """
            )
            return [self._row_from_sql(r) for r in cur.fetchall()]

    def _next_id_unlocked(self) -> int:
        if not self._products:
            return 1
        return max(p["id"] for p in self._products) + 1

    def add_product(self, name: str, price: float, active: bool = True) -> tuple[bool, str]:
        name = (name or "").strip()
        if not name:
            return False, "Tên không được trống"
        try:
            price = float(price)
        except (TypeError, ValueError):
            return False, "Giá không hợp lệ"
        if price < 0:
            return False, "Giá phải ≥ 0"
        if self._mode == "json":
            with self._lock:
                pid = self._next_id_unlocked()
                self._products.append(
                    {"id": pid, "name": name, "price": float(price), "active": bool(active)}
                )
                self._save_unlocked()
            return True, ""
        with self._sql_connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM dbo.menu_products")
            sort_order = int(cur.fetchone()[0])
            cur.execute(
                """
                INSERT INTO dbo.menu_products (name, price, is_active, sort_order)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?)
                """,
                name,
                float(price),
                1 if active else 0,
                sort_order,
            )
            _ = cur.fetchone()
        return True, ""

    def update_product(
        self, product_id: int, name: str, price: float, active: bool
    ) -> tuple[bool, str]:
        name = (name or "").strip()
        if not name:
            return False, "Tên không được trống"
        try:
            price = float(price)
        except (TypeError, ValueError):
            return False, "Giá không hợp lệ"
        if price < 0:
            return False, "Giá phải ≥ 0"
        if self._mode == "json":
            with self._lock:
                for p in self._products:
                    if p["id"] == int(product_id):
                        p["name"] = name
                        p["price"] = float(price)
                        p["active"] = bool(active)
                        self._save_unlocked()
                        return True, ""
            return False, "Không tìm thấy sản phẩm"
        with self._sql_connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE dbo.menu_products
                SET name = ?, price = ?, is_active = ?
                WHERE id = ?
                """,
                name,
                float(price),
                1 if active else 0,
                int(product_id),
            )
            if cur.rowcount == 0:
                return False, "Không tìm thấy sản phẩm"
        return True, ""

    def delete_product(self, product_id: int) -> tuple[bool, str]:
        if self._mode == "json":
            with self._lock:
                n = len(self._products)
                self._products = [p for p in self._products if p["id"] != int(product_id)]
                if len(self._products) == n:
                    return False, "Không tìm thấy sản phẩm"
                self._save_unlocked()
            return True, ""
        try:
            with self._sql_connect() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM dbo.menu_products WHERE id = ?", int(product_id))
                if cur.rowcount == 0:
                    return False, "Không tìm thấy sản phẩm"
        except Exception as e:
            if pyodbc is not None and isinstance(e, pyodbc.IntegrityError):
                return False, "Đã có đơn hàng dùng sản phẩm này, không xóa được."
            raise
        return True, ""

    def _product_index_for_order(self) -> dict[int, dict]:
        if self._mode == "json":
            with self._lock:
                return {p["id"]: dict(p) for p in self._products}
        with self._sql_connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, name, price, is_active FROM dbo.menu_products")
            return {int(r[0]): self._row_from_sql(r) for r in cur.fetchall()}

    def _format_summary(self, line_details: list[dict]) -> str:
        lines_txt = [
            f"  · {x['name']} x{x['qty']} = {x['subtotal']:,} đ" for x in line_details
        ]
        total = sum(x["subtotal"] for x in line_details)
        return "\n".join(lines_txt) + f"\n  Tạm tính: {total:,} đ"

    def _prepare_order_lines(self, items: list) -> tuple[list[dict] | None, str | None]:
        if not isinstance(items, list) or not items:
            return None, "Đơn trống"
        by_id = self._product_index_for_order()
        line_details: list[dict] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            try:
                pid = int(it.get("id"))
                qty = int(it.get("qty", 0))
            except (TypeError, ValueError):
                continue
            if qty <= 0:
                continue
            p = by_id.get(pid)
            if not p or not p.get("active", True):
                return None, f"Sản phẩm #{pid} không tồn tại hoặc đã tắt"
            unit = int(p["price"])
            sub = unit * qty
            line_details.append(
                {
                    "product_id": pid,
                    "qty": qty,
                    "unit_price": float(unit),
                    "name": p["name"],
                    "subtotal": sub,
                }
            )
        if not line_details:
            return None, "Chưa chọn số lượng"
        return line_details, None

    def validate_order(
        self, items: list
    ) -> tuple[str | None, str | None, list[dict]]:
        """
        items: [{"id": int, "qty": int}, ...]
        Trả về (summary, None, line_details) hoặc (None, error_message, []).
        """
        line_details, err = self._prepare_order_lines(items)
        if err:
            return None, err, []
        return self._format_summary(line_details), None, line_details

    def persist_order(self, machine_id: int, summary: str, line_details: list[dict]) -> None:
        """Chỉ ghi SQL khi backend=sqlserver; JSON bỏ qua."""
        if self._mode != "sqlserver" or not line_details:
            return
        with self._sql_connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO dbo.orders (machine_id, summary_text)
                OUTPUT INSERTED.id
                VALUES (?, ?)
                """,
                int(machine_id),
                summary or "",
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError("Không lấy được id đơn hàng")
            oid = int(row[0])
            for x in line_details:
                cur.execute(
                    """
                    INSERT INTO dbo.order_items (order_id, product_id, qty, unit_price)
                    VALUES (?, ?, ?, ?)
                    """,
                    oid,
                    int(x["product_id"]),
                    int(x["qty"]),
                    float(x["unit_price"]),
                )
