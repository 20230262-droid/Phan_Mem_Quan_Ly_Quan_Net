import json
import os
import threading
from datetime import datetime


class PCHistoryModel:
    """Lưu lịch sử chat/order theo PC vào file JSON để xem lại sau khi restart."""

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
        entries = data.get("entries") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            self._entries = []
            return
        out = []
        for e in entries:
            if not isinstance(e, dict):
                continue
            try:
                pc_index = int(e.get("pc_index", 0))
            except (TypeError, ValueError):
                continue
            if pc_index <= 0:
                continue
            out.append(
                {
                    "pc_index": pc_index,
                    "kind": str(e.get("kind") or "chat"),
                    "who": str(e.get("who") or ""),
                    "text": str(e.get("text") or ""),
                    "username": str(e.get("username") or ""),
                    "created_at": str(e.get("created_at") or ""),
                }
            )
        self._entries = out

    def _save_unlocked(self):
        parent = os.path.dirname(self._path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        payload = {"version": 1, "entries": self._entries}
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def append(
        self,
        pc_index: int,
        kind: str,
        who: str,
        text: str,
        username: str = "",
    ):
        if not text:
            return
        try:
            pid = int(pc_index)
        except (TypeError, ValueError):
            return
        if pid <= 0:
            return
        k = "order" if (kind or "").lower() == "order" else "chat"
        item = {
            "pc_index": pid,
            "kind": k,
            "who": str(who or ""),
            "text": str(text or ""),
            "username": str(username or ""),
            "created_at": datetime.now().isoformat(),
        }
        with self._lock:
            self._entries.append(item)
            self._save_unlocked()

    def list_pc_indices(self) -> list[int]:
        with self._lock:
            vals = {int(e.get("pc_index", 0)) for e in self._entries}
        return sorted(x for x in vals if x > 0)

    def get_lines(self, pc_index: int, kind: str | None = None) -> list[tuple[str, str]]:
        try:
            pid = int(pc_index)
        except (TypeError, ValueError):
            return []
        if pid <= 0:
            return []
        wanted = None if kind is None else ("order" if kind == "order" else "chat")
        with self._lock:
            rows = [e for e in self._entries if int(e.get("pc_index", 0)) == pid]
        out: list[tuple[str, str]] = []
        for e in rows:
            k = "order" if str(e.get("kind") or "").lower() == "order" else "chat"
            if wanted and k != wanted:
                continue
            who = str(e.get("who") or "")
            text = str(e.get("text") or "")
            ts = str(e.get("created_at") or "")
            prefix = f"[{ts}] " if ts else ""
            out.append((who, f"{prefix}{text}"))
        return out

    def clear_pc(self, pc_index: int) -> int:
        """Xóa toàn bộ lịch sử của một PC. Trả về số bản ghi đã xóa."""
        try:
            pid = int(pc_index)
        except (TypeError, ValueError):
            return 0
        if pid <= 0:
            return 0
        with self._lock:
            before = len(self._entries)
            self._entries = [e for e in self._entries if int(e.get("pc_index", 0)) != pid]
            deleted = before - len(self._entries)
            if deleted > 0:
                self._save_unlocked()
            return deleted

    def clear_all(self) -> int:
        """Xóa toàn bộ lịch sử. Trả về số bản ghi đã xóa."""
        with self._lock:
            deleted = len(self._entries)
            if deleted == 0:
                return 0
            self._entries = []
            self._save_unlocked()
            return deleted
