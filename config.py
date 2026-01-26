# config.py

# ====================================
# 🔥 ROUND-ROBIN 3x3 (Source → Target)
# ====================================
# Formato: (Source Group, Target Group, Descrição)
CHANNEL_PAIRS = [ 
    ("Tech Deals 🎯 [01]", "Testes", "Teste de Funcionalidades"),
    ("Home Deals [12]", "Testes", "Teste de Funcionalidades"),
    ("Rafa Shop", "Testes", "Teste de Funcionalidades"),
    ("Guerra Deals Fit [112]", "Testes", "Teste de Funcionalidades"),
    ("Guerra Deals Fit [73]", "Testes", "Teste de Funcionalidades"),
    ("Parfum Deals 👔 [11]", "Testes", "Teste de Funcionalidades")
]

# Tag de afiliado Mercado Livre (CORRETA)
MELI_AFFILIATE_TAG = "np20241006154502"

# Pasta para downloads
DOWNLOAD_DIR = "./tmp"

# Segundos entre verificações de cada grupo
POLL_SECONDS = 10

# Chrome profile - Gabriel Cardoso (CORRETO)
CHROME_USER_DATA_DIR = r"C:\BotChromeProfile"
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
MY_GROUP_LINK = "https://chat.whatsapp.com/LJYchTBpAQ3JZ1Bpvod4w1"
