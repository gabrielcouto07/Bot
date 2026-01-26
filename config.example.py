# config.example.py
# ⚠️ IMPORTANTE: Este arquivo contém seus dados sensíveis (ignorado pelo Git).
# Edite este arquivo com seus dados reais e o bot usará estas configurações.

# ====================================
# 🔥 ROUND-ROBIN 3x3 (Source → Target)
# ====================================
# Formato: (Source Group, Target Group, Descrição)
CHANNEL_PAIRS = [ 
    ("Rafa Shop", "Testes", "Teste de Funcionalidades"),
    # Adicione mais pares conforme necessário:
    # ("SOURCE_GROUP_NAME", "TARGET_GROUP_NAME", "Descrição"),
]

# Tag de afiliado Mercado Livre
MELI_AFFILIATE_TAG = "silvagabriel20230920180155"

# Pasta para downloads
DOWNLOAD_DIR = "./tmp"

# Segundos entre verificações de cada grupo
POLL_SECONDS = 10

# Chrome profile - Gabriel Cardoso
CHROME_USER_DATA_DIR = r"C:\Users\GABRIEL.CARDOSO\AppData\Local\BotChromeProfile"
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

# Link do grupo WhatsApp para adicionar nas mensagens (SUBSTITUA COM O SEU)
MY_GROUP_LINK = "https://chat.whatsapp.com/seu_link_aqui"
