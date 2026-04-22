"""
Sistema de deduplicação GLOBAL para evitar envio de mensagens repetidas.
Bloqueia mensagens com o mesmo link de produto em QUALQUER grupo dentro de uma janela de tempo.
"""

import re
import time
import hashlib
from pathlib import Path
from typing import Optional

# Janela de deduplicação em segundos (1 hora)
DEDUP_WINDOW_SECONDS = 1 * 60 * 60  # 3600 segundos = 1 hora

# Arquivo de cache persistente
DEDUP_CACHE_FILE = Path("dedup_cache.txt")

# Regex para extrair identificadores únicos de produtos
ML_PRODUCT_RE = re.compile(r"(MLB-?\d+)", re.IGNORECASE)
ML_SEC_RE = re.compile(r"/sec/([A-Za-z0-9]+)", re.IGNORECASE)
MELI_LA_RE = re.compile(r"meli\.la/([A-Za-z0-9]+)", re.IGNORECASE)
AMAZON_ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})", re.IGNORECASE)
AMAZON_ASIN_RE2 = re.compile(r"/gp/product/([A-Z0-9]{10})", re.IGNORECASE)
AMZN_SHORT_RE = re.compile(r"amzn\.to/([A-Za-z0-9]+)", re.IGNORECASE)


def _extract_product_id(urls: list[str]) -> Optional[str]:
    """
    Extrai um ID único do produto a partir das URLs.
    Prioridade: MLB (Mercado Livre) > ASIN (Amazon) > /sec/ ID > amzn.to short
    """
    for url in urls:
        # Tenta Mercado Livre MLB primeiro (mais confiável)
        m = ML_PRODUCT_RE.search(url)
        if m:
            # Normaliza: remove hífen e uppercase
            return f"ML_{m.group(1).upper().replace('-', '')}"
        
        # Tenta Amazon ASIN
        m = AMAZON_ASIN_RE.search(url) or AMAZON_ASIN_RE2.search(url)
        if m:
            return f"AMAZON_{m.group(1).upper()}"
    
    # Fallback: /sec/ ID do ML (menos ideal mas funciona)
    for url in urls:
        m = ML_SEC_RE.search(url)
        if m:
            return f"MLSEC_{m.group(1).upper()}"
    
    # Fallback: meli.la short code
    for url in urls:
        m = MELI_LA_RE.search(url)
        if m:
            return f"MLSEC_{m.group(1).upper()}"
    
    # Fallback: amzn.to short code
    for url in urls:
        m = AMZN_SHORT_RE.search(url)
        if m:
            return f"AMZN_{m.group(1).upper()}"
    
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


def _load_cache() -> dict[str, float]:
    """
    Carrega cache do disco.
    Formato NOVO (global): {content_hash: timestamp}
    Compatível com formato antigo: {target_group: {content_hash: timestamp}}
    """
    cache: dict[str, float] = {}
    
    if not DEDUP_CACHE_FILE.exists():
        return cache
    
    try:
        with open(DEDUP_CACHE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or "|" not in line:
                    continue
                
                parts = line.split("|")
                
                # Formato NOVO (2 campos): hash|timestamp
                if len(parts) == 2:
                    content_hash = parts[0]
                    try:
                        timestamp = float(parts[1])
                        cache[content_hash] = timestamp
                    except ValueError:
                        continue
                
                # Formato ANTIGO (3 campos): target_group|hash|timestamp
                # Converte para global (ignora target_group)
                elif len(parts) >= 3:
                    content_hash = parts[1]
                    try:
                        timestamp = float(parts[2])
                        # Mantém o mais recente se houver duplicata
                        if content_hash not in cache or cache[content_hash] < timestamp:
                            cache[content_hash] = timestamp
                    except ValueError:
                        continue
                        
    except Exception as e:
        print(f"⚠️ Erro ao carregar cache de dedup: {e}")
    
    return cache


def _save_cache(cache: dict[str, float]):
    """
    Salva cache no disco, removendo entradas expiradas.
    Formato: hash|timestamp
    """
    now = time.time()
    
    try:
        with open(DEDUP_CACHE_FILE, "w", encoding="utf-8") as f:
            for content_hash, timestamp in cache.items():
                # Só salva se ainda estiver válido
                if now - timestamp < DEDUP_WINDOW_SECONDS:
                    f.write(f"{content_hash}|{timestamp}\n")
    except Exception as e:
        print(f"⚠️ Erro ao salvar cache de dedup: {e}")


def is_duplicate(
    target_group: str,  # Mantido por compatibilidade, mas IGNORADO na lógica
    text: str,
    urls: list[str],
    window_seconds: int = DEDUP_WINDOW_SECONDS
) -> bool:
    """
    Verifica se a mensagem é duplicada (já foi enviada recentemente).
    
    🔥 IMPORTANTE: Verifica GLOBALMENTE (todos os grupos).
    Se o mesmo produto foi enviado para QUALQUER grupo na última hora, bloqueia.
    
    Args:
        target_group: Nome do grupo de destino (ignorado - bloqueio é global)
        text: Texto da mensagem
        urls: Lista de URLs na mensagem
        window_seconds: Janela de tempo em segundos (padrão: 1 hora)
    
    Returns:
        True se é duplicada (NÃO deve enviar), False se é nova (pode enviar)
    """
    content_hash = _generate_content_hash(text, urls)
    product_id = _extract_product_id(urls)
    cache = _load_cache()
    now = time.time()
    
    # Verifica se existe no cache GLOBAL
    if content_hash in cache:
        last_sent = cache[content_hash]
        age = now - last_sent
        
        if age < window_seconds:
            remaining = window_seconds - age
            remaining_min = int(remaining / 60)
            age_min = int(age / 60)
            
            if product_id:
                print(f"   🔄 DUPLICADA! Produto {product_id} enviado há {age_min} min.")
            else:
                print(f"   🔄 DUPLICADA! Mesma oferta enviada há {age_min} min.")
            print(f"   🔄 Bloqueio GLOBAL: {remaining_min} min restantes.")
            return True
    
    return False


def mark_as_sent(target_group: str, text: str, urls: list[str]):
    """
    Marca a mensagem como enviada no cache GLOBAL.
    Deve ser chamado APÓS envio bem-sucedido.
    
    Args:
        target_group: Nome do grupo de destino (logado mas bloqueio é global)
        text: Texto da mensagem
        urls: Lista de URLs na mensagem
    """
    content_hash = _generate_content_hash(text, urls)
    cache = _load_cache()
    now = time.time()
    
    cache[content_hash] = now
    _save_cache(cache)
    
    product_id = _extract_product_id(urls)
    window_min = DEDUP_WINDOW_SECONDS // 60
    
    if product_id:
        print(f"   🔒 Cache GLOBAL: {product_id} bloqueado por {window_min} min")
    else:
        print(f"   🔒 Cache GLOBAL: Hash {content_hash[:12]}... bloqueado por {window_min} min")


def get_product_id_from_urls(urls: list[str]) -> Optional[str]:
    """
    Função auxiliar para obter o ID do produto das URLs.
    Útil para logging e debug.
    """
    return _extract_product_id(urls)


def cleanup_expired_cache():
    """
    Remove entradas expiradas do cache.
    Pode ser chamado periodicamente para manter o arquivo limpo.
    """
    cache = _load_cache()
    _save_cache(cache)  # _save_cache já filtra expirados
    print("🧹 Cache de deduplicação limpo")