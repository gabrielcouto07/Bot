# config.py

# ========== GRUPOS DO WHATSAPP ==========
SOURCE_GROUP = "Herói da Promo #326"  # Grupo que o bot monitora
TARGET_GROUP = "Teste"                # Grupo para onde envia as mensagens

# ========== CONFIGURAÇÕES DE AFILIADOS ==========
# Mercado Livre
MELI_AFFILIATE_TAG = "silvagabriel20230920180155"
MELI_ENABLED = True  # Processar links do Mercado Livre?

# Amazon
AMAZON_AFFILIATE_TAG = "seu-id-amazon-20"  # ← COLOQUE SEU ID DE AFILIADO AMAZON
AMAZON_ENABLED = True  # Processar links da Amazon?

# Outras plataformas (AliExpress, Shopee, etc)
GENERIC_AFFILIATE_TAG = "seu-id-generico"  # Para outras plataformas
GENERIC_ENABLED = False  # Ativar processamento genérico?

# ========== OUTRAS CONFIGURAÇÕES ==========
DOWNLOAD_DIR = "./tmp"
POLL_SECONDS = 2  # Intervalo de verificação (em segundos)

CHROME_USER_DATA_DIR = r"C:\Users\GABRIEL.CARDOSO\AppData\Local\BotChromeProfile"
CHROME_PROFILE_DIR_NAME = "Default"

HEADLESS = False  # True = roda em segundo plano (sem janela)
