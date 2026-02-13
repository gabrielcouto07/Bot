import time
import logging
from config import ML_PROFILES, ML_ROTATION_MINUTES, HEADLESS

logger = logging.getLogger("BotAfiliados")


class MLRotationManager:
    """Gerencia rotacao de perfis ML (multi-conta Mercado Livre)."""

    def __init__(self, playwright):
        self._pw = playwright
        self._profiles = ML_PROFILES
        self._rotation_seconds = ML_ROTATION_MINUTES * 60
        self._current_index = 0
        self._last_rotation = time.time()
        self._ml_ctx = None    # contexto Playwright extra (perfis #2/#3)
        self._ml_page = None   # page do contexto extra

        prof = self._profiles[self._current_index]
        logger.info(f"[MLRotation] Perfil inicial: {prof['name']} (tag={prof['affiliate_tag'][:20]}...)")

    @property
    def current_profile(self) -> dict:
        return self._profiles[self._current_index]

    def _should_rotate(self) -> bool:
        return (time.time() - self._last_rotation) >= self._rotation_seconds

    async def _close_extra_context(self):
        """Fecha contexto ML extra se houver."""
        if self._ml_page is not None:
            try:
                await self._ml_page.close()
            except Exception:
                pass
            self._ml_page = None

        if self._ml_ctx is not None:
            try:
                await self._ml_ctx.close()
            except Exception:
                pass
            self._ml_ctx = None

    async def _open_extra_context(self, profile: dict):
        """Abre contexto Playwright dedicado para perfil ML."""
        import os
        user_data_dir = profile["user_data_dir"]
        
        # Verifica se o diretório existe
        if not os.path.exists(user_data_dir):
            logger.error(f"[MLRotation] ❌ Diretório NÃO existe: {user_data_dir}")
            logger.error(f"[MLRotation] Execute 'python setup_login.py' para criar os perfis!")
            return
        
        logger.info(f"[MLRotation] Abrindo {profile['name']} ({user_data_dir})...")
        
        self._ml_ctx = await self._pw.chromium.launch_persistent_context(
            user_data_dir,
            channel="chrome",
            headless=HEADLESS,
            args=[
                f"--profile-directory={profile['profile_dir_name']}",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ],
            ignore_default_args=["--enable-automation"],
        )
        self._ml_page = self._ml_ctx.pages[0] if self._ml_ctx.pages else await self._ml_ctx.new_page()

        # Navega para ML afiliados para garantir sessao ativa
        try:
            await self._ml_page.goto(
                "https://www.mercadolivre.com.br/afiliados",
                wait_until="domcontentloaded",
                timeout=60000,
            )
            # Verifica se está logado checando a URL final
            final_url = self._ml_page.url
            if "login" in final_url.lower():
                logger.warning(f"[MLRotation] ⚠️ {profile['name']} NÃO está logado!")
            else:
                logger.info(f"[MLRotation] ✅ {profile['name']} pronto!")
        except Exception as e:
            logger.warning(f"[MLRotation] Erro ao abrir {profile['name']}: {e}")

    async def _rotate(self):
        """Avanca para o proximo perfil ML."""
        from affiliate import clear_csrf_cache

        old_name = self._profiles[self._current_index]["name"]

        # Fecha contexto extra anterior
        await self._close_extra_context()

        # Avanca indice circular
        self._current_index = (self._current_index + 1) % len(self._profiles)
        self._last_rotation = time.time()

        # Limpa CSRF cache (token do perfil anterior nao serve)
        clear_csrf_cache()

        new_prof = self._profiles[self._current_index]
        logger.info(f"[MLRotation] Rotacao: {old_name} -> {new_prof['name']} (tag={new_prof['affiliate_tag'][:20]}...)")

        # Se o novo perfil nao usa contexto principal, abre contexto dedicado
        if not new_prof.get("uses_main_context", False):
            await self._open_extra_context(new_prof)

    async def force_rotate(self):
        """Forca rotacao imediata (usado no modo first-test)."""
        logger.info("[MLRotation] Rotacao forcada (first-test)...")
        await self._rotate()

    async def get_ml_page_and_tag(self, page_m_main):
        """
        Retorna (page, affiliate_tag) para gerar link ML.
        - Rotaciona automaticamente se 30 min passaram.
        - Se perfil atual usa contexto principal, retorna page_m_main.
        - Senao, retorna page do contexto dedicado.
        """
        if self._should_rotate():
            await self._rotate()

        prof = self._profiles[self._current_index]

        if prof.get("uses_main_context", False):
            return page_m_main, prof["affiliate_tag"]

        # Perfil dedicado: garante que contexto esta aberto
        if self._ml_page is None:
            await self._open_extra_context(prof)

        if self._ml_page is None:
            logger.error(f"[MLRotation] ❌ Contexto dedicado não foi criado! Usando fallback")
            return page_m_main, prof["affiliate_tag"]
            
        return self._ml_page, prof["affiliate_tag"]

    async def close(self):
        """Fecha tudo (chamado no shutdown/restart)."""
        await self._close_extra_context()
        logger.info("[MLRotation] Contextos ML extras fechados.")
