# main.py

import asyncio
import traceback
import random
import os
import logging
import re
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

from config_example import (
    CHANNEL_PAIRS,
    POLL_SECONDS,
    DOWNLOAD_DIR,
    MELI_AFFILIATE_TAG,
    CHROME_USER_DATA_DIR,
    CHROME_PROFILE_DIR_NAME,
    HEADLESS,
    SUPERHERO_EMOJI,
    GATILHOS,
    GATILHO_CHANCE,
)

from watcher import (
    open_chat,
    extract_last_message_text_and_urls,
    compute_msg_id,
    get_last_message_bubble,
    has_image,
    screenshot_last_image,
)

from extractor import extract_urls_from_text, replace_urls_in_text, format_old_price_with_strikethrough
from affiliate import generate_affiliate_link, download_product_image
from sender_whatsapp import send_text_message, send_image_with_caption
from storage import load_last_seen, save_last_seen

# ====================================
# 🔥 SISTEMA DE LOGS ESTRUTURADO
# ====================================
def setup_logger():
    """Configura sistema de logs em arquivo + console"""
    log_dir = Path("./logs")
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / f"bot_{datetime.now().strftime('%Y%m%d')}.log"

    logger = logging.getLogger("BotAfiliados")
    logger.setLevel(logging.INFO)

    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.info(f"✅ Sistema de logs iniciado: {log_file}")
    return logger


logger = setup_logger()


# ====================================
# 🔥 PROCESSAMENTO DE TEXTO COM GATILHOS
# ====================================
def process_text_enhancements(text: str) -> str:
    """Remove emoji indesejado e adiciona gatilho aleatório (20% chance)"""
    if not text:
        return text

    original_len = len(text)
    text = text.replace(SUPERHERO_EMOJI, "").strip()

    if len(text) < original_len:
        logger.info(f"   🧹 Removido emoji {SUPERHERO_EMOJI}")

    if random.random() < GATILHO_CHANCE:
        gatilho = random.choice(GATILHOS)
        text = f"{gatilho}\n\n{text}"
        logger.info(f"   🎯 Gatilho adicionado: {gatilho}")

    return text


async def wait_whatsapp_logged(page_w):
    logger.info(">> Aguardando WhatsApp logado...")
    await page_w.goto("https://web.whatsapp.com", wait_until="domcontentloaded")
    await page_w.wait_for_selector(
        "div[contenteditable='true'][data-tab]", timeout=240000
    )
    logger.info(">> WhatsApp pronto ✓")


def _filter_meli_sec(urls: list[str]) -> list[str]:
    """Filtra apenas links /sec/ do Mercado Livre (otimizado com regex)"""
    if not urls:
        return []
    meli_sec_pattern = re.compile(r'mercadolivre.*?/sec/', re.IGNORECASE)
    return [u for u in urls if u and meli_sec_pattern.search(u)]


def _cleanup_temp_images(download_dir: str):
    """Remove imagens temporárias antigas"""
    try:
        temp_dir = Path(download_dir)
        if not temp_dir.exists():
            return

        for img_file in temp_dir.glob("*.jpg"):
            try:
                img_file.unlink()
                logger.debug(f"   🗑️ Imagem temporária deletada: {img_file.name}")
            except Exception as e:
                logger.warning(f"   ⚠️ Erro ao deletar {img_file.name}: {e}")
    except Exception as e:
        logger.warning(f"   ⚠️ Erro ao limpar imagens temporárias: {e}")


async def process_new_message(
    page_w,
    page_m,
    text: str,
    hrefs: list[str],
    source_name: str,
    target_name: str,
) -> bool:
    """Processa mensagem nova: gera afiliado, aplica gatilhos e envia"""

    urls = hrefs[:] if hrefs else []
    if not urls:
        urls = extract_urls_from_text(text)

    meli_urls = _filter_meli_sec(urls)

    if not meli_urls:
        logger.warning(
            f"⚠️ [{source_name}] Mensagem sem link /sec/ do Mercado Livre - ignorando"
        )
        return True

    mapping: dict[str, str] = {}
    product_url = None

    for u in meli_urls[:3]:
        logger.info(f">> [{source_name}] Gerando link afiliado para: {u[:60]}...")
        new_u, prod_url = await generate_affiliate_link(
            page_m, u, MELI_AFFILIATE_TAG
        )
        if new_u:
            mapping[u] = new_u
            product_url = prod_url
            logger.info(f"   ✅ Link afiliado gerado: {new_u}")
            break

    if not mapping:
        logger.error(
            f"❌ [{source_name}] Falha ao gerar link afiliado - mensagem NÃO será enviada"
        )
        return False

    enhanced_text = process_text_enhancements(text)
    new_text = replace_urls_in_text(enhanced_text, mapping)

    new_text = format_old_price_with_strikethrough(new_text)

    logger.info(
        f">> [{source_name}] Texto processado: {len(text)} → {len(new_text)} chars"
    )

    if not new_text or len(new_text.strip()) == 0:
        logger.error(f"❌ [{source_name}] Texto vazio após processamento!")
        new_text = text

    bubble = await get_last_message_bubble(page_w)
    img_path = None

    if await has_image(bubble):
        logger.info(f">> [{source_name}] Mensagem tem IMAGEM")

        if product_url:
            logger.info(f"   → Tentando baixar de: {product_url[:60]}...")
            # 🚀 Paralelizar: baixar ML E screenshot simultaneamente com timeout
            tasks = [
                asyncio.create_task(download_product_image(page_m, product_url, DOWNLOAD_DIR)),
                asyncio.create_task(screenshot_last_image(page_w, DOWNLOAD_DIR)),
            ]
            done, pending = await asyncio.wait(tasks, timeout=8, return_when=asyncio.FIRST_COMPLETED)
            
            for task in done:
                result = await task
                if result:
                    img_path = result
                    break
            
            # Cancelar tasks pendentes
            for task in pending:
                task.cancel()

        if not img_path:
            logger.warning("   ⚠️ Falhou em ambas, tentando screenshot direto...")
            img_path = await screenshot_last_image(page_w, DOWNLOAD_DIR)

        if img_path:
            logger.info(f"   ✓ Imagem salva: {img_path}")

    await page_w.bring_to_front()
    await page_w.wait_for_timeout(300)  # ⚡ Reduzido de 800ms

    logger.info(f">> [{source_name}] Enviando para: {target_name}")
    ok = False

    if img_path and new_text.strip():
        ok = await send_image_with_caption(page_w, target_name, img_path, new_text, target_group=target_name)
        if not ok:
            logger.warning("   ⚠️ Falhou enviar imagem, tentando só texto...")
            ok = await send_text_message(page_w, target_name, new_text, target_group=target_name)
    elif new_text.strip():
        ok = await send_text_message(page_w, target_name, new_text, target_group=target_name)
    else:
        logger.error(f"❌ [{source_name}] Sem conteúdo para enviar!")
        ok = False

    if img_path and os.path.exists(img_path):
        try:
            os.remove(img_path)
            logger.info(
                f"   🗑️ Imagem temporária deletada: {Path(img_path).name}"
            )
        except Exception as e:
            logger.warning(f"   ⚠️ Erro ao deletar imagem: {e}")

    if ok:
        logger.info(
            f"✅ [{source_name}] Enviado com sucesso para [{target_name}]!"
        )
    else:
        logger.error(
            f"❌ [{source_name}] Falhou ao enviar para [{target_name}]"
        )

    return ok


async def monitoring_loop(page_w, page_m):
    """
    🔥 Monitora múltiplos grupos em ROUND-ROBIN 3x3 (Source → Target pareado)
    """

    last_seen_dict = {}

    logger.info("\n" + "=" * 80)
    logger.info("🤖 BOT INICIADO - Round-Robin 3x3 (Source → Target Pareado)")
    logger.info("=" * 80)

    for source_group, target_group, description in CHANNEL_PAIRS:
        last_seen_dict[source_group] = load_last_seen(source_group)

        logger.info(f"📍 {description}")
        logger.info(f"   Source: {source_group}")
        logger.info(f"   Target: {target_group}")

        if last_seen_dict[source_group]:
            logger.info(
                f"   Último ID: {last_seen_dict[source_group][:16]}..."
            )
        else:
            logger.info("   Último ID: nenhum (primeira execução)")

    logger.info(f"⏱️ Ciclo: Verificar todos os grupos uma vez, depois pausar 5 minutos")
    logger.info("💾 Estado: state_last_seen.txt")
    logger.info("=" * 80 + "\n")

    while True:
        try:
            # ✅ Verificar TODOS os grupos uma vez
            for source_group, target_group, description in CHANNEL_PAIRS:
                try:
                    logger.info(f"\n🔍 [{description}] Verificando: {source_group}...")

                    await open_chat(page_w, source_group)
                    await page_w.wait_for_timeout(300)

                    text, hrefs = await extract_last_message_text_and_urls(page_w)

                    if text or hrefs:
                        msg_id = compute_msg_id(text, hrefs)

                        if msg_id != last_seen_dict.get(source_group):
                            logger.info("\n" + "─" * 70)
                            logger.info(
                                f"📨 [{source_group}] NOVA MENSAGEM DETECTADA!"
                            )
                            logger.info("─" * 70)
                            logger.info(f"ID atual: {msg_id[:16]}...")

                            if last_seen_dict.get(source_group):
                                logger.info(
                                    f"ID anterior: {last_seen_dict[source_group][:16]}..."
                                )
                            else:
                                logger.info("ID anterior: nenhum")

                            preview = text[:100] if text else ""
                            if len(text) > 100:
                                preview += "..."
                            logger.info(f"Texto ({len(text)} chars): {preview}")

                            ok = await process_new_message(
                                page_w,
                                page_m,
                                text,
                                hrefs,
                                source_group,
                                target_group,
                            )

                            if ok:
                                last_seen_dict[source_group] = msg_id
                                preview_short = text[:50] if text else ""
                                save_last_seen(msg_id, source_group, preview_short)
                                logger.info(
                                    f"✅ [{source_group}] ID salvo - mensagem NÃO será reprocessada"
                                )
                            else:
                                logger.warning(
                                    f"⚠️ [{source_group}] Mensagem não enviada - ID NÃO foi salvo (tentará novamente)"
                                )
                        else:
                            logger.info("   ✓ Sem novas mensagens (ID já processado)")
                    else:
                        logger.info("   ✓ Sem mensagens no grupo")

                except Exception as e:
                    logger.error(f"❌ Erro ao verificar {source_group}: {e}")
                    logger.error(traceback.format_exc())

            # ⏸️ PAUSA DE 3 MINUTOS após verificar todos os grupos
            logger.info("\n" + "=" * 80)
            logger.info("⏸️ Ciclo completo! Pausando por 3 minutos...")
            logger.info("=" * 80 + "\n")
            await asyncio.sleep(180)  # 3 minutos = 180 segundos

        except Exception as e:
            logger.error(f"❌ Erro no loop principal: {e}")
            logger.error(traceback.format_exc())
            await asyncio.sleep(60)  # Espera 1 minuto antes de retry
            logger.error(traceback.format_exc())
            await asyncio.sleep(60)  # Espera 1 minuto antes de retry em caso de erro fatal


async def run():
    logger.info(">> Iniciando bot...")

    _cleanup_temp_images(DOWNLOAD_DIR)

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            CHROME_USER_DATA_DIR,
            channel="chrome",
            headless=HEADLESS,  # True = invisível, False = visível
            args=[
                f"--profile-directory={CHROME_PROFILE_DIR_NAME}",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",  # Fix para crashes
                "--no-sandbox",  # Required para alguns servidores
                "--disable-setuid-sandbox",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ],
            ignore_default_args=["--enable-automation"],  # Hide automation flag
        )

        page_w = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await wait_whatsapp_logged(page_w)

        page_m = await ctx.new_page()
        try:
            await page_m.goto(
                "https://www.mercadolivre.com.br/afiliados",
                wait_until="domcontentloaded",
                timeout=60000,
            )
            logger.info("✅ Mercado Livre logado")
        except Exception as e:
            logger.warning(
                f"⚠️ Erro ao abrir ML (login pode ser necessário): {e}"
            )

        await monitoring_loop(page_w, page_m)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("\n>> Bot interrompido pelo usuário (Ctrl+C)")
    except Exception as e:
        logger.critical(f"\n❌ ERRO FATAL: {e}")
        logger.critical(traceback.format_exc())