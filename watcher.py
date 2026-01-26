# watcher.py - MANTÉM \n NO TEXTO (não quebra)

import asyncio
import hashlib
from pathlib import Path
import re
from playwright.async_api import TimeoutError as PWTimeout
from extractor import cut_text_after_first_meli_link


def compute_msg_id(text: str, urls: list[str] | None = None) -> str:
    base = (text or "").strip()
    if urls:
        base += "\n" + "\n".join([u.strip() for u in urls if u and u.strip()])
    return hashlib.sha256(base.encode("utf-8", errors="ignore")).hexdigest()


async def detect_chat_type(page) -> str:
    """Detecta se o chat atual é um canal, grupo ou conversa individual"""
    try:
        # Canais têm elementos específicos
        channel_indicators = [
            "div[data-id][data-id*='newsletter']",  # ID de canal contém 'newsletter'
            "span[data-icon='newsletter']",  # Ícone de canal
            "div[aria-label*='Canal']",
            "div[aria-label*='Channel']",
        ]
        
        for selector in channel_indicators:
            element = page.locator(selector).first
            if await element.count() > 0:
                return "channel"
        
        # Grupos têm ícone de grupo ou múltiplos participantes no header
        group_indicators = [
            "span[data-icon='default-group']",
            "span[data-icon='group']",
        ]
        
        for selector in group_indicators:
            element = page.locator(selector).first
            if await element.count() > 0:
                return "group"
        
        # Se não for canal nem grupo, assume conversa individual
        return "individual"
        
    except Exception:
        return "unknown"


async def open_chat(page, chat_name: str):
    """Abre um chat (grupo, canal ou individual) pelo nome"""
    await page.wait_for_selector("div[contenteditable='true'][data-tab]", timeout=60000)
    search = page.locator("div[contenteditable='true'][data-tab]").first
    await search.click()
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Backspace")
    await search.type(chat_name, delay=50)
    await page.wait_for_timeout(1000)  # Aumentado para dar tempo de carregar canais

    # Estratégia 1: Procurar por título exato
    hit = page.locator(f'span[title="{chat_name}"]').first
    if await hit.count() > 0:
        await hit.click()
        await page.wait_for_timeout(800)
        return

    # Estratégia 2: Procurar em todos os resultados de busca (incluindo canais)
    search_results = page.locator("div[role='listitem'], div[data-testid='cell-frame-container']").all()
    results = await search_results
    
    for result in results:
        try:
            text_content = await result.text_content()
            if text_content and chat_name.lower() in text_content.lower():
                await result.click()
                await page.wait_for_timeout(800)
                return
        except Exception:
            continue

    # Estratégia 3: Busca por texto (fallback)
    hit2 = page.get_by_text(chat_name, exact=False).first
    if await hit2.count() > 0:
        await hit2.click()
        await page.wait_for_timeout(800)
        return

    raise RuntimeError(f"Não encontrei o chat '{chat_name}' na busca do WhatsApp.")


async def get_last_message_bubble(page):
    """Pega a última bolha de mensagem (grupos, canais ou individual)"""
    # Tenta primeiro com seletores de grupo/individual
    msgs = page.locator("div.message-in, div.message-out")
    n = await msgs.count()
    if n > 0:
        return msgs.nth(n - 1)
    
    # Para canais, as mensagens podem ter seletores diferentes
    # Canais usam estrutura diferente
    channel_msgs = page.locator("div[role='row']:has(div[class*='message'])").all()
    msgs_list = await channel_msgs
    if len(msgs_list) > 0:
        return msgs_list[-1]
    
    # Fallback genérico
    all_msgs = page.locator("div[data-id][class*='message']").all()
    msgs_list = await all_msgs
    if len(msgs_list) > 0:
        return msgs_list[-1]
    
    return None


async def has_image(bubble) -> bool:
    if bubble is None:
        return False
    img = bubble.locator("img[src^='blob:']").first
    if await img.count() > 0:
        return True
    img2 = bubble.locator("img[src]").first
    return await img2.count() > 0


async def extract_last_message_text_and_urls(page) -> tuple[str, list[str]]:
    """Extrai texto mantendo quebras de linha (funciona em grupos e canais)"""
    last = await get_last_message_bubble(page)
    if last is None:
        return "", []

    # URLs - expandir seletores para capturar links em canais também
    try:
        hrefs = await last.locator("a[href^='http']").evaluate_all(
            "els => els.map(a => a.getAttribute('href')).filter(Boolean)"
        )
        hrefs = [h.strip() for h in hrefs if isinstance(h, str) and h.strip()]
    except Exception:
        hrefs = []

    # 🔥 Texto mantendo \n
    raw_text = ""
    
    try:
        spans = last.locator("span.copyable-text")
        count = await spans.count()
        
        texts_parts = []
        for i in range(count):
            span = spans.nth(i)
            text = await span.inner_text()
            if text and text.strip():
                texts_parts.append(text.strip())
        
        # 🔥 JOIN COM \n (mantém quebras de linha)
        raw_text = "\n".join(texts_parts)
        
    except Exception as e:
        print(f"   [DEBUG] Erro ao extrair: {e}")
    
    # Fallback
    if not raw_text or len(raw_text.strip()) < 5:
        try:
            raw_text = await last.inner_text()
        except Exception:
            pass

    raw_text = raw_text.strip()
    
    # Limpeza mínima (só remove metadata)
    if raw_text:
        lines = []
        for ln in raw_text.splitlines():
            ln = ln.strip()
            if not ln:
                continue
            
            ln_lower = ln.lower()
            
            if ln_lower in ("encaminhada", "forwarded"):
                continue
            
            if len(ln) <= 8 and re.match(r"^\d{1,2}:\d{2}(\s?(AM|PM|am|pm))?$", ln):
                continue
            
            lines.append(ln)
        
        # 🔥 JOIN COM \n (mantém estrutura)
        raw_text = "\n".join(lines).strip()

    text = cut_text_after_first_meli_link(raw_text)

    seen = set()
    urls: list[str] = []
    for u in hrefs:
        if u not in seen:
            seen.add(u)
            urls.append(u)

    return text, urls


async def screenshot_last_image(page, out_dir: str, max_retries: int = 2) -> str | None:
    """Fallback"""
    last = await get_last_message_bubble(page)
    if last is None:
        return None

    for attempt in range(max_retries):
        try:
            thumb = last.locator("img[src^='blob:']").first
            if await thumb.count() == 0:
                thumb = last.locator("img[src]").first
            if await thumb.count() == 0:
                return None

            Path(out_dir).mkdir(parents=True, exist_ok=True)
            out_path = Path(out_dir) / "last_image.png"

            try:
                await thumb.scroll_into_view_if_needed(timeout=2000)
            except Exception:
                pass

            try:
                await thumb.click(timeout=4000, force=True)
                await page.wait_for_timeout(1000)
            except Exception:
                await thumb.screenshot(path=str(out_path))
                return str(out_path)

            viewer_img = page.locator("div[role='dialog'] img[src^='blob:'], div[role='dialog'] img[src]").first
            if await viewer_img.count() > 0:
                await page.wait_for_timeout(500)
                await viewer_img.screenshot(path=str(out_path))
            else:
                await thumb.screenshot(path=str(out_path))

            try:
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(250)
            except Exception:
                pass

            return str(out_path)

        except Exception as e:
            print(f"   ⚠️ Erro ao capturar imagem (tentativa {attempt+1}/{max_retries}): {e}")
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
                continue

    return None