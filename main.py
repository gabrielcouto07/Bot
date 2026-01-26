# main.py - VERSÃO FINAL COM CTRL+C/V

import asyncio
import traceback
from playwright.async_api import async_playwright

from config import (
    TARGET_GROUP,
    POLL_SECONDS,
    DOWNLOAD_DIR,
    MELI_AFFILIATE_TAG,
    CHROME_USER_DATA_DIR,
    CHROME_PROFILE_DIR_NAME,
    HEADLESS,
)

# Suporta modo single (SOURCE_GROUP) ou múltiplo (SOURCE_GROUPS)
try:
    from config import SOURCE_GROUPS
    if not isinstance(SOURCE_GROUPS, list):
        SOURCE_GROUPS = [SOURCE_GROUPS]
except ImportError:
    from config import SOURCE_GROUP
    SOURCE_GROUPS = [SOURCE_GROUP]

from watcher import (
    open_chat,
    extract_last_message_text_and_urls,
    compute_msg_id,
    get_last_message_bubble,
    has_image,
    screenshot_last_image,
    detect_chat_type,
)

from extractor import extract_urls_from_text, replace_urls_in_text
from affiliate import generate_affiliate_link, download_product_image
from sender_whatsapp import send_text_message, send_image_with_caption
from storage import (
    load_last_seen, 
    save_last_seen,
    load_last_seen_multi,
    save_last_seen_multi,
    update_last_seen_for_source,
)


async def wait_whatsapp_logged(page_w):
    print(">> Aguardando WhatsApp logado...")
    await page_w.goto("https://web.whatsapp.com", wait_until="domcontentloaded")
    await page_w.wait_for_selector("div[contenteditable='true'][data-tab]", timeout=240000)
    print(">> WhatsApp pronto.")


def _filter_meli_sec(urls: list[str]) -> list[str]:
    out = []
    for u in urls or []:
        low = (u or "").lower()
        if "mercadolivre" in low and "/sec/" in low:
            out.append(u)
    return out

async def process_new_message(page_w, page_m, text: str, hrefs: list[str]) -> bool:
    urls = hrefs[:] if hrefs else []
    if not urls:
        urls = extract_urls_from_text(text)
    
    meli_urls = _filter_meli_sec(urls)
    if not meli_urls:
        print("⚠️ Mensagem sem link /sec/ do Mercado Livre - ignorando")
        return True

    mapping: dict[str, str] = {}
    product_url = None
    
    for u in meli_urls[:3]:
        print(f">> Gerando link afiliado para: {u}")
        new_u, prod_url = await generate_affiliate_link(page_m, u, MELI_AFFILIATE_TAG)
        if new_u:
            mapping[u] = new_u
            product_url = prod_url
            break

    if not mapping:
        print("✗ Falha ao gerar link afiliado")
        return False

    new_text = replace_urls_in_text(text, mapping)
    
    print(f"\n>> Texto original ({len(text)} chars): {text[:200]}")
    print(f">> Texto com link trocado ({len(new_text)} chars): {new_text[:200]}")
    
    if not new_text or len(new_text.strip()) == 0:
        print("⚠️ ERRO: Texto vazio após substituição!")
        new_text = text

    # 🔥 BAIXA IMAGEM DO ML (se mensagem tiver imagem)
    bubble = await get_last_message_bubble(page_w)
    img_path = None
    
    if await has_image(bubble):
        print("\n>> Mensagem tem IMAGEM")
        
        if product_url:
            print(f"   → Baixando imagem de: {product_url[:80]}...")
            img_path = await download_product_image(page_m, product_url, DOWNLOAD_DIR)
        
        if not img_path:
            print("   ⚠️ Falhou baixar do ML, tentando WhatsApp...")
            img_path = await screenshot_last_image(page_w, DOWNLOAD_DIR)
        
        if img_path:
            print(f"   ✓ Imagem salva: {img_path}")
        else:
            print("   ⚠️ Sem imagem (vai enviar só texto)")

    # Volta para WhatsApp
    await page_w.bring_to_front()
    await page_w.wait_for_timeout(800)

    # Envia
    if img_path and new_text.strip():
        print(f"\n>> Enviando IMAGEM + LEGENDA para: {TARGET_GROUP}")
        print(f"   Legenda: {new_text[:100]}...")
        # 🔥 PASSA O CAMINHO DO ARQUIVO (não page_ml)
        ok = await send_image_with_caption(page_w, TARGET_GROUP, img_path, new_text)
        if not ok:
            print("⚠️ Falhou enviar imagem+legenda, tentando só texto...")
            ok = await send_text_message(page_w, TARGET_GROUP, new_text)
        return ok
    
    if new_text.strip():
        prcheck_source(page_w, page_m, source_name: str, last_seen_id: str | None) -> str | None:
    """
    Verifica uma fonte específica (canal/grupo) por novas mensagens.
    Retorna novo msg_id se processou com sucesso, ou None.
    """
    try:
        # Abre o chat da fonte
        await open_chat(page_w, source_name)
        await page_w.wait_for_timeout(500)
        
        # Extrai última mensagem
        text, hrefs = await extract_last_message_text_and_urls(page_w)
        if not text and not hrefs:
            return None

        msg_id = compute_msg_id(text, hrefs)
        
        # Se já vimos essa mensagem, pula
        if msg_id == last_seen_id:
            return None

        print("\n" + "─" * 62)
        print(f"📨 NOVA MENSAGEM em: {source_name}")
        print("─" * 62)
        print(f"ID: {msg_id}")
        print(f">> Texto ({len(text)} chars):\n{text}\n")

        # Processa mensagem
        ok = await process_new_message(page_w, page_m, text, hrefs)
        
        if ok:
            print(f"✓ Mensagem de '{source_name}' processada com sucesso")
            return msg_id
        else:
            print(f"⚠️ Falha ao processar mensagem de '{source_name}'")
            return None
            
    except Exception as e:
        print(f"❌ ERRO ao verificar '{source_name}': {e}")
        return None


async def monitoring_loop(page_w, page_m):
    """Monitora múltiplas fontes (canais/grupos) simultaneamente"""
    
    # Carrega estado (último ID visto por fonte)
    if len(SOURCE_GROUPS) == 1:
        # Modo compatibilidade: single source
        last_seen = load_last_seen()
        state = {SOURCE_GROUPS[0]: last_seen} if last_seen else {}
    else:
        # Modo múltiplas fontes
        state = load_last_seen_multi()
    
    print("\n" + "=" * 70)
    print(f"🤖 BOT INICIADO - Monitorando {len(SOURCE_GROUPS)} fonte(s):")
    print("=" * 70)
    
    for i, source in enumerate(SOURCE_GROUPS, 1):
        last_id = state.get(source, "nenhum")
        print(f"  {i}. {source}")
        print(f"     └─ Último ID: {last_id}")
        
        # Abre cada fonte uma vez para detectar tipo
        try:
            await open_chat(page_w, source)
            chat_type = await detect_chat_type(page_w)
            print(f"     └─ Tipo: {chat_type.upper()}")
        except Exception as e:
            print(f"     └─ ⚠️ Erro ao abrir: {e}")
    
    print("=" * 70 + "\n")
    print(f"🔄 Iniciando monitoramento a cada {POLL_SECONDS}s...\n")

    while True:
        try:
            # Itera por todas as fontes
            for source_name in SOURCE_GROUPS:
                last_seen_id = state.get(source_name)
                
                # Verifica se há nova mensagem nesta fonte
                new_id = await check_source(page_w, page_m, source_name, last_seen_id)
                
                # Se processou com sucesso, atualiza estado
                if new_id:
                    state[source_name] = new_id
                    
                    # Salva estado
                    if len(SOURCE_GROUPS) == 1:
                        save_last_seen(new_id)
                    else:
                        save_last_seen_multi(state)
                    
                    print(f"✓ Estado atualizado para '{source_name}': {new_id}")
                
                # Pequeno delay entre fontes
                await asyncio.sleep(0.5)
            
            # Delay antes do próximo ciclo completo
            await asyncio.sleep(POLL_SECONDS)

        except Exception as e:
            print(f"❌ ERRO no loop principal: {e}")
            traceback.print_exc()
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