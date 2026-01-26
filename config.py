# config.py
# ⚠️ IMPORTANTE: Este é o template padrão com valores de exemplo.
# Para usar o bot, edite config.example.py com seus dados reais.
# config.example.py é ignorado pelo Git para proteger dados sensíveis.

# ====================================
# 🔥 ROUND-ROBIN 3x3 (Source → Target)
# ====================================
# Formato: (Source Group, Target Group, Descrição)
CHANNEL_PAIRS = [ 
    ("SOURCE_GROUP", "TARGET_GROUP", "Descrição do par"),
    # Adicione mais pares conforme necessário
]

# Tag de afiliado Mercado Livre
MELI_AFFILIATE_TAG = "seu_affiliate_tag_aqui"

# Pasta para downloads
DOWNLOAD_DIR = "./tmp"

# Segundos entre verificações de cada grupo
POLL_SECONDS = 10

# Chrome profile - Substitua pelo seu caminho
CHROME_USER_DATA_DIR = r"C:\Users\SEU_USUARIO\AppData\Local\BotChromeProfile"
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
MY_GROUP_LINK = "https://chat.whatsapp.com/seu_link_aqui"
