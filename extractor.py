# extractor.py

import re

ML_SEC_RE = re.compile(
    r"(https?://[\w.-]*mercadolivre\.com(?:\.br)?/sec/[A-Za-z0-9]+)",
    re.IGNORECASE,
)

URL_RE = re.compile(r"https?://[^\s)>\]]+", re.IGNORECASE)

def cut_text_after_first_meli_link(text: str) -> str:
    if not text:
        return ""
    m = ML_SEC_RE.search(text)
    if not m:
        return text.strip()
    end = m.end(1)
    return text[:end].rstrip()

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
    if not text or not mapping:
        return text or ""

    def repl(m: re.Match):
        original = m.group(0)
        url_clean = original.rstrip(".,;:!?)]\\'\"")
        punct = original[len(url_clean):]
        new_url = mapping.get(url_clean, url_clean)
        return new_url + punct

    return URL_RE.sub(repl, text)