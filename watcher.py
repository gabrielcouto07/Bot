# watcher.py

import re
import hashlib
from pathlib import Path

from playwright.async_api import Page, Locator


async def open_chat(page: Page, chat_name: str):
    """Abre conversa pelo nome (LIMPA busca anterior)"""
    search_box = page.locator("div[contenteditable='true'][data-tab='3']")
    await search_box.click()
    await page.wait_for_timeout(300)
    await search_box.press("Control+A")
    await page.wait_for_timeout(100)
    await search_box.press("Backspace")
    await page.wait_for_timeout(200)
    await search_box.type(chat_name, delay=50)
    await page.wait_for_timeout(1000)
    chat_item = page.locator(f"span[title='{chat_name}']").first
    await chat_item.click()
    await page.wait_for_timeout(600)


async def get_last_message_bubble(page: Page) -> Locator | None:
    """Retorna a última mensagem (bolha) da conversa aberta"""
    bubbles = page.locator("div.message-in, div.message-out")
    count = await bubbles.count()
    if count == 0:
        return None
    return bubbles.nth(count - 1)


async def extract_last_message_text_and_urls(page) -> tuple[str, list[str]]:
    """Extrai texto preservando formatação do WhatsApp"""
    last = await get_last_message_bubble(page)
    if last is None:
        return "", []

    hrefs = []
    try:
        hrefs = await last.locator("a[href^='http']").evaluate_all(
            "els => els.map(a => a.getAttribute('href')).filter(Boolean)",
            timeout=5000,
        )
        hrefs = [h.strip() for h in hrefs if isinstance(h, str) and h.strip()]
    except Exception:
        pass

    raw_text = ""
    try:
        copyable = last.locator("span.copyable-text").first
        raw_text = await copyable.evaluate(
            """
            el => {
                let text = '';
                function extract(node) {
                    if (node.nodeType === 3) {
                        text += node.textContent;
                    } else if (node.nodeType === 1) {
                        const tag = node.tagName;
                        if (tag === 'IMG' && node.classList.contains('emoji')) {
                            text += node.alt || '';
                        } else if (tag === 'STRONG') {
                            text += '*';
                            node.childNodes.forEach(extract);
                            text += '*';
                        } else if (tag === 'EM') {
                            text += '_';
                            node.childNodes.forEach(extract);
                            text += '_';
                        } else if (tag === 'BR') {
                            text += '\\n';
                        } else {
                            node.childNodes.forEach(extract);
                        }
                    }
                }
                extract(el);
                return text;
            }
            """,
            timeout=8000,
        )
    except Exception:
        try:
            copyable = last.locator("span.copyable-text").first
            raw_text = await copyable.inner_text(timeout=5000)
        except Exception:
            try:
                raw_text = await last.inner_text(timeout=5000)
            except Exception as e:
                print(f" ⚠️ Não foi possível extrair texto (timeout): {e}")
                return "", hrefs

    raw_text = (raw_text or "").strip()

    lines = []
    for ln in raw_text.splitlines():
        ln_stripped = ln.strip()
        ln_lower = ln_stripped.lower()
        if ln_lower in ("encaminhada", "forwarded"):
            continue
        if (
            ln_stripped
            and len(ln_stripped) <= 8
            and re.match(r"^\d{1,2}:\d{2}(\s?(AM|PM|am|pm))?$", ln_stripped)
        ):
            continue
        lines.append(ln)

    cleaned_lines = []
    prev_empty = False
    for ln in lines:
        is_empty = not ln.strip()
        if is_empty:
            if not prev_empty:
                cleaned_lines.append(ln)
            prev_empty = True
        else:
            cleaned_lines.append(ln)
            prev_empty = False

    raw_text = "\n".join(cleaned_lines).strip()

    text = cut_text_after_first_meli_link(raw_text)

    seen = set()
    urls: list[str] = []
    for u in hrefs:
        if u not in seen:
            seen.add(u)
            urls.append(u)

    return text, urls


def cut_text_after_first_meli_link(text: str) -> str:
    """Corta texto após o primeiro link do Mercado Livre"""
    from extractor import ML_SEC_RE

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


def compute_msg_id(text: str, urls: list[str]) -> str:
    """Gera ID único para a mensagem"""
    combined = f"{text}||{'|'.join(urls)}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


async def has_image(bubble: Locator | None) -> bool:
    """Verifica se a mensagem tem imagem"""
    if bubble is None:
        return False
    img = bubble.locator(
        "img[src^='blob:'], img[src^='data:'], div._1JVSX"
    )
    count = await img.count()
    return count > 0


async def screenshot_last_image(page: Page, download_dir: str) -> str | None:
    """Tira screenshot da última imagem da mensagem"""
    last = await get_last_message_bubble(page)
    if last is None:
        return None

    img = last.locator("img[src^='blob:'], img[src^='data:']").first

    try:
        Path(download_dir).mkdir(parents=True, exist_ok=True)
        path = f"{download_dir}/screenshot_image.jpg"
        await img.screenshot(path=path, type="jpeg", quality=90)
        return path
    except Exception as e:
        print(f" ⚠️ Erro ao tirar screenshot: {e}")
        return None