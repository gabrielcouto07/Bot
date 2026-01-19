# watcher.py
import hashlib
from pathlib import Path
from playwright.async_api import TimeoutError as PWTimeout

def compute_msg_id(text: str) -> str:
    base = (text or "").encode("utf-8", errors="ignore")
    return hashlib.sha256(base).hexdigest()

async def open_chat(page, chat_name: str):
    await page.wait_for_selector("div[contenteditable='true'][data-tab]", timeout=60000)

    search = page.locator("div[contenteditable='true'][data-tab]").first
    await search.click()
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Backspace")
    await search.type(chat_name, delay=60)
    await page.wait_for_timeout(700)

    # 1) selector por title (mais comum)
    hit = page.locator(f'span[title="{chat_name}"]').first
    if await hit.count() > 0:
        await hit.click()
        await page.wait_for_timeout(800)
        return

    # 2) fallback por texto
    hit2 = page.get_by_text(chat_name, exact=False).first
    if await hit2.count() > 0:
        await hit2.click()
        await page.wait_for_timeout(800)
        return

    raise RuntimeError(f"Não encontrei o chat '{chat_name}' na busca do WhatsApp.")

async def get_last_message_bubble(page):
    msgs = page.locator("div.message-in, div.message-out")
    n = await msgs.count()
    if n == 0:
        return None
    return msgs.nth(n - 1)

async def extract_last_message_text_and_urls(page) -> tuple[str, list[str]]:
    """
    Extrai texto do bubble inteiro (não só selectable-text).
    Também extrai URLs via href dos <a> dentro da mensagem.
    """
    last = await get_last_message_bubble(page)
    if last is None:
        return "", []

    # texto bruto do bubble
    try:
        raw_text = (await last.inner_text()).strip()
    except PWTimeout:
        raw_text = ""

    # URLs via href (bem mais confiável em cards)
    hrefs = await last.locator("a[href^='http']").evaluate_all(
        "els => els.map(a => a.getAttribute('href')).filter(Boolean)"
    )
    hrefs = [h.strip() for h in hrefs if isinstance(h, str) and h.strip()]

    # remove lixo comum do forwarded/header caso tenha vindo no inner_text
    # (mantém o corpo, mas tira linhas padrão do topo)
    lines = [ln.strip() for ln in raw_text.splitlines()]
    cleaned = []
    for ln in lines:
        if not ln:
            cleaned.append("")
            continue
        low = ln.lower()
        if low in ("encaminhada", "forwarded"):
            continue
        # remove linha que parece telefone do remetente em encaminhada
        if low.startswith("+55") and len(ln) < 25:
            continue
        cleaned.append(ln)
    text = "\n".join(cleaned).strip()

    # junta urls do href com as do texto (dedupe mantendo ordem)
    seen = set()
    urls = []
    for u in hrefs:
        if u not in seen:
            seen.add(u)
            urls.append(u)

    return text, urls

async def screenshot_last_image(page, out_dir: str) -> str | None:
    """
    Método estável: abre a imagem no viewer e tira screenshot (sem 'Baixar').
    """
    last = await get_last_message_bubble(page)
    if last is None:
        return None

    thumb = last.locator("img").first
    if await thumb.count() == 0:
        return None

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    out_path = Path(out_dir) / "last_image.png"

    await thumb.click()
    await page.wait_for_timeout(800)

    # tenta achar imagem grande do viewer
    viewer_img = page.locator("div[role='dialog'] img").first
    if await viewer_img.count() == 0:
        # fallback: screenshot do thumbnail mesmo
        await thumb.screenshot(path=str(out_path))
        return str(out_path)

    await page.wait_for_timeout(800)
    await viewer_img.screenshot(path=str(out_path))

    # fecha viewer
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(300)
    return str(out_path)