# main.py - VERSÃO FINAL COM CTRL+C/V

import asyncio
import traceback
from playwright.async_api import async_playwright

from config import (
    SOURCE_GROUP,
    TARGET_GROUP,
    POLL_SECONDS,
    DOWNLOAD_DIR,
    MELI_AFFILIATE_TAG,
    MELI_ENABLED,
    AMAZON_AFFILIATE_TAG,
    AMAZON_ENABLED,
    GENERIC_AFFILIATE_TAG,
    GENERIC_ENABLED,
    CHROME_USER_DATA_DIR,
    CHROME_PROFILE_DIR_NAME,
    HEADLESS,
)

from watcher import (
    open_chat,
    extract_last_message_text_and_urls,
    compute_msg_id,
    get_last_message_bubble,
    has_image,
    copy_last_image,
    screenshot_last_image,
)

from extractor import (
    extract_urls_from_text, 
    replace_urls_in_text, 
    identify_platform,
    filter_urls_by_platform
)
from affiliate import generate_affiliate_link as generate_meli_affiliate_link
from affiliate_multi_platform import (
    generate_amazon_affiliate_link,
    generate_aliexpress_affiliate_link,
    generate_shopee_affiliate_link,
    generate_generic_affiliate_link
)
from sender_whatsapp import send_text_message, send_copied_image_with_caption, send_image_with_caption
from storage import load_last_seen, save_last_seen


async def wait_whatsapp_logged(page_w):
    print(">> Aguardando WhatsApp logado...")
    await page_w.goto("https://web.whatsapp.com", wait_until="domcontentloaded")
    await page_w.wait_for_selector("div[contenteditable='true'][data-tab]", timeout=240000)
    print(">> WhatsApp pronto.")


async def process_new_message(page_w, page_m, text: str, hrefs: list[str]) -> bool:
    """🔥 VERSÃO MULTI-PLATAFORMA - Processa links de várias lojas"""
    
    # 1. Extrai todas as URLs
    urls = hrefs[:] if hrefs else []
    if not urls:
        urls = extract_urls_from_text(text)
    
    if not urls:
        print("⚠️ Mensagem sem links - ignorando")
        return True
    
    # 2. Agrupa URLs por plataforma
    urls_by_platform = filter_urls_by_platform(urls)
    
    print(f"\n📊 URLs detectadas por plataforma:")
    for platform, platform_urls in urls_by_platform.items():
        if platform_urls:
            print(f"   • {platform.upper()}: {len(platform_urls)} link(s)")
    
    mapping: dict[str, str] = {}
    product_url = None
    
    # 3. Processa Mercado Livre (com geração de /sec/)
    if MELI_ENABLED and urls_by_platform["mercadolivre"]:
        for u in urls_by_platform["mercadolivre"][:3]:
            # Só processa se for link /sec/ (afiliado ML)
            if "/sec/" in u.lower():
                print(f"\n>> [MERCADO LIVRE] Gerando link afiliado: {u[:60]}...")
                new_u, prod_url = await generate_meli_affiliate_link(page_m, u, MELI_AFFILIATE_TAG)
                if new_u:
                    mapping[u] = new_u
                    product_url = prod_url
                    print(f"   ✓ Link afiliado gerado: {new_u[:60]}...")
                    break
            else:
                print(f"   ⚠️ Link ML sem /sec/ - ignorando: {u[:60]}...")
    
    # 4. Processa Amazon
    if AMAZON_ENABLED and urls_by_platform["amazon"]:
        for u in urls_by_platform["amazon"][:3]:
            print(f"\n>> [AMAZON] Gerando link afiliado: {u[:60]}...")
            new_u = generate_amazon_affiliate_link(u, AMAZON_AFFILIATE_TAG)
            if new_u:
                mapping[u] = new_u
                print(f"   ✓ Link afiliado gerado: {new_u[:60]}...")
    
    # 5. Processa AliExpress
    if GENERIC_ENABLED and urls_by_platform["aliexpress"]:
        for u in urls_by_platform["aliexpress"][:3]:
            print(f"\n>> [ALIEXPRESS] Gerando link afiliado: {u[:60]}...")
            new_u = generate_aliexpress_affiliate_link(u, GENERIC_AFFILIATE_TAG)
            if new_u:
                mapping[u] = new_u
                print(f"   ✓ Link afiliado gerado: {new_u[:60]}...")
    
    # 6. Processa Shopee
    if GENERIC_ENABLED and urls_by_platform["shopee"]:
        for u in urls_by_platform["shopee"][:3]:
            print(f"\n>> [SHOPEE] Gerando link afiliado: {u[:60]}...")
            new_u = generate_shopee_affiliate_link(u, GENERIC_AFFILIATE_TAG)
            if new_u:
                mapping[u] = new_u
                print(f"   ✓ Link afiliado gerado: {new_u[:60]}...")
    
    # 7. Processa Magalu e outros
    if GENERIC_ENABLED and urls_by_platform["magalu"]:
        for u in urls_by_platform["magalu"][:3]:
            print(f"\n>> [MAGALU] Gerando link afiliado: {u[:60]}...")
            new_u = generate_generic_affiliate_link(u, GENERIC_AFFILIATE_TAG, param_name="ref")
            if new_u:
                mapping[u] = new_u
                print(f"   ✓ Link afiliado gerado: {new_u[:60]}...")
    
    # Verifica se gerou algum link
    if not mapping:
        print("\n⚠️ Nenhum link de afiliado foi gerado - enviando texto original")
        # Envia sem modificar (pode comentar esta linha se quiser ignorar)
        # return True

    new_text = replace_urls_in_text(text, mapping)
    
    print(f"\n>> Texto original ({len(text)} chars): {text[:200]}")
    print(f">> Texto com link trocado ({len(new_text)} chars): {new_text[:200]}")
    
    if not new_text or len(new_text.strip()) == 0:
        print("⚠️ ERRO: Texto vazio após substituição!")
        new_text = text

    # 🔥 COPIA IMAGEM DA MENSAGEM ORIGINAL (se tiver)
    bubble = await get_last_message_bubble(page_w)
    has_img = await has_image(bubble)
    img_copied = False
    
    if has_img:
        print("\n>> Mensagem tem IMAGEM")
        print("   → Copiando imagem da mensagem original...")
        img_copied = await copy_last_image(page_w)
        
        if not img_copied:
            print("   ⚠️ Falhou copiar imagem com Ctrl+C")

    # Volta para WhatsApp
    await page_w.bring_to_front()
    await page_w.wait_for_timeout(500)

    # Envia
    if img_copied and new_text.strip():
        print(f"\n>> Enviando IMAGEM COPIADA + LEGENDA para: {TARGET_GROUP}")
        print(f"   Legenda: {new_text[:100]}...")
        # 🔥 USA CTRL+V PARA COLAR A IMAGEM
        ok = await send_copied_image_with_caption(page_w, TARGET_GROUP, new_text)
        if not ok:
            print("⚠️ Falhou enviar com Ctrl+V, tentando só texto...")
            ok = await send_text_message(page_w, TARGET_GROUP, new_text)
        return ok
    
    if new_text.strip():
        print(f"\n>> Enviando TEXTO para: {TARGET_GROUP}")
        return await send_text_message(page_w, TARGET_GROUP, new_text)
    
    print("⚠️ Nada para enviar (texto vazio)")
    return False

async def monitoring_loop(page_w, page_m):
    last_seen = load_last_seen()
    print(f">> Último ID visto: {last_seen or 'nenhum'}")
    print(f">> Abrindo grupo origem: {SOURCE_GROUP}")
    await open_chat(page_w, SOURCE_GROUP)

    print("\n" + "=" * 70)
    print("🤖 BOT INICIADO - Monitorando novas mensagens...")
    print("=" * 70 + "\n")

    while True:
        try:
            # 🔥 SCROLL até o fim para garantir que vê a última mensagem
            try:
                await page_w.keyboard.press("End")
                await page_w.wait_for_timeout(300)
            except Exception:
                pass
            
            text, hrefs = await extract_last_message_text_and_urls(page_w)
            if not text and not hrefs:
                await asyncio.sleep(POLL_SECONDS)
                continue

            msg_id = compute_msg_id(text, hrefs)
            if msg_id == last_seen:
                await asyncio.sleep(POLL_SECONDS)
                continue

            print("\n" + "─" * 62)
            print("📨 NOVA MENSAGEM DETECTADA!")
            print("─" * 62)
            print(f"ID: {msg_id}")
            print(f">> Texto ({len(text)} chars):\n{text}\n")

            ok = await process_new_message(page_w, page_m, text, hrefs)
            if ok:
                last_seen = msg_id
                save_last_seen(msg_id)
                print(f"✓ ID salvo: {msg_id}")
            else:
                print("⚠️ Mensagem não processada - ID não será salvo")

            # Volta pro grupo origem
            await open_chat(page_w, SOURCE_GROUP)

        except Exception as e:
            print(f"❌ ERRO no loop: {e}")
            traceback.print_exc()
        
        await asyncio.sleep(POLL_SECONDS)


async def run():
    print(">> Iniciando bot...")
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            CHROME_USER_DATA_DIR,
            channel="chrome",
            headless=HEADLESS,
            args=[
                f"--profile-directory={CHROME_PROFILE_DIR_NAME}",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        page_w = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await wait_whatsapp_logged(page_w)

        page_m = await ctx.new_page()
        try:
            await page_m.goto("https://www.mercadolivre.com.br/afiliados", wait_until="domcontentloaded", timeout=60000)
        except Exception:
            pass

        await monitoring_loop(page_w, page_m)


if __name__ == "__main__":
    asyncio.run(run())