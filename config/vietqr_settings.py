"""Đọc cấu hình VietQR và tạo URL ảnh mã QR (img.vietqr.io)."""

import json
import os
import urllib.parse

from config.database import get_vietqr_json_path


def load_vietqr_config():
    path = get_vietqr_json_path()
    if not os.path.isfile(path):
        return {
            "bank_bin": "",
            "account_no": "",
            "account_name": "",
            "template": "compact2",
        }
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {
            "bank_bin": "",
            "account_no": "",
            "account_name": "",
            "template": "compact2",
        }
    if not isinstance(data, dict):
        data = {}
    return {
        "bank_bin": str(data.get("bank_bin") or "").strip(),
        "account_no": str(data.get("account_no") or "").strip(),
        "account_name": str(data.get("account_name") or "").strip(),
        "template": str(data.get("template") or "compact2").strip() or "compact2",
    }


def is_vietqr_configured() -> bool:
    c = load_vietqr_config()
    return bool(c["bank_bin"] and c["account_no"])


def build_vietqr_image_url(
    amount_vnd: int,
    add_info: str = "",
    *,
    bank_bin: str | None = None,
    account_no: str | None = None,
    account_name: str | None = None,
    template: str | None = None,
) -> str:
    """
    URL ảnh VietQR (dịch vụ công khai). amount_vnd: số nguyên VNĐ; add_info: nội dung CK (ASCII an toàn hơn).
    """
    c = load_vietqr_config()
    bid = (bank_bin if bank_bin is not None else c["bank_bin"]) or ""
    acc = (account_no if account_no is not None else c["account_no"]) or ""
    name = (account_name if account_name is not None else c["account_name"]) or ""
    tpl = (template if template is not None else c["template"]) or "compact2"
    if not bid or not acc:
        return ""
    amt = max(0, int(amount_vnd))
    info = (add_info or "").strip()
    if len(info) > 50:
        info = info[:47] + "..."
    q = {}
    if amt > 0:
        q["amount"] = str(amt)
    if info:
        q["addInfo"] = info
    if name:
        q["accountName"] = name
    qs = urllib.parse.urlencode(q) if q else ""
    base = f"https://img.vietqr.io/image/{urllib.parse.quote(bid, safe='')}-{urllib.parse.quote(acc, safe='')}-{urllib.parse.quote(tpl, safe='')}.png"
    return f"{base}?{qs}" if qs else base
