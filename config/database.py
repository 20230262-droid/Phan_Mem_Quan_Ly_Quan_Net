import json
import os

_CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_CONFIG_DIR)
_DATABASE_JSON = os.path.join(_CONFIG_DIR, "database.json")


def _strip(s):
    if s is None:
        return ""
    return str(s).strip()


def _load_file_config():
    if not os.path.isfile(_DATABASE_JSON):
        return {}
    with open(_DATABASE_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def get_users_json_path():
    """Đường dẫn file JSON người dùng (tương đối theo thư mục gốc project hoặc đường dẫn tuyệt đối)."""
    data = _load_file_config()
    p = _strip(data.get("users_json")) or "users.json"
    if os.path.isabs(p):
        return p
    return os.path.join(_PROJECT_ROOT, p)


def get_menu_products_json_path():
    """File JSON danh mục sản phẩm order (thêm / sửa / xóa từ máy chủ)."""
    data = _load_file_config()
    p = _strip(data.get("menu_products_json")) or "menu_products.json"
    if os.path.isabs(p):
        return p
    return os.path.join(_PROJECT_ROOT, p)


def get_pc_history_json_path():
    """File JSON lưu lịch sử chat/order theo từng PC."""
    data = _load_file_config()
    p = _strip(data.get("pc_history_json")) or "pc_history.json"
    if os.path.isabs(p):
        return p
    return os.path.join(_PROJECT_ROOT, p)


def get_revenue_json_path():
    """File JSON lưu doanh thu để thống kê."""
    data = _load_file_config()
    p = _strip(data.get("revenue_json")) or "revenue.json"
    if os.path.isabs(p):
        return p
    return os.path.join(_PROJECT_ROOT, p)


def get_vietqr_json_path():
    """File cấu hình VietQR (mã ngân hàng, STK, tên chủ TK)."""
    data = _load_file_config()
    p = _strip(data.get("vietqr_json")) or os.path.join(_CONFIG_DIR, "vietqr.json")
    if os.path.isabs(p):
        return p
    return os.path.join(_PROJECT_ROOT, p)


def resolve_storage_backend():
    """
    json | sqlserver
    Ưu tiên: QUAN_NET_DB=json|file -> json;
    SQLSERVER_SERVER (env) -> sqlserver;
    database.json backend=sqlserver và có server -> sqlserver;
    còn lại -> json.
    """
    qn = _strip(os.environ.get("QUAN_NET_DB")).lower()
    if qn in ("json", "file"):
        return "json"
    if _strip(os.environ.get("SQLSERVER_SERVER")):
        return "sqlserver"
    data = _load_file_config()
    back = _strip(data.get("backend")).lower()
    if back not in ("sqlserver", "sql", "mssql"):
        return "json"
    sql = data.get("sqlserver") or {}
    if _strip(sql.get("server")):
        return "sqlserver"
    return "json"


def _merged_sqlserver_settings():
    """Gộp database.json và biến môi trường (env không rỗng sẽ ghi đè)."""
    data = _load_file_config()
    sql = dict(data.get("sqlserver") or {})

    def pick(env_key, file_key, default=""):
        ev = _strip(os.environ.get(env_key))
        if ev:
            return ev
        return _strip(sql.get(file_key)) or default

    server = pick("SQLSERVER_SERVER", "server")
    database = pick("SQLSERVER_DATABASE", "database", "QuanNet")
    user = pick("SQLSERVER_USER", "user")
    password = pick("SQLSERVER_PASSWORD", "password")
    driver = pick("SQLSERVER_ODBC_DRIVER", "odbc_driver", "ODBC Driver 18 for SQL Server")

    trust = sql.get("trust_server_certificate", True)
    env_trust = _strip(os.environ.get("SQLSERVER_TRUST_SERVER_CERTIFICATE")).lower()
    if env_trust in ("0", "false", "no"):
        trust = False
    if env_trust in ("1", "true", "yes"):
        trust = True

    return {
        "server": server,
        "database": database,
        "user": user,
        "password": password,
        "odbc_driver": driver,
        "trust_server_certificate": bool(trust),
    }


def build_sqlserver_connection_string():
    s = _merged_sqlserver_settings()
    if not s["server"]:
        raise ValueError("Thiếu SQL Server host/instance (config/sqlserver.server hoặc SQLSERVER_SERVER).")
    parts = [
        f"DRIVER={{{s['odbc_driver']}}}",
        f"SERVER={s['server']}",
        f"DATABASE={s['database']}",
    ]
    if s["trust_server_certificate"]:
        parts.append("TrustServerCertificate=yes")
    if _strip(s["user"]):
        parts.append(f"UID={s['user']}")
        parts.append(f"PWD={s['password']}")
    else:
        parts.append("Trusted_Connection=yes")
    return ";".join(parts) + ";"
