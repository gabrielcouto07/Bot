# watcher.py - Monitoramento e extração de mensagens do WhatsApp

import re
import hashlib
import base64
import uuid
import os
from pathlib import Path
from datetime import datetime
from playwright.async_api import Page, Locator


async def open_chat(page: Page, chat_name: str, max_retries: int = 3):
    """Abre um chat pelo nome com retry de até 3 vezes e seletores robustos"""
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"   🔎 Procurando chat: {chat_name}... (tentativa {attempt}/{max_retries})")
            
            # Método 1: Busca direta pelo nome
            try:
                chat_locator = page.locator(f"span[title='{chat_name}']").first
                if await chat_locator.count() > 0:
                    visible = await chat_locator.is_visible(timeout=2000)
                    if visible:
                        await chat_locator.click()
                        await page.wait_for_timeout(500)
                        print(f"   ✅ Chat aberto: {chat_name}")
                        return True
            except Exception:
                pass

            # Método 2: Usar busca do WhatsApp com seletores robustos
            try:
                # Seletores alternativos para a caixa de busca (WhatsApp muda frequentemente)
                search_selectors = [
                    'div[contenteditable="true"][data-tab="3"]',  # Original
                    'div[contenteditable="true"][title*="Pesquisar"]',
                    'div[contenteditable="true"][title*="Search"]',
                    '#side div[contenteditable="true"]',
                    'div[role="searchbox"]',
                ]
                
                search_box = None
                for sel in search_selectors:
                    try:
                        loc = page.locator(sel).first
                        if await loc.count() > 0:
                            search_box = loc
                            print(f"   ✓ Caixa de busca encontrada: {sel[:40]}...")
                            break
                    except Exception:
                        continue
                
                if search_box is None:
                    print(f"   ⚠️  Nenhuma caixa de busca encontrada com os seletores")
                    raise Exception("Search box not found")
                
                await search_box.click(timeout=2000)
                await page.wait_for_timeout(300)
                
                await search_box.press("Control+A")
                await search_box.press("Backspace")
                await page.wait_for_timeout(200)
                
                await search_box.fill(chat_name, timeout=2000)
                await page.wait_for_timeout(1500)

                chat_locator = page.locator(f"span[title='{chat_name}']").first
                if await chat_locator.count() > 0:
                    await chat_locator.click(timeout=2000)
                    await page.wait_for_timeout(300)
                    
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(800)
                    print(f"   ✅ Chat aberto: {chat_name}")
                    return True
                else:
                    print(f"   ⚠️  Chat '{chat_name}' não encontrado nos resultados")
            except Exception as search_err:
                print(f"   ⚠️  Método de busca falhou: {str(search_err)[:50]}")
        
        except Exception as e:
            print(f"   ⚠️  Tentativa {attempt}/{max_retries} falhou: {str(e)[:60]}")
        
        if attempt < max_retries:
            print(f"   ⏳ Aguardando 2s para retry...")
            await page.wait_for_timeout(2000)
    
    # Se chegou aqui, esgotou as tentativas
    print(f"   ❌ Não foi possível abrir o chat '{chat_name}' após {max_retries} tentativas")
    return False


async def get_last_message_bubble(page: Page) -> Locator | None:
    """Retorna a última bolha de mensagem"""
    bubbles = page.locator("div.message-in, div.message-out")
    count = await bubbles.count()
    if count == 0:
        return None
    return bubbles.nth(count - 1)


async def extract_last_message_text_and_urls(page) -> tuple[str, list[str]]:
    """Extrai texto e URLs da última mensagem"""
    last = await get_last_message_bubble(page)
    if last is None:
        return "", []
    
    # Extrai links
    hrefs = []
    try:
        hrefs = await last.locator("a[href^='http']").evaluate_all(
            "els => els.map(a => a.getAttribute('href')).filter(Boolean)"
        )
        hrefs = [h.strip() for h in hrefs if isinstance(h, str) and h.strip()]
    except Exception:
        pass
    
    # Extrai texto
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
    
    # Remove metadados (horário, encaminhado)
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
        
    # Remove linhas vazias duplicadas
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
    
    text = cut_text_after_link(raw_text)
    
    seen = set()
    urls: list[str] = []
    for u in hrefs:
        if u not in seen:
            seen.add(u)
            urls.append(u)
    return text, urls


def cut_text_after_link(text: str) -> str:
    """Corta o texto após o link do ML ou Amazon"""
    if not text:
        return ""

    # Padrões ML: /sec/ tradicional E meli.la shortener
    ml_re = re.compile(r"(mercadolivre\.com(?:\.br)?/.*?/sec/[A-Za-z0-9]+|https?://meli\.la/[A-Za-z0-9]+)", re.IGNORECASE)
    amz_re = re.compile(r"(https?://(?:www\.|m\.|smile\.)?amazon\.com\.br/[^\s]+|https?://amzn\.to/[^\s]+)", re.IGNORECASE)

    m_ml = ml_re.search(text)
    m_amz = amz_re.search(text)

    cut_index = len(text)
    found = False

    if m_ml:
        cut_index = min(cut_index, m_ml.end())
        found = True
    
    if m_amz:
        if m_amz.end() <= cut_index:
            cut_index = m_amz.end()
            found = True

    processed_text = text
    if found:
        processed_text = text[:cut_index]

    # Remove linhas de rodapé
    lines = processed_text.splitlines()
    clean_lines = []
    for ln in lines:
        ln_stripped = ln.strip()
        ln_lower = ln_stripped.lower()
        
        if (
            ln_lower.startswith("link do grupo")
            or ln_lower.startswith("☑️ link do grupo")
            or "link do grupo:" in ln_lower
            or ln_stripped == "☑️"
        ):
            break 
            
        clean_lines.append(ln)

    return "\n".join(clean_lines).strip()


def compute_msg_id(text: str, urls: list[str]) -> str:
    """Gera hash único para identificar a mensagem"""
    combined = f"{text}||{'|'.join(urls)}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


async def get_last_message_id(page: Page) -> str:
    """Obtém um ID estável da última mensagem pelo DOM (data-id/pre-plain-text)."""
    last = await get_last_message_bubble(page)
    if last is None:
        return ""
    try:
        msg_id = await last.get_attribute("data-id")
        if msg_id:
            return msg_id.strip()
        pre = await last.get_attribute("data-pre-plain-text")
        return (pre or "").strip()
    except Exception:
        return ""


async def has_image(bubble) -> bool:
    """
    🔥 CORRIGIDO: Verifica se a bolha tem imagem.
    Usa múltiplos seletores robustos em vez de classe CSS ofuscada (_1JVSX).
    """
    if bubble is None:
        return False

    # Seletores robustos (sem classes ofuscadas que mudam)
    img_selectors = [
        # Imagens blob (carregadas) e data URI
        "img[src^='blob:']",
        "img[src^='data:']",
        # Imagens do servidor WhatsApp
        "img[src*='mmg.whatsapp.net']",
        "img[src*='web.whatsapp.net']",
        # Container de mídia pelo role
        "div[data-testid='image-thumb']",
        "div[data-testid='media-viewer-image']",
        # Indicador de mídia carregando (também conta como tem imagem)
        "span[data-icon='media-download']",
        "div[data-icon='media-download']",
        # Botão de download de imagem
        "div[role='button'][aria-label*='download' i]",
        "div[role='button'][aria-label*='baixar' i]",
        # Classe _1JVSX legada (mantido como fallback)
        "div._1JVSX",
    ]

    for selector in img_selectors:
        try:
            elem = bubble.locator(selector).first
            count = await elem.count()
            if count > 0:
                return True
        except Exception:
            continue

    return False

async def _wait_for_image_fully_loaded(page: Page, bubble: Locator, max_wait_seconds: int = 45) -> bool:
    """
    🔥 Aguarda a imagem estar COMPLETAMENTE carregada no WhatsApp.
    Verifica múltiplos indicadores de loading e qualidade da imagem.
    
    Returns:
        True se imagem carregou, False se timeout
    """
    print("   ⏳ Aguardando imagem carregar completamente...")
    
    # Indicadores de que a imagem AINDA está carregando
    loading_selectors = [
        '[data-icon="media-download"]',
        '[data-icon="media-cancel"]', 
        '[data-icon="audio-download"]',
        'div[role="button"][aria-label*="Download"]',
        'span[data-icon="media-download"]',
        'div[data-icon="media-disabled"]',
        # Spinner/loading circle
        'div[role="progressbar"]',
        'span[data-icon="spinner"]',
        # Blur placeholder
        'div._1JVSX[style*="blur"]',
        'img[style*="blur"]',
    ]
    
    for attempt in range(max_wait_seconds * 2):  # Checa a cada 500ms
        is_loading = False
        
        # Verifica indicadores de loading
        for selector in loading_selectors:
            try:
                indicator = bubble.locator(selector).first
                if await indicator.count() > 0:
                    visible = await indicator.is_visible()
                    if visible:
                        is_loading = True
                        break
            except Exception:
                continue
        
        # Verifica se a imagem tem tamanho adequado (não é thumbnail blur)
        if not is_loading:
            try:
                img_elem = bubble.locator("img[src^='blob:'], img[src^='https://']").first
                if await img_elem.count() > 0:
                    # Verifica dimensões da imagem
                    dimensions = await page.evaluate(
                        """
                        (img) => {
                            if (!img) return null;
                            return {
                                natural: { w: img.naturalWidth, h: img.naturalHeight },
                                display: { w: img.width, h: img.height },
                                complete: img.complete,
                                src: img.src ? img.src.substring(0, 50) : ''
                            };
                        }
                        """,
                        await img_elem.element_handle()
                    )
                    
                    if dimensions:
                        nat_w = dimensions.get("natural", {}).get("w", 0)
                        nat_h = dimensions.get("natural", {}).get("h", 0)
                        complete = dimensions.get("complete", False)
                        
                        # Imagem válida: complete=True e dimensões > 100px (não é blur thumbnail)
                        if complete and nat_w > 100 and nat_h > 100:
                            print(f"   ✅ Imagem carregada: {nat_w}x{nat_h}px")
                            return True
                        elif not complete:
                            is_loading = True
                        elif nat_w <= 100 or nat_h <= 100:
                            # Provavelmente é thumbnail blur, ainda carregando
                            is_loading = True
                            
            except Exception:
                pass
        
        if is_loading:
            if attempt % 4 == 0:  # Log a cada 2 segundos
                print(f"   ⏳ Ainda carregando... ({attempt // 2}s)")
            await page.wait_for_timeout(500)
        else:
            # Sem indicador de loading e sem imagem válida = algo errado
            await page.wait_for_timeout(500)
            
    print(f"   ⚠️ Timeout após {max_wait_seconds}s aguardando imagem")
    return False


async def screenshot_last_image(page: Page, download_dir: str, source_name: str = "") -> str | None:
    """Fallback: tira screenshot da imagem se download falhar"""
    last = await get_last_message_bubble(page)
    if last is None:
        return None
    
    img = last.locator("img[src^='blob:'], img[src^='data:'], img[src^='https://']").first
    try:
        Path(download_dir).mkdir(parents=True, exist_ok=True)
        safe_source = re.sub(r'[^\w\-]', '_', source_name) if source_name else "unknown"
        timestamp = datetime.now().strftime("%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"screenshot_{safe_source}_{timestamp}_{unique_id}.jpg"
        path = f"{download_dir}/{filename}"
        await img.screenshot(path=path, type="jpeg", quality=90, timeout=15000)
        print(f"   ✓ Screenshot salvo: {filename}")
        return path
    except Exception as e:
        print(f"   ⚠️ Erro ao tirar screenshot: {e}")
        return None


async def download_last_image(page: Page, download_dir: str, source_name: str = "") -> str | None:
    """
    🔥 Baixa a imagem da última mensagem.
    AGUARDA a imagem carregar completamente antes de baixar.
    """
    last = await get_last_message_bubble(page)
    if last is None:
        return None
    
    try:
        # 🔥 PRIMEIRO: Aguarda a imagem carregar completamente
        image_loaded = await _wait_for_image_fully_loaded(page, last, max_wait_seconds=45)
        
        if not image_loaded:
            print("   ⚠️ Imagem não carregou completamente - tentando screenshot mesmo assim")
        
        # Espera adicional de segurança após loading
        await page.wait_for_timeout(2000)

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
                    # Verifica se não é thumbnail blur (muito pequena)
                    dimensions = await page.evaluate(
                        """
                        (img) => {
                            if (!img) return null;
                            return { w: img.naturalWidth, h: img.naturalHeight };
                        }
                        """,
                        await elem.element_handle()
                    )
                    
                    if dimensions and dimensions.get("w", 0) > 100 and dimensions.get("h", 0) > 100:
                        img_url = await elem.get_attribute("src")
                        if not img_url:
                            img_url = await elem.get_attribute("data-plain-src")
                        if img_url:
                            img_element = elem
                            print(f"   ✓ Imagem válida encontrada: {selector} ({dimensions['w']}x{dimensions['h']})")
                            break
            except Exception:
                continue
        
        if not img_element or not img_url:
            print("   ⚠️ Não encontrei imagem válida - usando screenshot")
            return await screenshot_last_image(page, download_dir, source_name)
        
        # Verifica uma última vez se a imagem está completa
        try:
            is_complete = await page.evaluate(
                """
                (img) => img && img.complete && img.naturalWidth > 100
                """,
                await img_element.element_handle()
            )
            if not is_complete:
                print("   ⚠️ Imagem não está completa - aguardando mais 3s...")
                await page.wait_for_timeout(3000)
        except Exception:
            pass
        
        Path(download_dir).mkdir(parents=True, exist_ok=True)
        safe_source = re.sub(r'[^\w\-]', '_', source_name) if source_name else "unknown"
        timestamp = datetime.now().strftime("%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"img_{safe_source}_{timestamp}_{unique_id}.jpg"
        path = f"{download_dir}/{filename}"

        if img_url.startswith("blob:"):
            try:
                base64_data = await page.evaluate(
                    """
                    async (blobUrl) => {
                        try {
                            const response = await fetch(blobUrl);
                            const blob = await response.blob();
                            return new Promise((resolve, reject) => {
                                const reader = new FileReader();
                                reader.onloadend = () => resolve(reader.result);
                                reader.onerror = () => reject('FileReader error');
                                reader.readAsDataURL(blob);
                            });
                        } catch (e) {
                            return null;
                        }
                    }
                    """,
                    img_url
                )
                if base64_data and "base64," in base64_data:
                    base64_str = base64_data.split("base64,")[1]
                    image_bytes = base64.b64decode(base64_str)
                    
                    # Verifica se não é imagem muito pequena (thumbnail)
                    if len(image_bytes) < 5000:  # < 5KB provavelmente é thumbnail
                        print(f"   ⚠️ Imagem muito pequena ({len(image_bytes)} bytes) - usando screenshot")
                        return await screenshot_last_image(page, download_dir, source_name)
                    
                    with open(path, "wb") as f:
                        f.write(image_bytes)
                    print(f"   ✓ Imagem salva: {filename} ({len(image_bytes)} bytes)")
                    return path
                else:
                    return await screenshot_last_image(page, download_dir, source_name)
            except Exception as e:
                print(f"   ⚠️ Erro ao baixar blob: {e}")
                return await screenshot_last_image(page, download_dir, source_name)
                
        elif img_url.startswith("https://"):
            try:
                response = await page.context.request.get(img_url, timeout=30000)
                if response.status == 200:
                    image_data = await response.body()
                    if len(image_data) < 5000:
                        print(f"   ⚠️ Imagem muito pequena ({len(image_data)} bytes) - usando screenshot")
                        return await screenshot_last_image(page, download_dir, source_name)
                    with open(path, "wb") as f:
                        f.write(image_data)
                    print(f"   ✓ Imagem salva: {filename}")
                    return path
                else:
                    return await screenshot_last_image(page, download_dir, source_name)
            except Exception:
                return await screenshot_last_image(page, download_dir, source_name)
        else:
            return await screenshot_last_image(page, download_dir, source_name)
            
    except Exception as e:
        print(f"   ⚠️ Erro geral ao baixar imagem: {e}")
        return await screenshot_last_image(page, download_dir, source_name)