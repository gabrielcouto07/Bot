# config.py

# ========================================
# 🔥 CONFIGURAÇÃO DE FONTES (canais/grupos)
# ========================================

# OPÇÃO 1: Uma única fonte (comportamento anterior)
# SOURCE_GROUP = "Herói da Promo #326"

# OPÇÃO 2: Múltiplas fontes (canais e/ou grupos)
# O bot vai monitorar TODOS ao mesmo tempo
SOURCE_GROUPS = [
    "Herói da Promo #326",     # Grupo
    # "Canal de Ofertas",       # Canal
    # "Promoções Relâmpago",    # Outro grupo
    # "Deals Brasil",           # Outro canal
]

# Nome do grupo/canal de destino (pode ser grupo OU canal)  
TARGET_GROUP = "Teste"  

MELI_AFFILIATE_TAG = "silvagabriel20230920180155"
DOWNLOAD_DIR = "./tmp"
POLL_SECONDS = 2

CHROME_USER_DATA_DIR = r"C:\Users\GABRIEL.CARDOSO\AppData\Local\BotChromeProfile"
CHROME_PROFILE_DIR_NAME = "Default"

HEADLESS = False
