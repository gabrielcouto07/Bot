# extractor.py
import re

URL_RE = re.compile(r"https?://[^\s)>\]]+", re.IGNORECASE)

def extract_urls_from_text(text: str) -> list[str]:
    if not text:
        return []
    urls = URL_RE.findall(text)
    # limpa pontuação final comum
    cleaned = []
    for u in urls:
        u2 = u.rstrip(".,;:!?)\"]'")
        cleaned.append(u2)
    # unique mantendo ordem
    seen = set()
    out = []
    for u in cleaned:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

def replace_urls_in_text(text: str, mapping: dict[str, str]) -> str:
    if not text or not mapping:
        return text or ""

    def repl(m: re.Match):
        u = m.group(0).rstrip(".,;:!?)\"]'")
        return mapping.get(u, u)

    # substitui por regex (mantém resto do texto)
    return URL_RE.sub(repl, text)