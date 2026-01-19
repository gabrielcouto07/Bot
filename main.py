# main.py
import asyncio
from playwright.async_api import async_playwright

from config import SOURCE_GROUP, TARGET_GROUP, POLL_SECONDS
from watcher import open_chat, extract_last_message_text_and_urls, compute_msg_id
from extractor import extract_urls_from_text, replace_urls_in_text
from affiliate import generate_affiliate_link
from sender_whatsapp import send_text_message
from storage import load_last_seen, save_last_seen

CHROME_USER_DATA_DIR = r"C:\Users\GABRIEL.CARDOSO\AppData\Local\BotChromeProfile"
CHROME_PROFILE_DIR_NAME = "Default"


async def wait_whatsapp_logged(page_w):
    print(">> Aguardando WhatsApp logado...")
    await page_w.goto("https://web.whatsapp.com/", wait_until="domcontentloaded", timeout=60000)
    await page_w.wait_for_selector("div[contenteditable='true'][data-tab]", timeout=180000)
    print(">> WhatsApp pronto.")


async def process_new_message(page_w, page_m, text, urls):
    """Processa uma mensagem: gera links afiliados e envia para o grupo destino."""
    
    print(f">> Processando mensagem. URLs encontradas: {len(urls)}")
    for u in urls:
        print(f"   - {u}")

    if not urls:
        print("⚠️ Mensagem sem URLs - ignorando")
        return False

    # Gera links afiliados
    mapping = {}
    for u in urls:
        print(f">> Gerando link afiliado para: {u}")
        aff = await generate_affiliate_link(page_m, u)
        if aff:
            print(f"   ✓ Link afiliado gerado: {aff[:60]}...")
            mapping[u] = aff
        else:
            print(f"   ✗ Falha ao gerar link afiliado")

    if not mapping:
        print("⚠️ Nenhum link afiliado gerado - ignorando mensagem")
        return False

    # Substitui URLs no texto
    new_text = replace_urls_in_text(text, mapping)

    print(f">> Enviando mensagem para: {TARGET_GROUP}")
    
    # Tenta enviar (com retry)
    ok_send = await send_text_message(page_w, TARGET_GROUP, new_text, open_chat)
    if not ok_send:
        print("⚠️ Primeira tentativa falhou, tentando novamente...")
        await asyncio.sleep(2)
        ok_send = await send_text_message(page_w, TARGET_GROUP, new_text, open_chat)

    if ok_send:
        print("✓ Mensagem enviada com sucesso!")
        return True
    else:
        print("✗ Falha ao enviar mensagem")
        return False


async def monitoring_loop(page_w, page_m):
    """Loop principal que monitora novas mensagens."""
    
    last_seen = load_last_seen()
    print(f">> Último ID visto: {last_seen or 'nenhum'}")
    
    print(f">> Abrindo grupo origem: {SOURCE_GROUP}")
    await open_chat(page_w, SOURCE_GROUP)
    
    print(f"\n{'='*60}")
    print("🤖 BOT INICIADO - Monitorando novas mensagens...")
    print(f"{'='*60}\n")
    
    while True:
        try:
            # Extrai última mensagem
            text, href_urls = await extract_last_message_text_and_urls(page_w)
            text_urls = extract_urls_from_text(text)
            
            # Combina URLs (dedupe)
            urls = []
            seen = set()
            for u in (href_urls + text_urls):
                if u and u not in seen:
                    seen.add(u)
                    urls.append(u)
            
            # Calcula ID da mensagem
            msg_id = compute_msg_id(text)
            
            # Verifica se é nova
            if msg_id != last_seen:
                print(f"\n{'─'*60}")
                print(f"📨 NOVA MENSAGEM DETECTADA!")
                print(f"{'─'*60}")
                print(f"Texto (primeiros 200 chars): {text[:200]}")
                print(f"ID: {msg_id}")
                
                # Processa a mensagem
                success = await process_new_message(page_w, page_m, text, urls)
                
                if success:
                    # Atualiza last_seen apenas se processou com sucesso
                    last_seen = msg_id
                    save_last_seen(msg_id)
                    print(f"✓ ID salvo: {msg_id}")
                else:
                    print(f"⚠️ Mensagem não processada - ID não será salvo")
                
                print(f"{'─'*60}\n")
                
                # Volta para o grupo origem após enviar
                await asyncio.sleep(1)
                await open_chat(page_w, SOURCE_GROUP)
            
            # Aguarda antes de verificar novamente
            await asyncio.sleep(POLL_SECONDS)
            
        except KeyboardInterrupt:
            print("\n\n⛔ Bot interrompido pelo usuário")
            break
        except Exception as e:
            print(f"\n❌ ERRO no loop: {e}")
            print(">> Tentando continuar em 5 segundos...")
            await asyncio.sleep(5)
            
            # Tenta reabrir o grupo origem
            try:
                await open_chat(page_w, SOURCE_GROUP)
            except Exception:
                pass


async def run():
    async with async_playwright() as p:
        print(">> Iniciando bot...")

        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=CHROME_USER_DATA_DIR,
            channel="chrome",
            headless=False,
            args=[
                f"--profile-directory={CHROME_PROFILE_DIR_NAME}",
                "--start-maximized",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-popup-blocking",
                "--disable-notifications",
            ],
        )

        page_w = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await wait_whatsapp_logged(page_w)

        # Abre página do Mercado Livre (reutilizada para todos os links)
        page_m = await ctx.new_page()

        # Inicia loop de monitoramento
        await monitoring_loop(page_w, page_m)


if __name__ == "__main__":
    asyncio.run(run())