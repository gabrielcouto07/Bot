"""
Sistema de deduplicação para evitar envio de mensagens repetidas.
Bloqueia mensagens com o mesmo link de produto dentro de uma janela de tempo.
"""

import re
import time
import hashlib
from pathlib import Path
from typing import Optional

# Janela de deduplicação em segundos (3 horas)
DEDUP_WINDOW_SECONDS = 3 * 60 * 60  # 10800 segundos

# Arquivo de cache persistente
DEDUP_CACHE_FILE = Path("dedup_cache.txt")

# Regex para extrair identificadores únicos de produtos
ML_PRODUCT_RE = re.compile(r"(MLB-?\d+)", re.IGNORECASE)
AMAZON_ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})", re.IGNORECASE)
AMAZON_ASIN_RE2 = re.compile(r"/gp/product/([A-Z0-9]{10})", re.IGNORECASE)


def _extract_product_id(urls: list[str]) -> Optional[str]:
    """
    Extrai um ID único do produto a partir das URLs.
    Prioridade: MLB (Mercado Livre) > ASIN (Amazon)
    """
    for url in urls:
        # Tenta Mercado Livre primeiro
        m = ML_PRODUCT_RE.search(url)
        if m:
            # Normaliza: remove hífen e uppercase
            return f"ML_{m.group(1).upper().replace('-', '')}"
        
        # Tenta Amazon ASIN
        m = AMAZON_ASIN_RE.search(url) or AMAZON_ASIN_RE2.search(url)
        if m:
            return f"AMAZON_{m.group(1).upper()}"
    
    return None


def _generate_content_hash(text: str, urls: list[str]) -> str:
    """
    Gera hash baseado no ID do produto (se existir) ou no conteúdo.
    """
    product_id = _extract_product_id(urls)
    
    if product_id:
        # Se tem ID de produto, usa ele como base (mais confiável)
        return hashlib.sha256(product_id.encode()).hexdigest()[:32]
    
    # Fallback: hash das URLs ordenadas
    if urls:
        sorted_urls = sorted(set(urls))
        return hashlib.sha256("|".join(sorted_urls).encode()).hexdigest()[:32]
    
    # Último recurso: hash do texto (menos confiável para variações)
    return hashlib.sha256(text.encode()).hexdigest()[:32]


def _load_cache() -> dict[str, dict]:
    """
    Carrega cache do disco.
    Formato: {target_group: {content_hash: timestamp}}
    """
    cache: dict[str, dict] = {}
    
    if not DEDUP_CACHE_FILE.exists():
        return cache
    
    try:
        with open(DEDUP_CACHE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or "|" not in line:
                    continue
                
                parts = line.split("|")
                if len(parts) >= 3:
                    target_group = parts[0]
                    content_hash = parts[1]
                    timestamp = float(parts[2])
                    
                    if target_group not in cache:
                        cache[target_group] = {}
                    cache[target_group][content_hash] = timestamp
    except Exception as e:
        print(f"⚠️ Erro ao carregar cache de dedup: {e}")
    
    return cache


def _save_cache(cache: dict[str, dict]):
    """
    Salva cache no disco, removendo entradas expiradas.
    """
    now = time.time()
    
    try:
        with open(DEDUP_CACHE_FILE, "w", encoding="utf-8") as f:
            for target_group, hashes in cache.items():
                for content_hash, timestamp in hashes.items():
                    # Só salva se ainda estiver válido
                    if now - timestamp < DEDUP_WINDOW_SECONDS:
                        f.write(f"{target_group}|{content_hash}|{timestamp}\n")
    except Exception as e:
        print(f"⚠️ Erro ao salvar cache de dedup: {e}")


def is_duplicate(
    target_group: str,
    text: str,
    urls: list[str],
    window_seconds: int = DEDUP_WINDOW_SECONDS
) -> bool:
    """
    Verifica se a mensagem é duplicada (já foi enviada recentemente).
    
    Args:
        target_group: Nome do grupo de destino
        text: Texto da mensagem
        urls: Lista de URLs na mensagem
        window_seconds: Janela de tempo em segundos (padrão: 3 horas)
    
    Returns:
        True se é duplicada (NÃO deve enviar), False se é nova (pode enviar)
    """
    content_hash = _generate_content_hash(text, urls)
    cache = _load_cache()
    now = time.time()
    
    # Verifica se existe no cache do grupo de destino
    if target_group in cache:
        if content_hash in cache[target_group]:
            last_sent = cache[target_group][content_hash]
            age = now - last_sent
            
            if age < window_seconds:
                remaining = window_seconds - age
                remaining_min = int(remaining / 60)
                print(f"   🔄 DUPLICADA! Mesma oferta enviada há {int(age/60)} min. Bloqueio: {remaining_min} min restantes.")
                return True
    
    return False


def mark_as_sent(target_group: str, text: str, urls: list[str]):
    """
    Marca a mensagem como enviada no cache.
    Deve ser chamado APÓS envio bem-sucedido.
    
    Args:
        target_group: Nome do grupo de destino
        text: Texto da mensagem
        urls: Lista de URLs na mensagem
    """
    content_hash = _generate_content_hash(text, urls)
    cache = _load_cache()
    now = time.time()
    
    if target_group not in cache:
        cache[target_group] = {}
    
    cache[target_group][content_hash] = now
    _save_cache(cache)
    
    product_id = _extract_product_id(urls)
    if product_id:
        print(f"   🔒 Cache: {product_id} bloqueado por 3h para {target_group}")
    else:
        print(f"   🔒 Cache: Hash {content_hash[:12]}... bloqueado por 3h")


def cleanup_expired_cache():
    """
    Remove entradas expiradas do cache.
    Pode ser chamado periodicamente para manter o arquivo limpo.
    """
    cache = _load_cache()
    _save_cache(cache)  # _save_cache já filtra expirados
    print("🧹 Cache de deduplicação limpo")