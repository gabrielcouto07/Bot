# extractor.py

import re

# ========== REGEX PARA DIFERENTES PLATAFORMAS ==========

# Mercado Livre
ML_SEC_RE = re.compile(
    r"(https?://[\w.-]*mercadolivre\.com(?:\.br)?/sec/[A-Za-z0-9]+)",
    re.IGNORECASE,
)
ML_PRODUCT_RE = re.compile(
    r"https?://[\w.-]*mercadolivre\.com(?:\.br)?/[^\s]+",
    re.IGNORECASE,
)

# Amazon
AMAZON_RE = re.compile(
    r"https?://(?:www\.)?amazon\.com(?:\.br)?/[^\s]+",
    re.IGNORECASE,
)

# AliExpress
ALIEXPRESS_RE = re.compile(
    r"https?://(?:[\w.-]*\.)?aliexpress\.com/[^\s]+",
    re.IGNORECASE,
)

# Shopee
SHOPEE_RE = re.compile(
    r"https?://(?:[\w.-]*\.)?shopee\.com(?:\.br)?/[^\s]+",
    re.IGNORECASE,
)

# Magalu
MAGALU_RE = re.compile(
    r"https?://(?:www\.)?magazineluiza\.com\.br/[^\s]+",
    re.IGNORECASE,
)

# Regex genérica para URLs
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

def identify_platform(url: str) -> str | None:
    """Identifica a plataforma da URL"""
    if not url:
        return None
    
    url_lower = url.lower()
    
    if "mercadolivre" in url_lower or "mercadolibre" in url_lower:
        return "mercadolivre"
    elif "amazon.com" in url_lower:
        return "amazon"
    elif "aliexpress" in url_lower:
        return "aliexpress"
    elif "shopee" in url_lower:
        return "shopee"
    elif "magazineluiza" in url_lower or "magalu" in url_lower:
        return "magalu"
    
    return None


def filter_urls_by_platform(urls: list[str]) -> dict[str, list[str]]:
    """Agrupa URLs por plataforma"""
    result = {
        "mercadolivre": [],
        "amazon": [],
        "aliexpress": [],
        "shopee": [],
        "magalu": [],
        "outros": []
    }
    
    for url in urls or []:
        platform = identify_platform(url)
        if platform:
            result[platform].append(url)
        else:
            result["outros"].append(url)
    
    return result


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