# config.py
# ⚠️ IMPORTANTE: Este é o template padrão com valores de exemplo.
# Para usar o bot, edite config.example.py com seus dados reais.
# config.example.py é ignorado pelo Git para proteger dados sensíveis.

# ====================================
# 🔥 ROUND-ROBIN 3x3 (Source → Target)
# ====================================
# Formato: (Source Group, Target Group, Descrição)
CHANNEL_PAIRS = [ 
    ("Tech Deals 🎯 [01]", "Promo Codes🛒🔥 - Promoções e Cupons", "Teste de Funcionalidades"),
    ("Home Deals [12]", "Promo Codes🛒🔥 - Promoções e Cupons", "Teste de Funcionalidades"),
    ("Rafa Shop", "Promo Codes🛒🔥 - Promoções e Cupons", "Teste de Funcionalidades"),
    ("Parfum Deals 👔 [11]", "Promo Codes🛒🔥 - Promoções e Cupons", "Teste de Funcionalidades"),
    ("Guerra Deals Fit [112]", "Promo Codes🛒🔥 - Promoções e Cupons", "Teste de Funcionalidades"),
    ("Tech Promos", "Promo Codes🛒🔥 - Promoções e Cupons", "Teste de Funcionalidades"),
    ("Guerra Deals Fit [73]", "Promo Codes🛒🔥 - Promoções e Cupons", "Teste de Funcionalidades"),
    ("Super Promos", "Promo Codes🛒🔥 - Promoções e Cupons", "Teste de Funcionalidades"),
]

# Tag de afiliado Mercado Livre
MELI_AFFILIATE_TAG = "np20241006154502"

# Pasta para downloads
DOWNLOAD_DIR = "./tmp"

# Segundos entre verificações de cada grupo
POLL_SECONDS = 10

# Chrome profile - Substitua pelo seu caminho
CHROME_USER_DATA_DIR = r"C:\Users\pedronunees\AppData\Local\BotChromeProfile"
CHROME_PROFILE_DIR_NAME = "Default"

# Modo headless (True = invisível, False = visível)
HEADLESS = False

# ====================================
# 🔥 GATILHOS E EMOJI
# ====================================
# Emoji a ser removido das mensagens
SUPERHERO_EMOJI = "🦸"

# Gatilhos aleatórios (20% de chance)
GATILHOS = [
    "🔥 CORRA!",
    "⚡ OFERTA IMPERDÍVEL!",
    "💥 NESSE PREÇO NUNCA!",
    "🎯 APROVEITA!",
    "⚡ ÚLTIMA UNIDADE!",
    "💰 PREÇO DE LOUCO!",
    "🚨 PROMOÇÃO RELÂMPAGO!",
]

# Chance de adicionar gatilho (0.0 a 1.0)
GATILHO_CHANCE = 0.20

# Link do grupo WhatsApp para adicionar nas mensagens
MY_GROUP_LINK = "https://chat.whatsapp.com/GCLG0St2zFqDJvC51o5V5X"
