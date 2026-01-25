# affiliate.py - VERSÃO CORRIGIDA COM LOCK

import asyncio
import json
import re
from pathlib import Path

from playwright.async_api import TimeoutError as PWTimeout

API_CREATE_LINK = (
    "https://www.mercadolivre.com.br/affiliate-program/api/v2/stripe/user/links"
)

ML_SEC_RE = re.compile(
    r"https?://[\w.-]*mercadolivre\.com(?:\.br)?/sec/[A-Za-z0-9]+",
    re.IGNORECASE,
)

# 🔥 FIX: Cache de CSRF com Lock para evitar race condition
_CACHED_CSRF: str | None = None
_CSRF_LOCK = asyncio.Lock()


def _is_sec(url: str) -> bool:
    return bool(ML_SEC_RE.search((url or "").strip()))


def _is_product_page(url: str) -> bool:
    url_lower = (url or "").lower()
    has_mlb = bool(re.search(r"mlb\d+", url_lower, re.IGNORECASE))
    is_not_sec = "/sec/" not in url_lower
    is_not_review = (
        "/social/" not in url_lower and "/minutoreview" not in url_lower
    )
    return has_mlb and is_not_sec and is_not_review


async def _click_ir_para_produto(page) -> bool:
    """Clica no botão 'Ir para produto' em páginas minutoreview"""
    candidates = [
        page.get_by_role("button", name="Ir para produto").first,
        page.get_by_role("link", name="Ir para produto").first,
        page.locator("a:has-text('Ir para produto')").first,
        page.locator("button:has-text('Ir para produto')").first,
        page.locator("text=Ir para produto").first,
        page.get_by_text("Ir para produto", exact=False).first,
    ]

    for loc in candidates:
        try:
            if await loc.count() == 0:
                continue

            await loc.scroll_into_view_if_needed(timeout=2000)
            await loc.click(timeout=8000)
            return True

        except Exception:
            continue

    return False


async def _ensure_csrf_token_from_affiliates(page) -> str | None:
    """
    🔥 Navega para página de AFILIADOS e captura token de lá
    (token precisa ser do mesmo domínio da API)
    COM LOCK para evitar race condition
    """
    global _CACHED_CSRF

    async with _CSRF_LOCK:
        if _CACHED_CSRF:
            return _CACHED_CSRF

        try:
            current_url = page.url
            print(
                f" → Navegando para página de afiliados (URL atual: {current_url[:60]}...)..."
            )

            await page.goto(
                "https://www.mercadolivre.com.br/afiliados",
                wait_until="domcontentloaded",
                timeout=60000,
            )
            await page.wait_for_timeout(2000)

            token = await page.evaluate(
                """
                () => {
                    const m =
                        document.querySelector('meta[name="csrf-token"]') ||
                        document.querySelector('meta[name="csrf_token"]') ||
                        document.querySelector('meta[name="csrfToken"]');
                    return m ? (m.content || '') : '';
                }
                """
            )

            token = (token or "").strip()

            if token:
                _CACHED_CSRF = token
                print(f" ✓ CSRF token capturado de /afiliados: {token[:20]}...")
                return token

            print(" ⚠️ Não encontrei CSRF token na página de afiliados")
            return None

        except Exception as e:
            print(f" ✗ Erro ao capturar CSRF token: {e}")
            return None


async def _resolve_product_url(page, sec_url: str) -> str | None:
    """Resolve link /sec/ para URL do produto (MLB-xxxxx)"""
    try:
        print(f" → Abrindo: {sec_url[:80]}...")

        await page.goto(sec_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(2000)

        url_inicial = page.url
        print(f" → Página inicial: {url_inicial[:100]}...")

        if _is_product_page(url_inicial):
            print(" ✓ Já está na página do produto!")
            return url_inicial

        if "/social/" in url_inicial.lower() or "/minutoreview" in url_inicial.lower():
            print(" → Detectado minutoreview, clicando 'Ir para produto'...")

            clicked = await _click_ir_para_produto(page)

            if not clicked:
                print(" ⚠️ Botão 'Ir para produto' não encontrado")
                return None

            print(" ✓ Clicou em 'Ir para produto'")

            try:
                await page.wait_for_load_state(
                    "domcontentloaded", timeout=30000
                )
                print(" ✓ Navegação detectada")
            except Exception as e:
                print(f" ⚠️ Timeout esperando navegação: {e}")

            await page.wait_for_timeout(2000)

        url_final = page.url
        print(f" → URL final: {url_final[:120]}")

        if "MLB" in url_final.upper():
            print(" ✓ URL de produto válida (contém MLB)")
            return url_final
        else:
            print(" ⚠️ URL não parece ser de produto")
            return None

    except Exception as e:
        print(f" ✗ Erro ao resolver URL: {e}")

        try:
            current = page.url
            if "MLB" in current.upper() and "/sec/" not in current.lower():
                print(f" ⚠️ Usando URL atual após erro: {current[:120]}")
                return current
        except Exception:
            pass

        return None


async def _create_sec_via_api(page, product_url: str, tag: str) -> str | None:
    """
    🔥 Captura CSRF do domínio correto (afiliados) e chama API
    """
    csrf = await _ensure_csrf_token_from_affiliates(page)

    if not csrf:
        print(" ✗ Não consegui obter x-csrf-token válido")
        return None

    headers = {
        "x-csrf-token": csrf,
        "referer": "https://www.mercadolivre.com.br/afiliados",
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json;charset=UTF-8",
        "origin": "https://www.mercadolivre.com.br",
    }

    payload = {"url": product_url, "tag": tag}

    print(" → Chamando API de afiliados...")

    try:
        resp = await page.context.request.post(
            API_CREATE_LINK,
            data=json.dumps(payload),
            headers=headers,
            timeout=60000,
        )

    except Exception as e:
        print(f" ✗ Falha ao chamar API de afiliados: {e}")
        return None

    if resp.status not in (200, 201):
        try:
            body = await resp.text()
        except Exception:
            body = ""

        print(f" ✗ API retornou {resp.status}. Body: {body[:300]}")

        global _CACHED_CSRF
        if resp.status in (401, 403):
            async with _CSRF_LOCK:
                _CACHED_CSRF = None

        return None

    try:
        data = await resp.json()
    except Exception:
        try:
            data = {"_raw": await resp.text()}
        except Exception:
            data = {}

    sec_id = (data.get("id") or "").strip()

    if not sec_id:
        maybe_url = data.get("url") or data.get("link") or ""
        if isinstance(maybe_url, str) and "/sec/" in maybe_url:
            return maybe_url.strip()

        print(f" ✗ Resposta inesperada da API: {str(data)[:200]}")
        return None

    new_sec = f"https://mercadolivre.com/sec/{sec_id}"
    print(f" ✓ API retornou sec_id: {sec_id}")

    return new_sec


async def generate_affiliate_link(
    page_m, any_url: str, tag: str, max_retries: int = 2
) -> tuple[str | None, str | None]:
    """
    🔥 RETORNA: (link_afiliado, product_url)
    Com retry automático em caso de falha
    """
    any_url = (any_url or "").strip()
    if not any_url:
        return None, None

    tag = (tag or "").strip()
    if not tag:
        print(" ✗ Tag do afiliado vazia")
        return None, None

    for attempt in range(max_retries):
        try:
            print(
                f"\n 🔄 Gerando link afiliado (tentativa {attempt+1}/{max_retries})"
            )

            product_url = await _resolve_product_url(page_m, any_url)

            if not product_url:
                print(" ✗ Não consegui chegar na página do produto")
                if attempt < max_retries - 1:
                    await asyncio.sleep(3)
                    continue
                return None, None

            sec = await _create_sec_via_api(page_m, product_url, tag)

            if sec:
                print(f" ✅ Link afiliado gerado com sucesso: {sec}")

                try:
                    await page_m.goto(
                        product_url,
                        wait_until="domcontentloaded",
                        timeout=30000,
                    )
                    await page_m.wait_for_timeout(1500)
                    print(" ✓ Voltou para página do produto")
                except Exception as e:
                    print(f" ⚠️ Erro ao voltar para produto: {e}")

                return sec, product_url

            else:
                print(" ✗ API não conseguiu gerar link afiliado")

                if attempt < max_retries - 1:
                    global _CACHED_CSRF
                    async with _CSRF_LOCK:
                        _CACHED_CSRF = None

                    await asyncio.sleep(3)
                    continue

        except Exception as e:
            print(f" ✗ Erro na tentativa {attempt+1}: {e}")

            if attempt < max_retries - 1:
                await asyncio.sleep(3)
                continue

    return None, None


async def download_product_image(
    page, product_url: str, out_dir: str = "./tmp"
) -> str | None:
    """
    🔥 Baixa imagem FORÇANDO formato JPEG (não PNG)
    Isso evita que WhatsApp converta em sticker
    """
    try:
        print(" → Baixando imagem do produto ML...")

        current = page.url
        if product_url not in current:
            await page.goto(
                product_url,
                wait_until="domcontentloaded",
                timeout=30000,
            )
            await page.wait_for_timeout(2000)

        img_selectors = [
            "figure.ui-pdp-gallery__figure img[src^='http']",
            "img.ui-pdp-image[src^='http']",
            "div.ui-pdp-gallery img[src^='http']",
            "img[src*='mlb-s1']",
            "img[src*='mlb-s2']",
            "img[src*='mlb-s3']",
        ]

        img_element = None

        for selector in img_selectors:
            try:
                elem = page.locator(selector).first
                if await elem.count() > 0:
                    img_element = elem
                    print(f" ✓ Imagem encontrada: {selector}")
                    break
            except Exception:
                continue

        if not img_element:
            print(" ✗ Não encontrei imagem do produto")
            return None

        Path(out_dir).mkdir(parents=True, exist_ok=True)
        out_path = Path(out_dir) / "product_image.jpg"

        await img_element.screenshot(
            path=str(out_path),
            type="jpeg",
            quality=90,
            timeout=15000,
        )

        print(f" ✓ Imagem salva como JPEG: {out_path}")
        return str(out_path)

    except Exception as e:
        print(f" ✗ Erro ao baixar imagem: {e}")
        return None