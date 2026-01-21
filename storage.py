# storage.py
from pathlib import Path

STATE_FILE = Path("./state_last_seen.txt")


def load_last_seen() -> str | None:
    if not STATE_FILE.exists():
        return None
    value = STATE_FILE.read_text(encoding="utf-8").strip()
    return value if value else None


def save_last_seen(value: str | None) -> None:
    STATE_FILE.write_text(value or "", encoding="utf-8")