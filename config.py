# Configuration settings for Croma Stock Tracker Bot

import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Scrape.do API Configuration
SCRAPE_DO_API_KEY = os.getenv("SCRAPE_DO_API_KEY", "")

# Bot Settings
CHECK_INTERVAL_MINUTES = 5
MAX_TRACKED_PRODUCTS_PER_USER = 10
RATE_LIMIT_SECONDS = 60  # Minimum time between user commands

# Croma URLs
CROMA_BASE_URL = "https://www.croma.com"

# Database
DATABASE_PATH = "bot_database.db"

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "bot.log"
