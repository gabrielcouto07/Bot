# sender_whatsapp.py - ENVIA COMO FOTO (NÃO STICKER)

import asyncio
from pathlib import Path
from playwright.async_api import TimeoutError as PWTimeout
from watcher import open_chat

async def _wait_message_box(page):
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


async def send_text_message(page, target_chat: str, text: str, skip_open_chat: bool = False) -> bool:
    """
    Envia mensagem de texto simples (FUNCIONA 100% - NÃO MEXER)
    skip_open_chat: Se True, não reabre o chat (já está no lugar certo)
    """
    try:
        if not skip_open_chat:
            await open_chat(page, target_chat)
        
        box = await _wait_message_box(page)
        await box.click()
        await page.wait_for_timeout(300)
        await box.fill(text or "")
        await page.wait_for_timeout(200)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(700)
        return True
    except Exception as e:
        print(f"✗ Falha ao enviar texto: {e}")
        return False


async def send_image_only(page, target_chat: str, image_path: str, max_retries: int = 2) -> bool:
    """
    🔥 Envia imagem usando botão ANEXAR (garante que vai como FOTO, não sticker)
    """
    for attempt in range(max_retries):
        try:
            if not image_path or not Path(image_path).exists():
                print(f"✗ Arquivo não existe: {image_path}")
                return False
            
            img = Path(image_path).resolve()
            print(f"   → Enviando imagem: {img.name}")
            
            # 1. Abre chat
            await open_chat(page, target_chat)
            await page.wait_for_timeout(800)
            
            # 2. 🔥 CLICA NO BOTÃO ANEXAR (clipe/+)
            print(f"   → Clicando botão anexar...")
            attach_selectors = [
                'span[data-icon="plus"]',
                'span[data-icon="attach-menu-plus"]',
                'span[data-icon="clip"]',
                'div[title="Anexar"]',
            ]
            
            attach_btn = None
            for selector in attach_selectors:
                try:
                    loc = page.locator(selector).first
                    if await loc.count() > 0:
                        attach_btn = loc
                        print(f"   ✓ Botão encontrado: {selector}")
                        break
                except Exception:
                    continue
            
            if not attach_btn:
                raise RuntimeError("Botão anexar não encontrado")
            
            await attach_btn.click()
            await page.wait_for_timeout(1000)
            
            # 3. 🔥 ESCOLHE INPUT CORRETO (foto/vídeo, NÃO sticker)
            print(f"   → Selecionando input de FOTO/VÍDEO...")
            
            # Procura input que aceita IMAGE E VIDEO (não só image = sticker)
            file_input = page.locator("input[accept*='image'][accept*='video']").first
            
            if await file_input.count() == 0:
                # Fallback: pega o ÚLTIMO input que aceita image (pula sticker)
                all_img_inputs = await page.locator("input[accept*='image']").all()
                if len(all_img_inputs) > 1:
                    file_input = all_img_inputs[-1]  # Último (não primeiro/sticker)
                    print(f"   ⚠️ Usando último input (fallback)")
                elif len(all_img_inputs) == 1:
                    file_input = all_img_inputs[0]
                    print(f"   ⚠️ Usando único input disponível")
                else:
                    raise RuntimeError("Nenhum input file encontrado")
            else:
                print(f"   ✓ Input de FOTO/VÍDEO encontrado")
            
            # 4. Define arquivo
            print(f"   → Carregando arquivo...")
            await file_input.set_input_files(str(img))
            
            # 5. Aguarda preview aparecer
            print(f"   → Aguardando preview...")
            await page.wait_for_timeout(2500)
            
            # 6. Envia (botão verde com aviãozinho ou Enter)
            print(f"   → Enviando...")
            
            # Tenta clicar no botão enviar
            send_btn = page.locator("span[data-icon='send']").last
            
            try:
                if await send_btn.count() > 0 and await send_btn.is_visible(timeout=2000):
                    await send_btn.click()
                    print(f"   ✓ Clicou no botão enviar")
                else:
                    await page.keyboard.press("Enter")
                    print(f"   ✓ Enviou com Enter")
            except Exception:
                await page.keyboard.press("Enter")
                print(f"   ✓ Enviou com Enter (fallback)")
            
            await page.wait_for_timeout(2000)
            
            print(f"   ✅ Imagem enviada como FOTO!")
            return True

        except Exception as e:
            print(f"✗ Falha (tentativa {attempt+1}/{max_retries}): {e}")
            
            # Fecha qualquer modal aberto
            try:
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(500)
            except Exception:
                pass
            
            if attempt < max_retries - 1:
                print(f"   → Tentando novamente em 2s...")
                await asyncio.sleep(2)
                continue

    return False


async def send_image_with_caption(page, target_chat: str, image_path: str, caption: str, page_ml=None, max_retries: int = 2) -> bool:
    """
    Envia imagem + texto em mensagens separadas (mais confiável)
    """
    try:
        # 1) Envia imagem
        print(f"\n   → [1/2] Enviando IMAGEM...")
        img_ok = await send_image_only(page, target_chat, image_path, max_retries=2)
        
        if not img_ok:
            print(f"   ⚠️ Falhou enviar imagem")
            return False
        
        # Aguarda imagem ser enviada
        await page.wait_for_timeout(1500)
        
        # 2) Envia texto (sem reabrir chat - já está no lugar)
        print(f"\n   → [2/2] Enviando TEXTO...")
        text_ok = await send_text_message(page, target_chat, caption, skip_open_chat=True)
        
        if text_ok:
            print(f"   ✅ Imagem + Texto enviados com sucesso!")
            return True
        else:
            print(f"   ⚠️ Imagem enviada, mas texto falhou")
            return True  # Considera sucesso parcial
        
    except Exception as e:
        print(f"✗ Erro: {e}")
        return False