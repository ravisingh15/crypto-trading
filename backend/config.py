import os
from pathlib import Path
from dotenv import load_dotenv

# Locate project root directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file in root directory
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

# Credentials & Configurations
API_KEY = os.getenv("API_KEY", "")
SECRET_KEY = os.getenv("SECRET_KEY", "")

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# Binance REST endpoints with fallback
BINANCE_BASE_URL = os.getenv("BINANCE_BASE_URL", "https://api.binance.com")
BINANCE_DATA_URL = os.getenv("BINANCE_DATA_URL", "https://data-api.binance.vision")
BINANCE_FUTURES_URL = os.getenv("BINANCE_FUTURES_URL", "https://fapi.binance.com")

# Default pairs to track if scanning fails or for quick summary
TOP_PAIRS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "NEARUSDT",
    "SUIUSDT", "PEPEUSDT", "APTUSDT", "FETUSDT", "RENDERUSDT",
    "ARBUSDT", "OPUSDT", "INJUSDT", "SHIBUSDT", "WIFUSDT"
]
