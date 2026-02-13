import re
import hashlib
import base64
import uuid
import os
from pathlib import Path
from datetime import datetime
from playwright.async_api import Page, Locator

# --- FUNÇÃO DE ABERTURA DE CHAT (MANTIDA) ---
async def open_chat(page: Page, chat_name: str):
    """
    Tenta abrir o chat. Se não estiver visível, usa a barra de pesquisa.
    """
    print(f"   🔎 Procurando chat: {chat_name}...")
    
    try:
        chat_locator = page.locator(f"span[title='{chat_name}']").first
        if await chat_locator.is_visible(timeout=2000):
            await chat_locator.click()
            await page.wait_for_timeout(500)
            return True
    except Exception:
        pass

    try:
        search_box = page.locator('div[contenteditable="true"][data-tab="3"]')
        await search_box.click()
        await page.wait_for_timeout(300)
        
        await search_box.press("Control+A")
        await search_box.press("Backspace")
        
        await search_box.fill(chat_name)
        await page.wait_for_timeout(2000)

        chat_locator = page.locator(f"span[title='{chat_name}']").first
        await chat_locator.click()

        await page.keyboard.press("Escape")
        await page.wait_for_timeout(1000)
        return True

    except Exception as e:
        raise Exception(f"❌ Não foi possível encontrar o chat '{chat_name}'. Erro: {e}")


# --- FUNÇÕES DE EXTRAÇÃO (ATUALIZADAS PARA CORTAR AMAZON TAMBÉM) ---

async def get_last_message_bubble(page: Page) -> Locator | None:
    bubbles = page.locator("div.message-in, div.message-out")
    count = await bubbles.count()
    if count == 0:
        return None
    return bubbles.nth(count - 1)

async def extract_last_message_text_and_urls(page) -> tuple[str, list[str]]:
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
            raw_text = await last.inner_text(timeout=5000)
        except Exception:
            pass

    raw_text = (raw_text or "").strip()
    
    # Remove metadados de tempo/encaminhamento
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
    
    # 🔥 AQUI ESTÁ A MUDANÇA: Usa a nova função genérica
    text = cut_text_after_link(raw_text)
    
    seen = set()
    urls: list[str] = []
    for u in hrefs:
        if u not in seen:
            seen.add(u)
            urls.append(u)
    return text, urls

def cut_text_after_link(text: str) -> str:
    """
    Corta o texto imediatamente após o link do Mercado Livre OU Amazon.
    Também remove linhas de rodapé (Link do grupo, checks, etc).
    """
    if not text:
        return ""

    # Regex para ML (/sec/)
    ml_re = re.compile(r"(mercadolivre\.com(?:\.br)?/.*?/sec/[A-Za-z0-9]+)", re.IGNORECASE)
    # Regex para Amazon (dp/ASIN, gp/product, amzn.to)
    amz_re = re.compile(r"(https?://(?:www\.|m\.|smile\.)?amazon\.com\.br/[^\s]+|https?://amzn\.to/[^\s]+)", re.IGNORECASE)

    # Procura ML
    m_ml = ml_re.search(text)
    # Procura Amazon
    m_amz = amz_re.search(text)

    cut_index = len(text)
    found = False

    # Se achou ML, marca onde termina
    if m_ml:
        cut_index = min(cut_index, m_ml.end())
        found = True
    
    # Se achou Amazon, vê se termina antes (caso tenha os dois, pega o primeiro)
    if m_amz:
        # Verifica se o link da Amazon termina antes do corte atual
        if m_amz.end() <= cut_index:
            cut_index = m_amz.end()
            found = True

    # Se achou algum link, corta o texto HARD ali
    processed_text = text
    if found:
        processed_text = text[:cut_index]

    # Limpeza adicional de linhas (para remover restos ou caso não tenha achado link)
    lines = processed_text.splitlines()
    clean_lines = []
    for ln in lines:
        ln_stripped = ln.strip()
        ln_lower = ln_stripped.lower()
        
        # Pula linhas que parecem rodapé antigo
        if (
            ln_lower.startswith("link do grupo")
            or ln_lower.startswith("☑️ link do grupo")
            or "link do grupo:" in ln_lower
            or ln_stripped == "☑️"
        ):
            # Se encontrou linha de grupo explicitamente, para de processar (break)
            # ou apenas ignora (continue). Como cortamos no link, 'break' é seguro.
            break 
            
        clean_lines.append(ln)

    return "\n".join(clean_lines).strip()

def compute_msg_id(text: str, urls: list[str]) -> str:
    combined = f"{text}||{'|'.join(urls)}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()

async def has_image(bubble: Locator | None) -> bool:
    if bubble is None:
        return False
    img = bubble.locator("img[src^='blob:'], img[src^='data:'], div._1JVSX")
    count = await img.count()
    return count > 0


async def download_image_from_bubble(page: Page, bubble: Locator, download_dir: str, source_name: str = "") -> str | None:
    """
    Baixa a imagem de um bubble ESPECÍFICO (garante que imagem e texto vêm da mesma mensagem).
    """
    if bubble is None:
        return None
    try:
        img_selectors = [
            "img[src^='blob:']",
            "img[src^='https://']",
            "img[data-plain-src]",
            "img[src*='mmg.whatsapp.net']",
            "img[src^='data:']",
        ]
        img_element = None
        img_url = None
        for selector in img_selectors:
            try:
                elem = bubble.locator(selector).first
                if await elem.count() > 0:
                    img_url = await elem.get_attribute("src")
                    if not img_url:
                        img_url = await elem.get_attribute("data-plain-src")
                    if img_url:
                        img_element = elem
                        print(f"   ✓ Imagem encontrada: {selector} ({img_url[:50]}...)")
                        break
            except Exception:
                continue
        if not img_element or not img_url:
            print("   ⚠️ Não encontrei imagem no bubble")
            return None
        
        Path(download_dir).mkdir(parents=True, exist_ok=True)
        safe_source = re.sub(r'[^\w\-]', '_', source_name) if source_name else "unknown"
        timestamp = datetime.now().strftime("%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"img_{safe_source}_{timestamp}_{unique_id}.jpg"
        path = f"{download_dir}/{filename}"

        if img_url.startswith("blob:"):
            print(f"   → Convertendo blob em imagem real...")
            try:
                base64_data = await page.evaluate(
                    """
                    async (blobUrl) => {
                        const response = await fetch(blobUrl);
                        const blob = await response.blob();
                        return new Promise((resolve) => {
                            const reader = new FileReader();
                            reader.onloadend = () => resolve(reader.result);
                            reader.readAsDataURL(blob);
                        });
                    }
                    """,
                    img_url
                )
                if base64_data and "base64," in base64_data:
                    base64_str = base64_data.split("base64,")[1]
                    image_bytes = base64.b64decode(base64_str)
                    with open(path, "wb") as f:
                        f.write(image_bytes)
                    print(f"   ✓ Imagem ORIGINAL do WhatsApp salva: {filename}")
                    return path
                else:
                    return await _screenshot_bubble_image(bubble, download_dir, source_name)
            except Exception:
                return await _screenshot_bubble_image(bubble, download_dir, source_name)
        elif img_url.startswith("https://"):
            response = await page.context.request.get(img_url)
            if response.status == 200:
                image_data = await response.body()
                with open(path, "wb") as f:
                    f.write(image_data)
                return path
            else:
                return await _screenshot_bubble_image(bubble, download_dir, source_name)
        else:
            return await _screenshot_bubble_image(bubble, download_dir, source_name)
    except Exception:
        return await _screenshot_bubble_image(bubble, download_dir, source_name)


async def _screenshot_bubble_image(bubble: Locator, download_dir: str, source_name: str = "") -> str | None:
    """Faz screenshot da imagem de um bubble específico como fallback."""
    if bubble is None:
        return None
    img = bubble.locator("img[src^='blob:'], img[src^='data:']").first
    try:
        Path(download_dir).mkdir(parents=True, exist_ok=True)
        safe_source = re.sub(r'[^\w\-]', '_', source_name) if source_name else "unknown"
        timestamp = datetime.now().strftime("%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"screenshot_{safe_source}_{timestamp}_{unique_id}.jpg"
        path = f"{download_dir}/{filename}"
        await img.screenshot(path=path, type="jpeg", quality=90)
        print(f"   ✓ Screenshot salvo: {filename}")
        return path
    except Exception as e:
        print(f"   ⚠️ Erro ao fazer screenshot do bubble: {e}")
        return None


async def download_last_image(page: Page, download_dir: str, source_name: str = "") -> str | None:
    last = await get_last_message_bubble(page)
    if last is None:
        return None
    try:
        img_selectors = [
            "img[src^='blob:']",
            "img[src^='https://']",
            "img[data-plain-src]",
            "img[src*='mmg.whatsapp.net']",
            "img[src^='data:']",
        ]
        img_element = None
        img_url = None
        for selector in img_selectors:
            try:
                elem = last.locator(selector).first
                if await elem.count() > 0:
                    img_url = await elem.get_attribute("src")
                    if not img_url:
                        img_url = await elem.get_attribute("data-plain-src")
                    if img_url:
                        img_element = elem
                        print(f"   ✓ Imagem encontrada: {selector} ({img_url[:50]}...)")
                        break
            except Exception:
                continue
        if not img_element or not img_url:
            print("   ⚠️ Não encontrei imagem")
            return None
        
        Path(download_dir).mkdir(parents=True, exist_ok=True)
        safe_source = re.sub(r'[^\w\-]', '_', source_name) if source_name else "unknown"
        timestamp = datetime.now().strftime("%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"img_{safe_source}_{timestamp}_{unique_id}.jpg"
        path = f"{download_dir}/{filename}"

        if img_url.startswith("blob:"):
            print(f"   → Convertendo blob em imagem real...")
            try:
                base64_data = await page.evaluate(
                    """
                    async (blobUrl) => {
                        const response = await fetch(blobUrl);
                        const blob = await response.blob();
                        return new Promise((resolve) => {
                            const reader = new FileReader();
                            reader.onloadend = () => resolve(reader.result);
                            reader.readAsDataURL(blob);
                        });
                    }
                    """,
                    img_url
                )
                if base64_data and "base64," in base64_data:
                    base64_str = base64_data.split("base64,")[1]
                    image_bytes = base64.b64decode(base64_str)
                    with open(path, "wb") as f:
                        f.write(image_bytes)
                    print(f"   ✓ Imagem ORIGINAL do WhatsApp salva: {filename}")
                    return path
                else:
                    return await screenshot_last_image(page, download_dir, source_name)
            except Exception:
                return await screenshot_last_image(page, download_dir, source_name)
        elif img_url.startswith("https://"):
            response = await page.context.request.get(img_url)
            if response.status == 200:
                image_data = await response.body()
                with open(path, "wb") as f:
                    f.write(image_data)
                return path
            else:
                return await screenshot_last_image(page, download_dir, source_name)
        else:
            return await screenshot_last_image(page, download_dir, source_name)
    except Exception:
        return await screenshot_last_image(page, download_dir, source_name)

async def screenshot_last_image(page: Page, download_dir: str, source_name: str = "") -> str | None:
    last = await get_last_message_bubble(page)
    if last is None:
        return None
    img = last.locator("img[src^='blob:'], img[src^='data:']").first
    try:
        Path(download_dir).mkdir(parents=True, exist_ok=True)
        safe_source = re.sub(r'[^\w\-]', '_', source_name) if source_name else "unknown"
        timestamp = datetime.now().strftime("%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"screenshot_{safe_source}_{timestamp}_{unique_id}.jpg"
        path = f"{download_dir}/{filename}"
        await img.screenshot(path=path, type="jpeg", quality=90)
        print(f"   ✓ Screenshot salvo: {filename}")
        return path
    except Exception as e:
        print(f"   ⚠️ Erro ao tirar screenshot: {e}")
        return None