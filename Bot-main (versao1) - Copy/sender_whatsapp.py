# sender_whatsapp.py - VERSÃO QUE FUNCIONAVA (RECUPERADA)

import asyncio
from pathlib import Path
from typing import Optional
from playwright.async_api import Page, Locator
from config import GROUP_LINK
from watcher import open_chat


async def _wait_message_box(page: Page) -> Locator:
    """Aguarda a caixa de mensagem estar disponível"""
    candidates = [
        page.locator("footer div[contenteditable='true'][role='textbox']").last,
        page.locator("div[contenteditable='true'][data-tab='10']").last,
    ]
    
    for loc in candidates:
        try:
            await loc.wait_for(state="visible", timeout=15000)
            return loc
        except Exception:
            continue
    
    raise RuntimeError("Não achei a caixa de mensagem do WhatsApp.")


async def send_text_message(
    page: Page,
    target_chat: str,
    text: str,
    target_group: Optional[str] = None,
    skip_open_chat: bool = False
) -> bool:
    """Envia texto COM formatação (*negrito*, emojis)"""
    try:
        if not skip_open_chat:
            await open_chat(page, target_chat)
        
        box = await _wait_message_box(page)
        await box.click()
        await page.wait_for_timeout(200)
        
        await box.press("Control+A")
        await box.press("Backspace")
        await page.wait_for_timeout(80)
        
        # Adiciona link do grupo no final da mensagem
        if GROUP_LINK:
            full_text = f"{text}\n\n☑️ Link do grupo: {GROUP_LINK}"
        else:
            full_text = text
        
        lines = full_text.split("\n")
        for i, line in enumerate(lines):
            if line:
                await box.type(line, delay=2)
            if i < len(lines) - 1:
                await box.press("Shift+Enter")
                await page.wait_for_timeout(15)
        
        await page.wait_for_timeout(100)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(500)
        
        return True
    
    except Exception as e:
        print(f"✗ Falha ao enviar texto: {e}")
        return False


async def _type_with_line_breaks(locator_or_page, text: str, delay: int = 5) -> None:
    """Digita texto convertendo \n em Shift+Enter"""
    lines = text.split("\n")
    
    for i, line in enumerate(lines):
        if line:
            await locator_or_page.type(line, delay=delay)
        if i < len(lines) - 1:
            await locator_or_page.press("Shift+Enter")
            if hasattr(locator_or_page, "page"):
                await locator_or_page.page.wait_for_timeout(25)
            else:
                await asyncio.sleep(0.025)


async def send_image_with_caption(
    page: Page,
    target_chat: str,
    image_path: str,
    caption: str,
    target_group: Optional[str] = None,
    page_ml: Optional[Page] = None,
    max_retries: int = 3,
) -> bool:
    """
    🔥 Imagem + Legenda em 1 bolha - VERSÃO QUE FUNCIONAVA ONTEM
    """
    
    for attempt in range(max_retries):
        try:
            if not image_path or not Path(image_path).exists():
                print(f"✗ Arquivo não existe: {image_path}")
                return False
            
            img = Path(image_path).resolve()
            print(f"\n🔥 [{attempt+1}/{max_retries}] Enviando imagem + legenda")
            print(f" → {img.name}")
            print(f" → {len(caption)} chars ({caption.count(chr(10))} quebras)")
            
            # FIX BUG #4: Verifica retorno de open_chat
            chat_ok = await open_chat(page, target_chat)
            if not chat_ok:
                print(f" ✗ Chat '{target_chat}' não encontrado - abortando envio")
                return False
            await page.wait_for_timeout(1500)
            
            # Adiciona link do grupo no final da legenda
            if GROUP_LINK:
                full_caption = f"{caption}\n\n☑️ Link do grupo: {GROUP_LINK}"
            else:
                full_caption = caption
            
            # ============================================
            # [1/4] CLICAR NO BOTÃO ANEXAR (REFORÇADO)
            # ============================================
            print(" [1/4] Procurando botão Anexar...")
            
            # FIX BUG #3: Reordenado - "attach-menu-plus" primeiro (mais específico)
            attach_selectors = [
                'span[data-icon="attach-menu-plus"]',   # ← mais confiável, específico
                'div[title="Anexar"]',
                'button[aria-label="Anexar"]',
                'div[aria-label="Anexar"]',
                'button[title="Anexar"]',
                'div[data-tab="attach-media"]',
                # span[data-icon="plus"] removido — ambíguo demais
            ]
            
            attach_clicked = False
            for sel in attach_selectors:
                try:
                    attach = page.locator(sel).first
                    if await attach.count() > 0:
                        await attach.click(timeout=3000)
                        await page.wait_for_timeout(1500)
                        print(f" ✓ Clicou em Anexar ({sel})")
                        attach_clicked = True
                        break
                except Exception:
                    continue
            
            if not attach_clicked:
                print(" ✗ Botão Anexar não encontrado!")
                raise RuntimeError("Botão Anexar não encontrado")
            
            # ============================================
            # [2/4] CLICAR EM "FOTOS E VÍDEOS" + UPLOAD (MÉTODO QUE FUNCIONAVA)
            # ============================================
            print(" [2/4] Procurando 'Fotos e vídeos'...")
            
            photo_selectors = [
                'button[aria-label*="Fotos"]',
                'li[aria-label*="Fotos"]',
                'text=Fotos e vídeos',
                'text=Fotos',
                'input[accept="image/*,video/mp4,video/3gpp,video/quicktime"]',
                'span[data-icon="image"]',
                'li:has-text("Fotos e vídeos")',
                'button:has-text("Fotos")',
                'div[role="button"]:has-text("Fotos")',
            ]
            
            photo_clicked = False
            for sel in photo_selectors:
                try:
                    # ✅ SE FOR INPUT FILE, USA DIRETO
                    if 'input[accept' in sel:
                        file_input = page.locator(sel).first
                        if await file_input.count() > 0:
                            # Para input file, usar set_input_files
                            file_handle = await file_input.element_handle()
                            if file_handle:
                                await file_handle.set_input_files(str(img))
                                print(f" ✓ Upload via input file")
                                photo_clicked = True
                                break
                    else:
                        # ✅ MÉTODO QUE FUNCIONAVA: expect_file_chooser
                        elem = page.locator(sel).first
                        if await elem.count() == 0:
                            continue
                        
                        # Verifica se não é "Figurinhas"
                        try:
                            txt = await elem.inner_text(timeout=500)
                            if txt and "figurinha" in txt.lower():
                                continue
                        except Exception:
                            pass
                        
                        # ✅ CLICA E CAPTURA FILE CHOOSER
                        try:
                            async with page.expect_file_chooser(timeout=5000) as fc:
                                await elem.click(timeout=2000)
                                file_chooser = await fc.value
                                await file_chooser.set_files(str(img))
                            
                            print(f" ✓ Upload via file chooser ({sel})")
                            photo_clicked = True
                            break
                        except Exception:
                            continue
                
                except Exception as e:
                    continue
            
            if not photo_clicked:
                print(" ✗ 'Fotos e vídeos' não encontrado!")
                raise RuntimeError("Botão 'Fotos e vídeos' não encontrado")
            
            # ============================================
            # [3/4] INSERIR LEGENDA COM QUEBRAS DE LINHA
            # ============================================
            print(" [3/4] Inserindo legenda...")
            
            await page.wait_for_timeout(2500)
            
            caption_inserted = False
            caption_field_used = None
            
            try:
                fields = await page.locator('[contenteditable="true"]').all()
                print(f" → Encontrados {len(fields)} campos editáveis")
                
                # Testa os últimos 5 campos (do fim para o início)
                for i in range(len(fields) - 1, max(0, len(fields) - 5), -1):
                    field = fields[i]
                    
                    try:
                        visible = await field.is_visible()
                        if not visible:
                            continue
                        
                        bbox = await field.bounding_box()
                        if not bbox or bbox["y"] < 100:
                            continue
                        
                        print(f" → Tentando campo #{i} (y={bbox['y']:.0f})")
                        
                        await field.click(timeout=2000)
                        await page.wait_for_timeout(300)
                        
                        # Limpa campo
                        try:
                            await field.press("Control+A", timeout=500)
                            await field.press("Backspace", timeout=500)
                            await page.wait_for_timeout(200)
                        except Exception:
                            pass
                        
                        # Digita legenda
                        await _type_with_line_breaks(field, full_caption, delay=10)
                        await page.wait_for_timeout(1000)
                        
                        # Verifica se funcionou
                        text_check = await field.inner_text()
                        text_len = len(text_check.strip())
                        
                        if text_len > 20:
                            print(f" ✅ Legenda inserida: {text_len} chars")
                            caption_inserted = True
                            caption_field_used = field
                            break
                        else:
                            print(f" ⊗ Campo #{i} vazio após digitação")
                    
                    except Exception:
                        print(f" ⊗ Campo #{i} erro no processamento")
                        continue

            except Exception:
                print(f" ⚠️ Erro ao buscar campos")
            
            # Fallback: keyboard global
            if not caption_inserted:
                print(" → Tentando keyboard global...")
                try:
                    lines = full_caption.split("\n")
                    for idx, line in enumerate(lines):
                        if line:
                            await page.keyboard.type(line, delay=10)
                        if idx < len(lines) - 1:
                            await page.keyboard.press("Shift+Enter")
                            await page.wait_for_timeout(50)
                    
                    await page.wait_for_timeout(1000)
                    print(" ✓ Legenda digitada via keyboard")
                    caption_inserted = True
                except Exception:
                    print(f" ⚠️ Keyboard falhou")
            
            if not caption_inserted:
                raise RuntimeError("Não conseguiu inserir legenda")
            
            # ============================================
            # [4/4] ENVIAR
            # ============================================
            print(" [4/4] Enviando...")
            
            await page.wait_for_timeout(1000)
            
            sent = False
            
            # Método 1: Enter no campo
            if caption_field_used:
                try:
                    await caption_field_used.press("Enter")
                    await page.wait_for_timeout(2500)
                    print(" ✓ Enviado via Enter no campo")
                    sent = True
                except Exception:
                    print(f" ⚠️ Enter no campo falhou")

            # Método 2: Enter global
            if not sent:
                try:
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(2500)
                    print(" ✓ Enviado via Enter global")
                    sent = True
                except Exception:
                    print(f" ⚠️ Enter global falhou")

            # Método 3: Botão Send
            if not sent:
                try:
                    send = page.locator('span[data-icon="send"]').last
                    await send.click(force=True, timeout=3000)
                    await page.wait_for_timeout(2500)
                    print(" ✓ Enviado via botão Send")
                    sent = True
                except Exception:
                    print(f" ⚠️ Botão Send falhou")
            
            if not sent:
                raise RuntimeError("Nenhum método de envio funcionou")
            
            print("\n ✅✅✅ SUCESSO: Imagem + Legenda enviada!\n")
            return True
        
        except Exception as e:
            print(f"\n ❌ Tentativa {attempt+1} falhou: {str(e)[:150]}\n")
            
            # Cancela anexo com ESC
            try:
                for _ in range(10):
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(300)
            except Exception:
                pass
            
            if attempt < max_retries - 1:
                print(f" → Retry em 4s...\n")
                await asyncio.sleep(4)
            else:
                print(" ❌ FALHA FINAL\n")
                return False
    
    return False