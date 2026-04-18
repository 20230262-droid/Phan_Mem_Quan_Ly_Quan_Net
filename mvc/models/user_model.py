import json
import os
from contextlib import contextmanager
from datetime import datetime

from config.database import (
    build_sqlserver_connection_string,
    get_users_json_path,
    resolve_storage_backend,
)

try:
    import pyodbc
except ImportError:
    pyodbc = None


class UserModel:
    """Lưu người dùng: SQL Server hoặc users.json theo config/config/database.json (và biến môi trường ghi đè)."""

    def __init__(self, data_file=None):
        self._mode = resolve_storage_backend()
        if self._mode == "json":
            self.data_file = data_file or get_users_json_path()
            self.users = self.load_users()
            self._conn_str = None
        else:
            if pyodbc is None:
                raise RuntimeError("Cần cài pyodbc để dùng SQL Server: pip install pyodbc")
            self.data_file = data_file or get_users_json_path()
            self.users = {}
            self._conn_str = build_sqlserver_connection_string()
            self._ensure_sql_connection()
            self._import_users_json_if_sql_empty()

    def _import_users_json_if_sql_empty(self):
        """Một lần: nếu bảng SQL trống nhưng còn users.json thì copy tài khoản + lịch sử vào SQL."""
        path = get_users_json_path()
        if not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(data, list) or not data:
            return
        with self._sql_connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM dbo.users")
            if cur.fetchone()[0] > 0:
                return
        for u in data:
            if not isinstance(u, dict):
                continue
            username = u.get("username")
            if not username:
                continue
            password = u.get("password", "")
            balance = float(u.get("balance", 0) or 0)
            user_type = u.get("type", "normal") or "normal"
            try:
                with self._sql_connect() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO dbo.users (username, password, balance, user_type) VALUES (?, ?, ?, ?)",
                        username,
                        password,
                        balance,
                        user_type,
                    )
            except pyodbc.IntegrityError:
                continue
            for h in u.get("history") or []:
                if not isinstance(h, dict):
                    continue
                mid = h.get("machine_id")
                dur = h.get("duration")
                if mid is None or dur is None:
                    continue
                ts_raw = h.get("timestamp")
                try:
                    if isinstance(ts_raw, str) and ts_raw:
                        recorded = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                    else:
                        recorded = datetime.now()
                except ValueError:
                    recorded = datetime.now()
                with self._sql_connect() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        """
                        INSERT INTO dbo.usage_history (username, machine_id, duration, recorded_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        username,
                        int(mid),
                        float(dur),
                        recorded,
                    )

    def _ensure_sql_connection(self):
        try:
            with pyodbc.connect(self._conn_str, timeout=15) as conn:
                conn.cursor().execute("SELECT 1")
        except Exception as e:
            raise RuntimeError(
                "Không kết nối được SQL Server. Kiểm tra config/database.json (sqlserver), "
                "ODBC Driver 17/18, và đã chạy sql/init_sqlserver.sql trên database."
            ) from e

    @contextmanager
    def _sql_connect(self):
        conn = pyodbc.connect(self._conn_str, timeout=15)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def load_users(self):
        if self._mode != "json":
            return {}
        if os.path.exists(self.data_file):
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {user["username"]: user for user in data}
        return {}

    def save_users(self):
        if self._mode != "json":
            return
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(list(self.users.values()), f, ensure_ascii=False, indent=4)

    def register(self, username, password, user_type="normal", balance=0):
        ut = user_type if user_type in ("normal", "vip") else "normal"
        bal = max(0.0, float(balance or 0))
        if self._mode == "json":
            if username in self.users:
                return False, "Tên đăng nhập đã tồn tại"
            self.users[username] = {
                "username": username,
                "password": password,
                "balance": bal,
                "type": ut,
                "history": [],
            }
            self.save_users()
            return True, "Đăng ký thành công"
        try:
            with self._sql_connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO dbo.users (username, password, balance, user_type) VALUES (?, ?, ?, ?)",
                    username,
                    password,
                    bal,
                    ut,
                )
        except pyodbc.IntegrityError:
            return False, "Tên đăng nhập đã tồn tại"
        return True, "Đăng ký thành công"

    def list_users(self, search=""):
        """Danh sách tài khoản (không có mật khẩu). search: lọc theo tên, không phân biệt hoa thường."""
        q_raw = (search or "").strip()
        q = q_raw.lower()
        if self._mode == "json":
            rows = []
            for name in sorted(self.users.keys(), key=lambda x: x.lower()):
                if q and q not in name.lower():
                    continue
                d = self.users[name]
                rows.append(
                    {
                        "username": name,
                        "balance": float(d.get("balance", 0) or 0),
                        "type": d.get("type", "normal"),
                    }
                )
            return rows

        def _esc_like(s: str) -> str:
            return s.replace("[", "[[]").replace("%", "[%]").replace("_", "[_]")

        with self._sql_connect() as conn:
            cur = conn.cursor()
            if q_raw:
                pat = f"%{_esc_like(q_raw)}%"
                cur.execute(
                    "SELECT username, balance, user_type FROM dbo.users WHERE LOWER(username) LIKE LOWER(?) ORDER BY username",
                    pat,
                )
            else:
                cur.execute(
                    "SELECT username, balance, user_type FROM dbo.users ORDER BY username"
                )
            return [
                {"username": r[0], "balance": float(r[1]), "type": r[2]}
                for r in cur.fetchall()
            ]

    def delete_user(self, username):
        if not username or not str(username).strip():
            return False, "Thiếu tên đăng nhập"
        username = str(username).strip()
        if self._mode == "json":
            if username not in self.users:
                return False, "Không tồn tại"
            del self.users[username]
            self.save_users()
            return True, "Đã xóa tài khoản"
        with self._sql_connect() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM dbo.users WHERE username = ?", username)
            if cur.rowcount == 0:
                return False, "Không tồn tại"
        return True, "Đã xóa tài khoản"

    def update_user(self, username, password=None, balance=None, user_type=None):
        """Cập nhật tài khoản. password=None: giữ nguyên mật khẩu."""
        if not username or not str(username).strip():
            return False, "Thiếu tên đăng nhập"
        username = str(username).strip()
        if self._mode == "json":
            if username not in self.users:
                return False, "Không tồn tại"
            u = self.users[username]
            if password is not None:
                u["password"] = password
            if balance is not None:
                u["balance"] = max(0.0, float(balance))
            if user_type is not None:
                if user_type in ("normal", "vip"):
                    u["type"] = user_type
            self.save_users()
            return True, "Đã cập nhật"
        sets = []
        params = []
        if password is not None:
            sets.append("password = ?")
            params.append(password)
        if balance is not None:
            sets.append("balance = ?")
            params.append(max(0.0, float(balance)))
        if user_type is not None and user_type in ("normal", "vip"):
            sets.append("user_type = ?")
            params.append(user_type)
        if not sets:
            return True, "Không có thay đổi"
        params.append(username)
        sql = "UPDATE dbo.users SET " + ", ".join(sets) + " WHERE username = ?"
        with self._sql_connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            if cur.rowcount == 0:
                cur.execute("SELECT 1 FROM dbo.users WHERE username = ?", username)
                if not cur.fetchone():
                    return False, "Không tồn tại"
        return True, "Đã cập nhật"

    def login(self, username, password):
        if self._mode == "json":
            if username not in self.users or self.users[username]["password"] != password:
                return False, "Sai tên đăng nhập hoặc mật khẩu"
            return True, self.users[username]
        with self._sql_connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT username, password, balance, user_type FROM dbo.users WHERE username = ?",
                username,
            )
            row = cur.fetchone()
            if not row or row[1] != password:
                return False, "Sai tên đăng nhập hoặc mật khẩu"
            cur.execute(
                """
                SELECT machine_id, duration, recorded_at
                FROM dbo.usage_history
                WHERE username = ?
                ORDER BY id
                """,
                username,
            )
            history = []
            for h in cur.fetchall():
                ts = h[2]
                if hasattr(ts, "isoformat"):
                    ts = ts.isoformat()
                history.append({"machine_id": h[0], "duration": float(h[1]), "timestamp": ts})
            user = {
                "username": row[0],
                "password": row[1],
                "balance": float(row[2]),
                "type": row[3],
                "history": history,
            }
            return True, user

    def top_up(self, username, amount):
        if self._mode == "json":
            if username not in self.users:
                return False, "Người dùng không tồn tại"
            self.users[username]["balance"] += amount
            if self.users[username]["balance"] > 100000:
                self.users[username]["type"] = "vip"
            else:
                self.users[username]["type"] = "normal"
            self.save_users()
            return True, f"Nạp tiền thành công. Số dư: {self.users[username]['balance']}"
        with self._sql_connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT balance FROM dbo.users WHERE username = ?", username)
            row = cur.fetchone()
            if not row:
                return False, "Người dùng không tồn tại"
            new_bal = float(row[0]) + float(amount)
            utype = "vip" if new_bal > 100000 else "normal"
            cur.execute(
                "UPDATE dbo.users SET balance = ?, user_type = ? WHERE username = ?",
                new_bal,
                utype,
                username,
            )
            return True, f"Nạp tiền thành công. Số dư: {new_bal}"

    def add_usage_history(self, username, machine_id, duration):
        if self._mode == "json":
            if username in self.users:
                self.users[username]["history"].append(
                    {
                        "machine_id": machine_id,
                        "duration": duration,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                self.save_users()
            return
        with self._sql_connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM dbo.users WHERE username = ?", username)
            if not cur.fetchone():
                return
            cur.execute(
                """
                INSERT INTO dbo.usage_history (username, machine_id, duration, recorded_at)
                VALUES (?, ?, ?, ?)
                """,
                username,
                machine_id,
                float(duration),
                datetime.now(),
            )

    def try_pay_order(self, username: str, amount_vnd: float) -> tuple[bool, str, float]:
        """
        Trừ số dư khi đặt món. Trả về (ok, lỗi hoặc rỗng, số_dư_sau_khi_trừ hoặc số_dư_hiện_tại_khi_lỗi).
        """
        if not username or not str(username).strip():
            return False, "Thiếu tài khoản", 0.0
        username = str(username).strip()
        try:
            amt = float(amount_vnd)
        except (TypeError, ValueError):
            return False, "Số tiền đơn không hợp lệ", 0.0
        if amt <= 0:
            info = self.get_user(username)
            if not info:
                return False, "Không tìm thấy tài khoản", 0.0
            return True, "", float(info.get("balance", 0) or 0)

        if self._mode == "json":
            if username not in self.users:
                return False, "Không tìm thấy tài khoản", 0.0
            u = self.users[username]
            bal = float(u.get("balance", 0) or 0)
            if bal < amt:
                return (
                    False,
                    f"Số dư không đủ (còn {bal:,.0f} đ). Vui lòng nạp tiền tại quầy.",
                    bal,
                )
            u["balance"] = bal - amt
            u["type"] = "vip" if u["balance"] > 100000 else "normal"
            self.save_users()
            return True, "", float(u["balance"])

        with self._sql_connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE dbo.users SET balance = balance - ? WHERE username = ? AND balance >= ?",
                amt,
                username,
                amt,
            )
            if cur.rowcount == 0:
                cur.execute("SELECT balance FROM dbo.users WHERE username = ?", username)
                row = cur.fetchone()
                if not row:
                    return False, "Không tìm thấy tài khoản", 0.0
                bal = float(row[0])
                return (
                    False,
                    f"Số dư không đủ (còn {bal:,.0f} đ). Vui lòng nạp tiền tại quầy.",
                    bal,
                )
            cur.execute("SELECT balance FROM dbo.users WHERE username = ?", username)
            new_bal = float(cur.fetchone()[0])
            ut = "vip" if new_bal > 100000 else "normal"
            cur.execute(
                "UPDATE dbo.users SET user_type = ? WHERE username = ?",
                ut,
                username,
            )
            return True, "", new_bal

    def refund_order_payment(self, username: str, amount_vnd: float) -> None:
        """Hoàn tiền khi đã trừ ví nhưng lưu đơn thất bại (nội bộ server)."""
        if not username or not str(username).strip():
            return
        username = str(username).strip()
        try:
            amt = float(amount_vnd)
        except (TypeError, ValueError):
            return
        if amt <= 0:
            return
        if self._mode == "json":
            if username not in self.users:
                return
            u = self.users[username]
            u["balance"] = float(u.get("balance", 0) or 0) + amt
            u["type"] = "vip" if u["balance"] > 100000 else "normal"
            self.save_users()
            return
        with self._sql_connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE dbo.users SET balance = balance + ? WHERE username = ?",
                amt,
                username,
            )
            cur.execute("SELECT balance FROM dbo.users WHERE username = ?", username)
            row = cur.fetchone()
            if not row:
                return
            new_bal = float(row[0])
            ut = "vip" if new_bal > 100000 else "normal"
            cur.execute(
                "UPDATE dbo.users SET user_type = ? WHERE username = ?",
                ut,
                username,
            )

    def get_user(self, username):
        if self._mode == "json":
            return self.users.get(username)
        with self._sql_connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT username, password, balance, user_type FROM dbo.users WHERE username = ?",
                username,
            )
            row = cur.fetchone()
            if not row:
                return None
            cur.execute(
                """
                SELECT machine_id, duration, recorded_at
                FROM dbo.usage_history
                WHERE username = ?
                ORDER BY id
                """,
                username,
            )
            history = []
            for h in cur.fetchall():
                ts = h[2]
                if hasattr(ts, "isoformat"):
                    ts = ts.isoformat()
                history.append({"machine_id": h[0], "duration": float(h[1]), "timestamp": ts})
            return {
                "username": row[0],
                "password": row[1],
                "balance": float(row[2]),
                "type": row[3],
                "history": history,
            }
