import json
import os
import threading
import calendar
from datetime import datetime, timedelta


class RevenueModel:
    """Lưu giao dịch doanh thu và tổng hợp theo ngày/tuần/tháng/năm."""

    def __init__(self, path: str):
        self._path = path
        self._lock = threading.Lock()
        self._entries: list[dict] = []
        self._load()

    def _load(self):
        if not os.path.isfile(self._path):
            self._entries = []
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            self._entries = []
            return
        rows = data.get("entries") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            self._entries = []
            return
        out = []
        for e in rows:
            if not isinstance(e, dict):
                continue
            out.append(
                {
                    "ts": str(e.get("ts") or ""),
                    "kind": str(e.get("kind") or ""),
                    "amount_vnd": float(e.get("amount_vnd", 0) or 0),
                    "pc_index": int(e.get("pc_index", 0) or 0),
                    "username": str(e.get("username") or ""),
                    "meta": str(e.get("meta") or ""),
                }
            )
        self._entries = out

    def _save_unlocked(self):
        parent = os.path.dirname(self._path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "entries": self._entries}, f, ensure_ascii=False, indent=2)

    def append(self, kind: str, amount_vnd: float, pc_index: int = 0, username: str = "", meta: str = ""):
        try:
            amt = float(amount_vnd)
        except (TypeError, ValueError):
            return
        if amt <= 0:
            return
        with self._lock:
            self._entries.append(
                {
                    "ts": datetime.now().isoformat(),
                    "kind": "order" if kind == "order" else "usage",
                    "amount_vnd": amt,
                    "pc_index": int(pc_index or 0),
                    "username": str(username or ""),
                    "meta": str(meta or ""),
                }
            )
            self._save_unlocked()

    @staticmethod
    def _period_start(now: datetime, period: str) -> datetime:
        p = (period or "").lower()
        if p == "day":
            return datetime(now.year, now.month, now.day)
        if p == "week":
            d = now - timedelta(days=now.weekday())
            return datetime(d.year, d.month, d.day)
        if p == "month":
            return datetime(now.year, now.month, 1)
        if p == "year":
            return datetime(now.year, 1, 1)
        return datetime.min

    def summarize(self, period: str) -> dict:
        now = datetime.now()
        start = self._period_start(now, period)
        usage = 0.0
        order = 0.0
        count = 0
        labels, total_series = self._build_period_buckets(now, period)
        with self._lock:
            rows = list(self._entries)
        for e in rows:
            ts_raw = str(e.get("ts") or "")
            try:
                ts = datetime.fromisoformat(ts_raw)
            except ValueError:
                continue
            if ts < start:
                continue
            amt = float(e.get("amount_vnd", 0) or 0)
            if amt <= 0:
                continue
            count += 1
            if str(e.get("kind") or "") == "order":
                order += amt
            else:
                usage += amt
            idx = self._bucket_index(ts, now, period)
            if idx is not None and 0 <= idx < len(total_series):
                total_series[idx] += amt
        return {
            "period": period,
            "start": start.isoformat(),
            "end": now.isoformat(),
            "usage_vnd": int(usage),
            "order_vnd": int(order),
            "total_vnd": int(usage + order),
            "transactions": count,
            "labels": labels,
            "series_total_vnd": [int(x) for x in total_series],
        }

    @staticmethod
    def _build_period_buckets(now: datetime, period: str) -> tuple[list[str], list[float]]:
        p = (period or "").lower()
        if p == "day":
            labels = [f"{h:02d}" for h in range(24)]
        elif p == "week":
            labels = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
        elif p == "month":
            days = calendar.monthrange(now.year, now.month)[1]
            labels = [str(d) for d in range(1, days + 1)]
        elif p == "year":
            labels = [f"Th{m}" for m in range(1, 13)]
        else:
            labels = []
        return labels, [0.0 for _ in labels]

    @staticmethod
    def _bucket_index(ts: datetime, now: datetime, period: str) -> int | None:
        p = (period or "").lower()
        if p == "day":
            if ts.date() != now.date():
                return None
            return ts.hour
        if p == "week":
            monday = (now - timedelta(days=now.weekday())).date()
            sunday = monday + timedelta(days=6)
            if ts.date() < monday or ts.date() > sunday:
                return None
            return ts.weekday()
        if p == "month":
            if ts.year != now.year or ts.month != now.month:
                return None
            return ts.day - 1
        if p == "year":
            if ts.year != now.year:
                return None
            return ts.month - 1
        return None
