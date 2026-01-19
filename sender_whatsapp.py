# sender_whatsapp.py
from playwright.async_api import TimeoutError as PWTimeout

async def _open_and_focus_composer(page, chat_name: str, open_chat_fn):
    await open_chat_fn(page, chat_name)
    await page.wait_for_timeout(500)

    # Composer (campo de digitar) - seletor mais estável
    # Em muitos builds é data-tab="10"
    box = page.locator("footer div[contenteditable='true'][data-tab='10']").first

    # Fallbacks (mudanças do WA)
    if await box.count() == 0:
        box = page.locator("footer div[contenteditable='true']").first
    if await box.count() == 0:
        box = page.locator("div[contenteditable='true'][data-tab]").last

    await box.wait_for(state="visible", timeout=30000)
    await box.click()
    return box

async def _clear_box(page):
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Backspace")

async def _get_last_out_text(page) -> str:
    """
    Lê o texto da última mensagem enviada (message-out).
    Usa inner_text do bubble inteiro (mais robusto que span.selectable-text).
    Retorna string vazia se não houver mensagens OUT.
    """
    try:
        out = page.locator("div.message-out").last
        
        # Verifica se existe pelo menos uma mensagem OUT
        if await out.count() == 0:
            return ""
        
        await out.wait_for(state="visible", timeout=5000)

        # tenta pegar o "copyable-text" (geralmente contém só o corpo)
        body = out.locator("div.copyable-text").last
        if await body.count() > 0:
            try:
                return (await body.inner_text(timeout=3000)).strip()
            except Exception:
                pass

        # fallback: texto do bubble inteiro
        try:
            return (await out.inner_text(timeout=3000)).strip()
        except Exception:
            return ""
            
    except Exception:
        # Se der qualquer erro, retorna vazio (chat sem mensagens OUT)
        return ""

async def send_text_message(page, chat_name: str, text: str, open_chat_fn) -> bool:
    """
    Envia texto e CONFIRMA que apareceu como última mensagem OUT.
    """
    text = (text or "").strip()
    if not text:
        return False

    # usamos um pedaço do final para confirmar
    needle = text[-60:] if len(text) > 60 else text

    try:
        before = await _get_last_out_text(page)  # agora retorna "" se não houver
    except Exception:
        before = ""

    try:
        box = await _open_and_focus_composer(page, chat_name, open_chat_fn)
        await _clear_box(page)

        # type é mais confiável do que fill no WA
        await box.type(text, delay=0)
        await page.keyboard.press("Enter")

        # confirmar: esperar mudar a última mensagem OUT e conter needle
        for attempt in range(25):  # 25 * 400ms = 10s
            await page.wait_for_timeout(400)
            last = await _get_last_out_text(page)

            # Se before estava vazio (primeira msg) ou mudou
            if last and last != before:
                # Verifica se contém o trecho esperado
                if needle in last or last.endswith(needle) or needle in last[-200:]:
                    return True
                # Se a mensagem mudou mas não é a nossa, continua esperando
                # (pode ser que outra pessoa enviou)
                
        # Timeout: não confirmou
        return False

    except PWTimeout:
        return False
    except Exception as e:
        print(f"Erro ao enviar mensagem: {e}")
        return False