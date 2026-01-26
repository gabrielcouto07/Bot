# storage.py
import json
from pathlib import Path

STATE_FILE = Path("./state_last_seen.txt")
STATE_FILE_JSON = Path("./state_last_seen.json")


# ========================================
# FUNÇÕES ANTIGAS (compatibilidade)
# ========================================

def load_last_seen() -> str | None:
    """Carrega último ID visto (modo single source - legado)"""
    if not STATE_FILE.exists():
        return None
    value = STATE_FILE.read_text(encoding="utf-8").strip()
    return value if value else None


def save_last_seen(value: str | None) -> None:
    """Salva último ID visto (modo single source - legado)"""
    STATE_FILE.write_text(value or "", encoding="utf-8")


# ========================================
# FUNÇÕES NOVAS (múltiplas fontes)
# ========================================

def load_last_seen_multi() -> dict[str, str]:
    """
    Carrega último ID visto por fonte (canal/grupo)
    Retorna dict: {"Nome do Canal": "hash_id", "Nome do Grupo": "hash_id"}
    """
    if not STATE_FILE_JSON.exists():
        return {}
    
    try:
        data = json.loads(STATE_FILE_JSON.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_last_seen_multi(state: dict[str, str]) -> None:
    """
    Salva último ID visto por fonte
    state: {"Nome do Canal": "hash_id", "Nome do Grupo": "hash_id"}
    """
    STATE_FILE_JSON.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def update_last_seen_for_source(source_name: str, msg_id: str) -> None:
    """Atualiza apenas uma fonte específica"""
    state = load_last_seen_multi()
    state[source_name] = msg_id
    save_last_seen_multi(state)