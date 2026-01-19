# affiliate.py
from playwright.async_api import TimeoutError as PWTimeout

def _has_meli_link(s: str) -> bool:
    s = (s or "").strip().lower()
    return "mercadolivre.com" in s and "/sec/" in s

async def _click_ir_para_produto(page):
    # tenta vários seletores (button / link)
    candidates = [
        page.get_by_role("button", name="Ir para produto").first,
        page.locator("a:has-text('Ir para produto')").first,
        page.locator("button:has-text('Ir para produto')").first,
        page.locator("text=Ir para produto").first,
    ]

    for loc in candidates:
        try:
            if await loc.count() == 0:
                continue
            await loc.scroll_into_view_if_needed(timeout=2000)
            # force ajuda quando tem overlay/camada
            await loc.click(timeout=8000, force=True)
            return True
        except Exception:
            continue

    return False

async def _wait_share_bar(page) -> bool:
    # Botão de afiliados (topo)
    share = page.get_by_role("button", name="Compartilhar").first
    try:
        await share.wait_for(state="visible", timeout=15000)
        return True
    except Exception:
        return False

async def _open_share_modal(page) -> bool:
    share = page.get_by_role("button", name="Compartilhar").first
    try:
        await share.scroll_into_view_if_needed(timeout=2000)
        await share.click(timeout=15000)
    except Exception:
        # fallback
        try:
            share2 = page.locator("button:has-text('Compartilhar')").first
            await share2.scroll_into_view_if_needed(timeout=2000)
            await share2.click(timeout=15000, force=True)
        except Exception:
            return False

    # às vezes aparece menu com "Gerar link / ID de produto"
    try:
        opt = page.locator("text=Gerar link / ID de produto").first
        if await opt.count() > 0:
            await opt.click(timeout=8000)
    except Exception:
        pass

    # modal/título
    try:
        await page.locator("text=Gerar link / ID de produto").first.wait_for(state="visible", timeout=20000)
        return True
    except Exception:
        return False

async def _read_affiliate_link_from_modal(page) -> str | None:
    # pega pelo label (bem mais estável)
    label = page.locator("text=Link do produto").first
    try:
        await label.wait_for(state="visible", timeout=20000)
    except PWTimeout:
        return None

    input_link = label.locator("xpath=following::input[1]").first

    try:
        await input_link.wait_for(state="visible", timeout=20000)
        await page.wait_for_timeout(1200)  # tempo pro JS preencher
        val = (await input_link.input_value()).strip()
        if _has_meli_link(val):
            return val
    except Exception:
        pass

    # fallback: clicar no botão copiar do campo e ler clipboard
    try:
        copy_btn = input_link.locator("xpath=following::button[1]").first
        if await copy_btn.count() > 0:
            await copy_btn.click(timeout=8000, force=True)
            await page.wait_for_timeout(300)
            clip = await page.evaluate("() => navigator.clipboard.readText().catch(()=> '')")
            clip = (clip or "").strip()
            if _has_meli_link(clip):
                return clip
    except Exception:
        pass

    return None

async def generate_affiliate_link(page_m, any_url: str) -> str | None:
    # 1) abre o link /sec/
    try:
        await page_m.goto(any_url, wait_until="domcontentloaded", timeout=60000)
    except Exception:
        return None

    # 2) sai da tela "Ir para produto" até encontrar a barra Afiliados (Compartilhar)
    for _ in range(6):
        if await _wait_share_bar(page_m):
            break

        clicked = await _click_ir_para_produto(page_m)
        if clicked:
            # espera navegar/renderizar
            try:
                await page_m.wait_for_load_state("domcontentloaded", timeout=30000)
            except Exception:
                pass
            await page_m.wait_for_timeout(1500)
        else:
            # se nem achou botão, dá um respiro e tenta de novo (página pode estar montando)
            await page_m.wait_for_timeout(1200)

    # se ainda não apareceu "Compartilhar", falha aqui (não chegou na página certa)
    if not await _wait_share_bar(page_m):
        return None

    # 3) abre modal e lê o link
    if not await _open_share_modal(page_m):
        return None

    link = await _read_affiliate_link_from_modal(page_m)
    return link