"""
setup_login.py - Abre os perfis BotChrome1 e BotChrome2 no Mercado Livre
para que voce possa fazer login manualmente em cada um.

Uso: python setup_login.py

Apos fazer login em ambos, pressione ENTER no terminal para fechar.
"""

import asyncio
from playwright.async_api import async_playwright
from config import ML_PROFILES


async def main():
    # Filtra apenas perfis que NAO usam o contexto principal (BotChrome1, BotChrome2)
    extra_profiles = [p for p in ML_PROFILES if not p.get("uses_main_context", False)]

    if not extra_profiles:
        print("Nenhum perfil extra configurado em ML_PROFILES.")
        return

    print("=" * 60)
    print("SETUP DE LOGIN - Mercado Livre")
    print("=" * 60)
    print()
    for p in extra_profiles:
        print(f"  Perfil: {p['name']} -> {p['user_data_dir']}")
    print()

    contexts = []
    pages = []

    async with async_playwright() as pw:
        for profile in extra_profiles:
            print(f"Abrindo {profile['name']} ({profile['user_data_dir']})...")
            ctx = await pw.chromium.launch_persistent_context(
                profile["user_data_dir"],
                channel="chrome",
                headless=False,  # Sempre visivel para login manual
                args=[
                    f"--profile-directory={profile['profile_dir_name']}",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                ],
                ignore_default_args=["--enable-automation"],
            )
            contexts.append(ctx)

            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            pages.append(page)

            print(f"  Navegando para Mercado Livre afiliados...")
            try:
                await page.goto(
                    "https://www.mercadolivre.com.br/afiliados",
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
                print(f"  {profile['name']}: Mercado Livre aberto!")
            except Exception as e:
                print(f"  {profile['name']}: Erro ao abrir ML: {e}")
                print(f"  Tente fazer login manualmente na janela que abriu.")

        print()
        print("=" * 60)
        print("Faca login no Mercado Livre em CADA janela do Chrome.")
        print("Quando terminar, pressione ENTER aqui para fechar tudo.")
        print("=" * 60)

        # Espera o usuario pressionar ENTER
        await asyncio.get_event_loop().run_in_executor(None, input)

        print()
        print("Fechando perfis...")
        for ctx in contexts:
            try:
                await ctx.close()
            except Exception:
                pass

        print("Pronto! Perfis fechados. Agora voce pode rodar o bot normalmente.")
        print("Para teste inicial: python main.py --first-test")


if __name__ == "__main__":
    asyncio.run(main())
