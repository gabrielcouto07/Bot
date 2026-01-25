# affiliate_multi_platform.py - Suporte para múltiplas plataformas

import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


def generate_amazon_affiliate_link(url: str, tag: str) -> str | None:
    """
    Adiciona tag de afiliado Amazon na URL
    Exemplo: https://amazon.com.br/produto?tag=seu-id-20
    """
    try:
        if not url or not tag:
            return None
        
        # Parse URL
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        # Adiciona/substitui tag de afiliado
        query_params['tag'] = [tag]
        
        # Remove parâmetros desnecessários (opcional)
        # query_params.pop('pd_rd_i', None)
        # query_params.pop('pd_rd_w', None)
        
        # Reconstrói URL
        new_query = urlencode(query_params, doseq=True)
        new_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))
        
        return new_url
        
    except Exception as e:
        print(f"      ✗ Erro ao gerar link Amazon: {e}")
        return None


def generate_aliexpress_affiliate_link(url: str, tag: str) -> str | None:
    """
    Adiciona parâmetros de afiliado AliExpress
    """
    try:
        if not url or not tag:
            return None
        
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        # AliExpress usa 'aff_platform_order_id' ou outros parâmetros
        query_params['aff_trace_key'] = [tag]
        
        new_query = urlencode(query_params, doseq=True)
        new_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))
        
        return new_url
        
    except Exception as e:
        print(f"      ✗ Erro ao gerar link AliExpress: {e}")
        return None


def generate_shopee_affiliate_link(url: str, tag: str) -> str | None:
    """
    Adiciona parâmetros de afiliado Shopee
    """
    try:
        if not url or not tag:
            return None
        
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        # Shopee usa 'af_siteid' ou 'af_sub_siteid'
        query_params['af_siteid'] = [tag]
        
        new_query = urlencode(query_params, doseq=True)
        new_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))
        
        return new_url
        
    except Exception as e:
        print(f"      ✗ Erro ao gerar link Shopee: {e}")
        return None


def generate_generic_affiliate_link(url: str, tag: str, param_name: str = "ref") -> str | None:
    """
    Adiciona tag genérica de afiliado (funciona para várias plataformas)
    """
    try:
        if not url or not tag:
            return None
        
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        query_params[param_name] = [tag]
        
        new_query = urlencode(query_params, doseq=True)
        new_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))
        
        return new_url
        
    except Exception as e:
        print(f"      ✗ Erro ao gerar link genérico: {e}")
        return None
