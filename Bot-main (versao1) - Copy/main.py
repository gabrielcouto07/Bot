import asyncio
import traceback
import random
import os
import sys
import logging
import re
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright
from config import (
    BUBBLE_REFRESH_DELAY,
    CHANNEL_PAIRS,
    DOWNLOAD_DIR,
    MELI_AFFILIATE_TAG,
    CHROME_USER_DATA_DIR,
    AMAZON_AFFILIATE_TAG,
    AMAZON_ENABLED,
    CHROME_PROFILE_DIR_NAME,
    HEADLESS,
    SUPERHERO_EMOJI,
    GATILHOS,
    GATILHO_CHANCE,
    POLL_SECONDS,
    RESTART_EVERY_CYCLES,
    CYCLE_TIMEOUT_SECONDS,
    SLEEP_GRANULARITY_SECONDS,
    NIGHT_MODE_ENABLED,
    NIGHT_START_HOUR,
    NIGHT_END_HOUR,
    GROUP_LINK,
    LOG_CLEANUP_CYCLES,
    ML_PROFILES,
    ML_ROTATION_MINUTES,
)
from watcher import (
    open_chat,
    extract_last_message_text_and_urls,
    compute_msg_id,
    get_last_message_bubble,
    has_image,
    download_last_image,
    get_last_message_bubble,
)
from extractor import (
    extract_urls_from_text,
    replace_urls_in_text,
    filter_amazon_urls,
    format_old_price_with_strikethrough,
)
from affiliate import generate_affiliate_link, generate_amazon_affiliate_link_async
from sender_whatsapp import send_image_with_caption
from storage import get_last_seen as load_last_seen, save_last_seen
from ml_rotation import MLRotationManager

# Flag de primeiro teste (roda 1 link por perfil sem esperar 30 min)
FIRST_TEST = "--first-test" in sys.argv

# Variável global para rastrear o arquivo de log atual
CURRENT_LOG_FILE = None

def setup_logger():
    global CURRENT_LOG_FILE
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Cria nome novo com timestamp
    log_file = log_dir / f"bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    CURRENT_LOG_FILE = log_file  # Salva referência para deletar depois
    
    logger = logging.getLogger("BotAfiliados")
    logger.setLevel(logging.INFO)
    
    # Limpa handlers anteriores para não duplicar logs na rotação
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

def rotate_logs():
    """Fecha o log atual, deleta o arquivo e inicia um novo."""
    global CURRENT_LOG_FILE, logger
    
    # 1. Fechar handlers para liberar o arquivo (Windows trava se não fechar)
    logger = logging.getLogger("BotAfiliados")
    if logger.hasHandlers():
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)
            
    # 2. Deletar o arquivo físico antigo
    if CURRENT_LOG_FILE and CURRENT_LOG_FILE.exists():
        try:
            os.remove(CURRENT_LOG_FILE)
            # Como o logger está fechado, usamos print nativo temporariamente
            print(f"🗑️ [SISTEMA] Log antigo deletado: {CURRENT_LOG_FILE.name}")
        except Exception as e:
            print(f"⚠️ [SISTEMA] Falha ao deletar log antigo: {e}")
            
    # 3. Reiniciar o logger (cria arquivo novo)
    setup_logger()
    logger.info("♻️ Logs reiniciados automaticamente (Ciclo de Limpeza)")


class RestartRequested(Exception):
    """Raised to force a clean browser/context restart."""


# 🔥 Contador de falhas por mensagem para evitar loop infinito
_FAIL_COUNTER: dict[str, int] = {}  # msg_id → nº de falhas consecutivas
MAX_RETRIES_PER_MSG = 3  # após 3 falhas, considera mensagem como "processada"


async def chunked_sleep(total_seconds: int, chunk_seconds: int, *, label: str = ""):
    remaining = max(0, int(total_seconds))
    chunk = max(1, int(chunk_seconds))
    while remaining > 0:
        step = min(chunk, remaining)
        await asyncio.sleep(step)
        remaining -= step
        if remaining > 0 and label:
            logger.info(f"   ⏳ {label}: {remaining}s restantes...")


async def ensure_whatsapp_ready(page_w):
    """Light health-check with retries. If WA is not usable, request restart."""
    max_attempts = 3
    
    # Seletores alternativos robustos (WhatsApp muda DOM frequentemente)
    selectors = [
        'div[contenteditable="true"][data-tab]',  # Seletor original
        'div[contenteditable="true"][title*="Pesquisar"]',
        'div[contenteditable="true"][title*="Search"]',
        '#side div[contenteditable="true"]',
        'div[role="searchbox"]',
        'input[type="text"]',
    ]
    
    for attempt in range(1, max_attempts + 1):
        try:
            # Check if page is closed
            try:
                await page_w.evaluate("1+1")  # Simple JS to check if page is alive
            except Exception:
                logger.error("❌ Página está fechada!")
                raise RestartRequested("Page closed")
            
            # Check if WhatsApp is ready - tenta múltiplos seletores
            found_selector = None
            for sel in selectors:
                try:
                    await page_w.wait_for_selector(sel, timeout=3000)
                    found_selector = sel
                    logger.info(f"✅ WhatsApp OK (seletor encontrado: {sel[:40]}...)")
                    return
                except Exception:
                    continue
            
            # Se chegou aqui, nenhum seletor funcionou
            if attempt < max_attempts:
                logger.warning(f"⚠️  Nenhum seletor respondeu ({attempt}/{max_attempts})")
            else:
                logger.error("❌ Nenhum seletor de WhatsApp encontrado após 3 tentativas")
                raise RestartRequested("WhatsApp selectors not responding")
            
        except RestartRequested:
            raise
        except Exception as e:
            logger.warning(f"⚠️  WhatsApp parece travado ({attempt}/{max_attempts}): {str(e)[:80]}")
            
            if attempt < max_attempts:
                logger.info("🔄 Tentando recarregar em 3s...")
                await asyncio.sleep(3)
                try:
                    await page_w.reload(wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(2)
                except Exception as reload_err:
                    logger.warning(f"⚠️  Reload falhou: {str(reload_err)[:60]}")
            else:
                logger.error("❌ WhatsApp não respondeu após 3 tentativas")
                raise RestartRequested("WhatsApp not responding")


def process_text_enhancements(text: str) -> str:
    """
    Remove emoji específico (🦸) mas MANTÉM formatação, quebras de linha e emojis
    """
    if not text:
        return text

    original_len = len(text)

    text = re.sub(r"🦸[\u200d\ufe0f♂️♀️🏻-🏿]*", "", text)
    text = re.sub(r"[\u200d\ufe0f🏻-🏿]+", "", text)

    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        cleaned_line = " ".join(line.split())
        cleaned_lines.append(cleaned_line)

    text = "\n".join(cleaned_lines)

    if len(text) < original_len:
        logger.info(f"   🧹 Removido emoji: {SUPERHERO_EMOJI}")

    if random.random() < GATILHO_CHANCE:
        gatilho = random.choice(GATILHOS)
        text = f"{gatilho}\n\n{text}"
        logger.info(f"   ✨ Gatilho adicionado: {gatilho}")

    return text


def filter_meli_sec_urls(urls: list[str]) -> list[str]:
    """Filtra URLs do Mercado Livre (/sec/, meli.la, etc)"""
    if not urls:
        return []
    # Padrões de URLs do Mercado Livre
    patterns = [
        re.compile(r"mercadolivre\..*?/sec/", re.IGNORECASE),  # /sec/ tradicional
        re.compile(r"https?://meli\.la/", re.IGNORECASE),       # meli.la shortener
        re.compile(r"https?://mercadolivre\.com/sec/", re.IGNORECASE),  # sem .br
    ]
    result = []
    for u in urls:
        if u and any(p.search(u) for p in patterns):
            result.append(u)
    return result


def cleanup_temp_images(download_dir: str):
    try:
        temp_dir = Path(download_dir)
        if not temp_dir.exists():
            return
        for img_file in temp_dir.glob("*.jpg"):
            try:
                img_file.unlink()
            except Exception:
                pass
        logger.info("🗑️  Cleanup: imagens temporárias deletadas")
    except Exception as e:
        logger.warning(f"⚠️  Erro ao limpar imagens: {e}")


async def wait_for_day_time():
    if not NIGHT_MODE_ENABLED:
        return
    now = datetime.now()
    current_hour = now.hour
    if NIGHT_START_HOUR <= current_hour < NIGHT_END_HOUR or (
        NIGHT_START_HOUR > NIGHT_END_HOUR
        and (current_hour >= NIGHT_START_HOUR or current_hour < NIGHT_END_HOUR)
    ):
        logger.info(f"Modo noturno ativo ({NIGHT_START_HOUR:02d}:00-{NIGHT_END_HOUR:02d}:00)")
        logger.info(f"Pausando até {NIGHT_END_HOUR:02d}:00...")
        while True:
            now = datetime.now()
            current_hour = now.hour
            if not (
                NIGHT_START_HOUR <= current_hour < NIGHT_END_HOUR
                or (
                    NIGHT_START_HOUR > NIGHT_END_HOUR
                    and (current_hour >= NIGHT_START_HOUR or current_hour < NIGHT_END_HOUR)
                )
            ):
                logger.info("Modo diurno - retomando operação")
                break
            await asyncio.sleep(300)


async def process_new_message(
    page_w,
    page_m,
    ml_manager,
    text: str,
    hrefs: list[str],
    source_name: str,
    target_name: str,
    description: str,
    bubble=None,  # 🔥 Novo: recebe o bubble específico para evitar mistura de imagem/legenda
    msg_id: str = "",  # 🔥 NOVO: recebe msg_id para o fail counter
) -> bool:
    logger.info(f"   📌 [process_new_message] Iniciando para {source_name}")
    
    # Se não recebeu bubble, busca (compatibilidade)
    if bubble is None:
        bubble = await get_last_message_bubble(page_w)
    
    logger.info(f"   🔍 Verificando se tem imagem...")
    if not await has_image(bubble):
        logger.warning(f"   ⚠️  {source_name}: Sem IMAGEM - IGNORANDO mensagem")
        return True

    logger.info(f"   📸 {source_name}: Mensagem tem IMAGEM ✅")

    urls = hrefs if hrefs else []
    if not urls:
        logger.info(f"   🔗 Extraindo URLs do texto...")
        urls = extract_urls_from_text(text)
        logger.info(f"   🔗 Extraídas {len(urls)} URLs do texto")

    logger.info(f"   🔍 Filtrando URLs...")
    meli_urls = filter_meli_sec_urls(urls)
    
    # 🔥 Verifica se AMAZON está habilitado antes de filtrar
    amazon_urls = filter_amazon_urls(urls) if AMAZON_ENABLED else []
    logger.info(f"   📊 URLs encontradas: ML={len(meli_urls)}, AMAZON={len(amazon_urls)}")
    
    mapping = {}
    product_url = None
    platform = None  # 'ML' ou 'AMAZON'
    resolved_ml_url = None  # 🔥 URL real MLB após resolver meli.la
    
    # Prioridade: Mercado Livre primeiro
    if meli_urls:
        platform = "ML"
        logger.info(f"   🛒 Processando URLs do Mercado Livre...")
        page_ml, tag_ml = await ml_manager.get_ml_page_and_tag(page_m)
        prof_name = ml_manager.current_profile["name"]
        for u in meli_urls[:3]:
            logger.info(f"   🔗 [ML/{prof_name}] Gerando afiliado para: {u[:60]}...")
            try:
                new_u, prod_url = await generate_affiliate_link(page_ml, u, tag_ml)
                if new_u:
                    mapping[u] = new_u
                    product_url = prod_url
                    resolved_ml_url = prod_url  # 🔥 Guarda URL real MLB
                    logger.info(f"   ✅ [ML/{prof_name}] Gerado: {new_u[:60]}...")
                    break
                else:
                    logger.warning(f"   ⚠️  Falhou gerar link para {u[:60]}")
            except Exception as e:
                logger.error(f"   ❌ Erro ao gerar link ML: {e}")
    
    # Se não tem ML, tenta Amazon
    elif amazon_urls:
        platform = "AMAZON"
        logger.info(f"   🛒 Processando URLs da Amazon...")
        for u in amazon_urls[:3]:
            logger.info(f"   🔗 [AMAZON] Gerando afiliado para: {u[:60]}...")
            try:
                # Usando a função importada do affiliate.py unificado
                new_u, prod_url = await generate_amazon_affiliate_link_async(
                    page_m, u, AMAZON_AFFILIATE_TAG
                )
                if new_u:
                    mapping[u] = new_u
                    product_url = prod_url
                    logger.info(f"   ✅ [AMAZON] Gerado: {new_u[:60]}...")
                    break
                else:
                    logger.warning(f"   ⚠️  Falhou gerar link Amazon para {u[:60]}")
            except Exception as e:
                logger.error(f"   ❌ Erro ao gerar link Amazon: {e}")
    
    else:
        logger.warning(f"   ⚠️  {source_name}: Sem link ML ou Amazon (ou Amazon desativada) - IGNORANDO")
        return True

    if not mapping:
        logger.error(f"   ❌ {source_name}: Falha ao gerar afiliado [{platform}]")
        return False

    enhanced_text = process_text_enhancements(text)
    new_text = replace_urls_in_text(enhanced_text, mapping)
    new_text = format_old_price_with_strikethrough(new_text)
    final_text = new_text

    logger.info(f"   📝 Texto processado: {len(final_text)} chars")
    preview = final_text.replace("\n", " ")[:80]
    logger.info(f"   📝 Preview: {preview}...")

    # 🔥 DEDUP: verifica duplicata ANTES de baixar imagem
    # Usa a URL real MLB se disponível (mais confiável que meli.la)
    dedup_urls = list(mapping.values())  # URLs afiliadas geradas
    if resolved_ml_url:
        dedup_urls.insert(0, resolved_ml_url)  # MLB URL tem prioridade no hash

    from dedup import is_duplicate, mark_as_sent
    if is_duplicate(target_name, text, dedup_urls):
        logger.warning(f"   🔄 {source_name}: DUPLICATA detectada - IGNORANDO (sem envio)")
        return True  # True = considera processado para não retentar infinitamente

    logger.info(f"   📸 Baixando imagem do bubble específico (evita mistura)...")

    # 🔥 Usa download_last_image com o bubble específico para evitar mistura
    img_path = await download_last_image(page_w, DOWNLOAD_DIR)
    if not img_path:
        logger.error(f"   ❌ {source_name}: FALHA ao capturar/baixar imagem")
        return False

    logger.info(f"   ✅ Imagem pronta: {os.path.basename(img_path)}")

    await page_w.bring_to_front()
    await page_w.wait_for_timeout(300)

    logger.info(f"   📤 {source_name}: Enviando IMAGEM + LEGENDA para {target_name}...")
    ok = await send_image_with_caption(
        page_w,
        target_name,
        img_path,
        final_text,
        target_group=target_name,
    )

    if img_path and os.path.exists(img_path):
        try:
            os.remove(img_path)
            logger.info(f"   🗑️  Imagem temporária deletada")
        except Exception as e:
            logger.warning(f"   ⚠️  Erro ao deletar imagem: {e}")

    if ok:
        # 🔥 Marca como enviado usando URL MLB real (não meli.la)
        mark_as_sent(target_name, text, dedup_urls)
        logger.info(f"   ✅✅✅ {source_name}: SUCESSO!")
    else:
        logger.error(f"   ❌ {source_name}: FALHA ao enviar")

    return ok


async def monitoring_loop(page_w, page_m, ml_manager):
    last_seen_dict = {}
    logger.info("")
    logger.info("=" * 80)
    logger.info("🤖 BOT INICIADO - Sources Múltiplos")
    if FIRST_TEST:
        logger.info("🧪 MODO FIRST-TEST: Vai testar cada perfil ML uma vez sem esperar 30 min")
    logger.info("=" * 80)
    logger.info("")
    for source_group, target_group, description in CHANNEL_PAIRS:
        last_seen_dict[source_group] = load_last_seen(source_group)
        logger.info(f"📋 {description}")
        logger.info(f"   Source: {source_group}")
        logger.info(f"   Target: {target_group}")
        if last_seen_dict[source_group]:
            logger.info(f"   Último ID: {last_seen_dict[source_group][:16]}...")
        else:
            logger.info(f"   Último ID: nenhum (primeira execução - vai enviar ÚLTIMA)")
        logger.info("")
    logger.info(f"⏱️  Ciclo: Verificar todos → pausar 1~6 minutos (aleatório)")
    logger.info("=" * 80)
    logger.info("")
    cycle_count = 0

    # Para modo first-test: rastreia quais perfis ja foram testados
    tested_profiles = set()

    async def _check_all_sources():
        nonlocal tested_profiles
        for source_group, target_group, description in CHANNEL_PAIRS:
            try:
                logger.info(f"🔹 {description}")
                logger.info(f"   Verificando: {source_group}...")

                try:
                    await ensure_whatsapp_ready(page_w)
                except RestartRequested:
                    logger.error("WhatsApp não está respondendo - acionando restart do contexto")
                    raise
                
                chat_opened = await open_chat(page_w, source_group)
                
                if not chat_opened:
                    logger.warning(f"   ⚠️  Não foi possível abrir o chat '{source_group}' - pulando")
                    continue
                
                await page_w.wait_for_timeout(BUBBLE_REFRESH_DELAY * 1000)

                # 🔥 Captura o bubble ANTES de extrair texto/urls para garantir consistência
                current_bubble = await get_last_message_bubble(page_w)
                
                text, hrefs = await extract_last_message_text_and_urls(page_w)
                if text or hrefs:
                    msg_id = compute_msg_id(text, hrefs)
                    last_seen_id = last_seen_dict.get(source_group)
                    if not last_seen_id:
                        logger.info("   🆕 PRIMEIRA EXECUÇÃO - Enviando ÚLTIMA mensagem")
                        ok = await process_new_message(
                            page_w, page_m, ml_manager, text, hrefs, source_group, target_group, description,
                            bubble=current_bubble  # 🔥 Passa o bubble específico
                        )
                        if ok:
                            last_seen_dict[source_group] = msg_id
                            preview = text[:50] if text else ""
                            save_last_seen(msg_id, source_group, preview)
                            logger.info(f"   💾 ID salvo: {msg_id[:16]}...")

                            # First-test: forca rotacao apos envio
                            if FIRST_TEST:
                                prof_name = ml_manager.current_profile["name"]
                                tested_profiles.add(prof_name)
                                logger.info(f"   🧪 [FIRST-TEST] Perfil {prof_name} testado! Forcando rotacao...")
                                await ml_manager.force_rotate()
                        else:
                            logger.warning("   ⚠️  Falhou enviar - ID NÃO salvo")
                    elif msg_id != last_seen_id:
                        logger.info("   🆕 MENSAGEM NOVA DETECTADA!")
                        logger.info(f"   ID atual: {msg_id[:16]}...")
                        logger.info(f"   ID anterior: {last_seen_id[:16]}...")

                        # 🔥 Verifica se esta mensagem já falhou muitas vezes
                        fail_count = _FAIL_COUNTER.get(msg_id, 0)
                        if fail_count >= MAX_RETRIES_PER_MSG:
                            logger.warning(
                                f"   ⚠️  Mensagem {msg_id[:16]}... falhou {fail_count}x - descartando"
                            )
                            # Salva o ID para não tentar mais esta mensagem
                            last_seen_dict[source_group] = msg_id
                            save_last_seen(msg_id, source_group, text[:50] if text else "")
                            _FAIL_COUNTER.pop(msg_id, None)
                        else:
                            ok = await process_new_message(
                                page_w, page_m, ml_manager, text, hrefs, source_group, target_group, description,
                                bubble=current_bubble,  # 🔥 Passa o bubble específico
                                msg_id=msg_id,  # 🔥 Passa msg_id
                            )
                            if ok:
                                last_seen_dict[source_group] = msg_id
                                preview = text[:50] if text else ""
                                save_last_seen(msg_id, source_group, preview)
                                logger.info(f"   💾 ID salvo: {msg_id[:16]}...")
                                _FAIL_COUNTER.pop(msg_id, None)  # 🔥 Limpa contador de falhas

                                # First-test: forca rotacao apos envio
                                if FIRST_TEST:
                                    prof_name = ml_manager.current_profile["name"]
                                    tested_profiles.add(prof_name)
                                    logger.info(f"   🧪 [FIRST-TEST] Perfil {prof_name} testado! Forcando rotacao...")
                                    await ml_manager.force_rotate()
                            else:
                                _FAIL_COUNTER[msg_id] = fail_count + 1  # 🔥 Incrementa contador
                                remaining = MAX_RETRIES_PER_MSG - _FAIL_COUNTER[msg_id]
                                logger.warning(
                                    f"   ⚠️  Falhou enviar - ID NÃO salvo "
                                    f"(tentativa {_FAIL_COUNTER[msg_id]}/{MAX_RETRIES_PER_MSG}, "
                                    f"{remaining} restantes)"
                                )
                    else:
                        logger.info("   ✅ Nenhuma mensagem nova")
                else:
                    logger.info("   ℹ️  Sem mensagens no grupo")
            except Exception as e:
                logger.error(f"❌ Erro ao verificar {source_group}: {e}")
                logger.error(traceback.format_exc())
            await asyncio.sleep(2)

            # First-test: verifica se todos os perfis foram testados
            if FIRST_TEST:
                all_profile_names = {p["name"] for p in ML_PROFILES}
                if tested_profiles >= all_profile_names:
                    logger.info("")
                    logger.info("=" * 80)
                    logger.info("🧪 FIRST-TEST COMPLETO! Todos os perfis foram testados:")
                    for pn in sorted(tested_profiles):
                        logger.info(f"   ✅ {pn}")
                    logger.info("Bot encerrando. Rode sem --first-test para operacao normal.")
                    logger.info("=" * 80)
                    return True  # Sinaliza que deve parar
        return False  # Continua normalmente

    while True:
        try:
            cycle_count += 1
            logger.info(f"⏱️ [CICLO #{cycle_count}] Iniciando...")
            
            # ==========================================
            # 🧹 LIMPEZA AUTOMÁTICA DE LOGS
            # ==========================================
            if LOG_CLEANUP_CYCLES > 0 and cycle_count % LOG_CLEANUP_CYCLES == 0:
                logger.info(f"🧹 Iniciando limpeza de logs (Ciclo {cycle_count})...")
                rotate_logs()

            logger.info(f"⏰ Verificando modo noturno...")
            await wait_for_day_time()
            
            logger.info("")
            logger.info("=" * 80)
            logger.info(f"🔄 CICLO #{cycle_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("=" * 80)
            logger.info("")
            
            logger.info(f"🔎 Iniciando _check_all_sources()...")
            should_stop = await _check_all_sources()
            logger.info(f"✅ _check_all_sources() completou com should_stop={should_stop}")

            # First-test: encerra se todos os perfis foram testados
            if should_stop:
                break

            if RESTART_EVERY_CYCLES and cycle_count % RESTART_EVERY_CYCLES == 0:
                logger.warning(
                    f"🔁 Reinício preventivo a cada {RESTART_EVERY_CYCLES} ciclos (agora: {cycle_count})"
                )
                raise RestartRequested("Periodic restart")

            logger.info("")
            logger.info("=" * 80)
            random_minutes = random.randint(1, 6)
            logger.info(f"⏸️  Ciclo completo! Pausando por {random_minutes} minutos...")
            logger.info("=" * 80)
            logger.info("")
            await chunked_sleep(random_minutes * 60, SLEEP_GRANULARITY_SECONDS, label="Pausa")

        except KeyboardInterrupt:
            logger.info("")
            logger.info("⚠️  Bot interrompido pelo usuário (Ctrl+C)")
            break
        except RestartRequested:          # ← FIX BUG #2: propaga para run()
            raise
        except Exception as e:
            logger.error(f"❌ Erro no loop principal: {e}")
            logger.error(traceback.format_exc())
            await asyncio.sleep(60)


async def run():
    logger.info("🚀 Iniciando bot...")
    if FIRST_TEST:
        logger.info("🧪 MODO FIRST-TEST ativado via --first-test")
    cleanup_temp_images(DOWNLOAD_DIR)
    async with async_playwright() as p:
        logger.info(f"🔧 Chrome Profile: {CHROME_USER_DATA_DIR}")
        logger.info(f"🎭 Modo Headless: {HEADLESS}")

        while True:
            ctx = None
            ml_manager = None
            try:
                ctx = await p.chromium.launch_persistent_context(
                    CHROME_USER_DATA_DIR,
                    channel="chrome",
                    headless=HEADLESS,
                    args=[
                        f"--profile-directory={CHROME_PROFILE_DIR_NAME}",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    ],
                    ignore_default_args=["--enable-automation"],
                )

                page_w = ctx.pages[0] if ctx.pages else await ctx.new_page()
                logger.info("📱 Abrindo WhatsApp Web...")
                await page_w.goto("https://web.whatsapp.com", wait_until="domcontentloaded")
                
                # 🔥 Aguarda WhatsApp carregar com verificação robusta via JS
                logger.info("⏳ Aguardando WhatsApp carregar...")
                logger.info("⚠️ NÃO FECHE O NAVEGADOR!")

                import time as _time
                wa_deadline = _time.time() + 240  # 4 min total
                wa_ready = False

                while _time.time() < wa_deadline and not wa_ready:
                    elapsed = int(_time.time() - (wa_deadline - 240))

                    # ── Método 1: seletores CSS (fallback largo) ──────────────────────
                    wa_selectors = [
                        '#pane-side',                                        # painel esquerdo (muito estável)
                        'div[contenteditable="true"][data-tab]',             # caixa de busca clássica
                        'div[contenteditable="true"][title*="Pesquisar"]',
                        'div[contenteditable="true"][title*="Search"]',
                        'div[role="searchbox"]',
                        'div[aria-label*="conversa"]',
                        'div[aria-label*="Chat list"]',
                        '#side div[contenteditable="true"]',
                        'header div[role="button"]',
                    ]
                    for sel in wa_selectors:
                        try:
                            await page_w.wait_for_selector(sel, timeout=8000)
                            logger.info(f"✅ WhatsApp pronto! ({elapsed}s | CSS: {sel[:50]})")
                            wa_ready = True
                            break
                        except Exception:
                            continue

                    # ── Método 2: JavaScript direto no DOM ───────────────────────────
                    if not wa_ready:
                        try:
                            js_ok = await page_w.evaluate("""
                                () => {
                                    // Se QR code está visível, NÃO está pronto
                                    if (document.querySelector('canvas[aria-label*="QR"]') ||
                                        document.querySelector('div[data-ref]'))
                                        return false;

                                    // Qualquer desses indica app principal carregado
                                    return !!(
                                        document.querySelector('#pane-side') ||
                                        document.querySelector('[data-testid="chat-list"]') ||
                                        document.querySelector('[data-testid="cell-frame-container"]') ||
                                        document.querySelectorAll('div[contenteditable="true"]').length >= 1
                                    );
                                }
                            """)
                            if js_ok:
                                logger.info(f"✅ WhatsApp pronto! ({elapsed}s | via JS DOM check)")
                                wa_ready = True
                        except Exception as js_err:
                            logger.debug(f"JS check falhou: {js_err}")

                    if not wa_ready:
                        # Avisa se QR code está aparecendo
                        try:
                            qr_visible = await page_w.evaluate(
                                "() => !!document.querySelector('canvas[aria-label*=\"QR\"]')"
                            )
                            if qr_visible:
                                logger.warning(f"📱 QR CODE visível ({elapsed}s) — escaneie o WhatsApp!")
                            else:
                                logger.info(f"⏳ Aguardando WhatsApp... ({elapsed}s/240s)")
                        except Exception:
                            logger.info(f"⏳ Aguardando WhatsApp... ({elapsed}s/240s)")
                        await asyncio.sleep(3)

                if not wa_ready:
                    logger.error("❌ WhatsApp não carregou em 4 minutos.")
                    raise RuntimeError("WhatsApp timeout — verifique se o QR foi escaneado")

                page_m = await ctx.new_page()
                logger.info("🛒 Abrindo Mercado Livre (Verificação)...")
                try:
                    await page_m.goto(
                        "https://www.mercadolivre.com.br/afiliados",
                        wait_until="domcontentloaded",
                        timeout=60000,
                    )
                    logger.info("✅ Mercado Livre pronto!")
                except Exception as e:
                    logger.warning(f"⚠️  Erro ao abrir ML: {e}")
                    logger.warning(traceback.format_exc())

                # 🔥 LÓGICA DE LOGIN AMAZON SEM FREEZE
                if AMAZON_ENABLED:
                    logger.info("🛒 Abrindo Amazon (Verificação de Sessão)...")
                    try:
                        # Apenas acessa para garantir que cookies/sessão estão ativos
                        await page_m.goto("https://www.amazon.com.br", wait_until="domcontentloaded", timeout=60000)
                        logger.info("✅ Amazon carregada!")
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao abrir Amazon: {e}")
                        logger.warning(traceback.format_exc())

                logger.info("")
                logger.info("🚀 Iniciando monitoramento...")
                logger.info("")

                logger.info("🔧 Inicializando MLRotationManager...")
                ml_manager = MLRotationManager(p)
                logger.info("✅ MLRotationManager criado!")
                
                logger.info("🔄 Começando monitoring_loop...")
                await monitoring_loop(page_w, page_m, ml_manager)
                logger.info("✅ monitoring_loop concluído (só volta se receber STOP)")
                break

            except RestartRequested as e:
                logger.warning(f"♻️  Reiniciando contexto: {e}")
                await asyncio.sleep(5)
            except KeyboardInterrupt:
                logger.info("\n⚠️  Bot interrompido pelo usuário (Ctrl+C)")
                break
            except Exception as e:
                error_msg = str(e)
                logger.critical(f"❌ ERRO CRÍTICO na inicialização: {error_msg}")
                logger.critical(traceback.format_exc())
                
                if "Target page, context or browser has been closed" in error_msg:
                    logger.error("❌ O NAVEGADOR FOI FECHADO INESPERADAMENTE!")
                    logger.error("🔴 Possíveis causas:")
                    logger.error("   1. Você fechou o navegador manualmente")
                    logger.error("   2. Falta de memória RAM")
                    logger.error("   3. Antivírus matou o processo")
                    logger.error("   4. Outra instância do bot usando o mesmo perfil")
                    logger.error("🔄 Reiniciando em 15 segundos...")
                    await asyncio.sleep(15)
                else:
                    logger.critical("⚠️  Erro desconhecido! Aguardando 30s e tentando novamente...")
                    await asyncio.sleep(30)
            finally:
                if ml_manager is not None:
                    try:
                        await ml_manager.close()
                    except Exception:
                        pass
                if ctx is not None:
                    try:
                        await ctx.close()
                    except Exception:
                        pass


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("\n⚠️  Bot interrompido pelo usuário (Ctrl+C)")
    except Exception as e:
        logger.critical(f"❌ ERRO FATAL: {e}")
        logger.critical(traceback.format_exc())