# extractor.py

import re

ML_SEC_RE = re.compile(
    r"(https?://[\w.-]*mercadolivre\.com(?:\.br)?/sec/[A-Za-z0-9]+)",
    re.IGNORECASE,
)

AMAZON_RE = re.compile(
    r"https?://(?:(?:www|m|smile)\.)?(?:amazon\.[a-z.]{2,}|amzn\.to)/[^\s]+",
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
    """Extrai todas URLs do texto"""
    if not text:
        return []
    
    urls = URL_RE.findall(text)
    cleaned: list[str] = []
    
    for u in urls:
        u2 = u.rstrip(".,;:!?)]'\\'\"")
        cleaned.append(u2)
    
    seen = set()
    out: list[str] = []
    
    for u in cleaned:
        if u not in seen:
            seen.add(u)
            out.append(u)
    
    return out


def filter_meli_sec_urls(urls: list[str]) -> list[str]:
    """Filtra apenas URLs do Mercado Livre /sec/"""
    if not urls:
        return []
    
    meli_urls = []
    
    for url in urls:
        if ML_SEC_RE.match(url):
            meli_urls.append(url)
    
    return meli_urls


def replace_urls_in_text(text: str, mapping: dict[str, str]) -> str:
    """Substitui URLs antigas por afiliadas"""
    if not text or not mapping:
        return text or ""
    
    result = text
    
    for old_url, new_url in mapping.items():
        result = result.replace(old_url, new_url)
    
    return result


def process_text_enhancements(text: str) -> str:
    """
    Processa texto para melhorias visuais
    (Por enquanto retorna o texto como está, mas pode adicionar emojis, formatação, etc)
    """
    if not text:
        return text
    
    # Aqui você pode adicionar processamentos extras:
    # - Adicionar emojis
    # - Formatar títulos
    # - Destacar ofertas
    
    # Por enquanto, apenas retorna o texto original
    return text


def format_old_price_with_strikethrough(text: str) -> str:
    """
    Detecta preço antigo (geralmente antes de "por" ou em linhas separadas)
    e adiciona ~ antes e depois para criar efeito riscado no WhatsApp.
    
    Padrões comuns:
    - "R$ 100,00" seguido de "por R$ 80,00"
    - Linha com "De: R$ 100" seguida de "Por: R$ 80"
    - "R$ 100" em uma linha e "R$ 80" na próxima
    """
    if not text:
        return text
    
    # Padrão para detectar preços brasileiros: R$ 123,45 ou R$ 1.234,56
    price_pattern = r'(R\$\s*\d{1,3}(?:\.\d{3})*(?:,\d{2})?)'
    
    # Padrão 1: "De R$ X" ou "de R$ X" (marca como preço antigo)
    text = re.sub(
        r'(\b[Dd]e:?\s*)' + price_pattern,
        r'\1~\2~',
        text
    )
    
    # Padrão 2: Preço seguido de "por" (o primeiro é o antigo)
    # Ex: "R$ 100,00 por R$ 80,00" -> "~R$ 100,00~ por R$ 80,00"
    text = re.sub(
        price_pattern + r'(\s+[Pp]or\s+)' + price_pattern,
        r'~\1~\2\3',
        text
    )
    
    return text

def filter_amazon_urls(urls: list[str]) -> list[str]:
    """Filtra apenas URLs da Amazon"""
    if not urls:
        return []
    
    amazon_urls = []
    
    for url in urls:
        if AMAZON_RE.match(url):
            amazon_urls.append(url)
    
    return amazon_urls