import os

CHROME_USER_DATA_DIR = "C:\\BotChromeProfile"
CHROME_PROFILE_DIR_NAME = "Default"
HEADLESS = True

DOWNLOAD_DIR = "./tmp"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

MELI_AFFILIATE_TAG = "silvagabriel20230920180155"
AMAZON_AFFILIATE_TAG = "superprom03bb-20"

AMAZON_ENABLED = True

# ✅ REATIVADA para testar se links funcionam sem limpeza de URL
VALIDATE_ML_LINKS = True

# Perfis ML para rotacao multi-conta
ML_PROFILES = [
    {
        "name": "ML1",
        "user_data_dir": "C:\\BotChromeProfile",
        "profile_dir_name": "Default",
        "affiliate_tag": "silvagabriel20230920180155",
        "uses_main_context": True,
    },
    {
        "name": "ML2",
        "user_data_dir": "C:\\BotChrome1",
        "profile_dir_name": "Default",
        "affiliate_tag": "arthurothero",
        "uses_main_context": False,
    },
    {
        "name": "ML3",
        "user_data_dir": "C:\\BotChrome2",
        "profile_dir_name": "Default",
        "affiliate_tag": "np20241006154502",
        "uses_main_context": False,
    },
]
ML_ROTATION_MINUTES = 30

SUPERHERO_EMOJI = "🦸"

GATILHOS = [
    "⚡ CORRE!",
    "🔥 OFERTA IMPERDÍVEL!",
    "💰 PREÇO NUNCA VISTO!",
    "⏰ ÚLTIMAS UNIDADES!",
    "🎯 NESSE PREÇO NUNCA!",
    "💥 ACABANDO!",
]
GATILHO_CHANCE = 0.20

BUBBLE_REFRESH_DELAY = 2

POLL_SECONDS = 180

RESTART_EVERY_CYCLES = 25

CYCLE_TIMEOUT_SECONDS = 240

SLEEP_GRANULARITY_SECONDS = 60

LOG_CLEANUP_CYCLES = 50 

NIGHT_MODE_ENABLED = True
NIGHT_START_HOUR = 1
NIGHT_END_HOUR = 8

CHANNEL_PAIRS = [
    ("Herói da Promo #731", "Super Promos [21]", "Herói da Promo"),
    ("Home Deals [12]", "Super Promos [21]", "Home Deals"),
    ("Tech Deals 🎯 [20]", "Super Promos [21]", "Tech Deals"),
    ("Parfum Deals 👔 [15]", "Super Promos [21]", "Parfum Deals"),
]

GROUP_LINK = "https://linktr.ee/superpromos01"

DEDUP_WINDOW_SECONDS = 1 * 60 * 60