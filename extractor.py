# extractor.py

import re

ML_SEC_RE = re.compile(
    r"(https?://[\w.-]*mercadolivre\.com(?:\.br)?/sec/[A-Za-z0-9]+)",
    re.IGNORECASE,
)

URL_RE = re.compile(r"https?://[^\s)>\]]+", re.IGNORECASE)


def cut_text_after_first_meli_link(text: str) -> str:
    """Corta TUDO após o link ML (remove 'Link do grupo:', '☑️', etc)"""
    if not text:
        return ""

    m = ML_SEC_RE.search(text)
    if not m:
        return text

    link_end = m.end(1)
    result = text[:link_end]

    lines = result.splitlines()
    clean_lines = []
    for ln in lines:
        ln_stripped = ln.strip()
        ln_lower = ln_stripped.lower()
        if (
            ln_lower.startswith("link do grupo")
            or ln_lower.startswith("☑️")
            or "link do grupo" in ln_lower
        ):
            break
        clean_lines.append(ln)

    return "\n".join(clean_lines).strip()


def extract_urls_from_text(text: str) -> list[str]:
    if not text:
        return []
    urls = URL_RE.findall(text)
    cleaned: list[str] = []
    for u in urls:
        u2 = u.rstrip(".,;:!?)]\\'\"")
        cleaned.append(u2)

    seen = set()
    out: list[str] = []
    for u in cleaned:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def replace_urls_in_text(text: str, mapping: dict[str, str]) -> str:
    """Substitui URLs antigas por afiliadas"""
    if not text or not mapping:
        return text or ""
    result = text
    for old_url, new_url in mapping.items():
        result = result.replace(old_url, new_url)
    return result