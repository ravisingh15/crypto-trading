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

# Default pairs to track if scanning fails or for quick summary (Crypto)
TOP_PAIRS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "NEARUSDT",
    "SUIUSDT", "PEPEUSDT", "APTUSDT", "FETUSDT", "RENDERUSDT",
    "ARBUSDT", "OPUSDT", "INJUSDT", "SHIBUSDT", "WIFUSDT"
]

# Popular US Stock & ETF bStocks on Binance
TOP_STOCK_PAIRS = [
    "TSLABUSDT", "NVDABUSDT", "AAPLBUSDT", "MSFTBUSDT", "AMZNBUSDT",
    "GOOGLBUSDT", "METABUSDT", "MSTRBUSDT", "COINBUSDT", "PLTRBUSDT",
    "SPYBUSDT", "QQQBUSDT", "TQQQBUSDT", "SMHBUSDT", "SOXLBUSDT",
    "AMDBUSDT", "HOODBUSDT", "ARMBUSDT", "TSMBUSDT", "GMEBUSDT"
]

# Human-friendly company names & ticker aliases
STOCK_METADATA = {
    "TSLA": {"symbol": "TSLABUSDT", "name": "Tesla, Inc.", "sector": "Magnificent 7", "ticker": "TSLA"},
    "NVDA": {"symbol": "NVDABUSDT", "name": "NVIDIA Corporation", "sector": "Magnificent 7", "ticker": "NVDA"},
    "AAPL": {"symbol": "AAPLBUSDT", "name": "Apple Inc.", "sector": "Magnificent 7", "ticker": "AAPL"},
    "MSFT": {"symbol": "MSFTBUSDT", "name": "Microsoft Corporation", "sector": "Magnificent 7", "ticker": "MSFT"},
    "AMZN": {"symbol": "AMZNBUSDT", "name": "Amazon.com, Inc.", "sector": "Magnificent 7", "ticker": "AMZN"},
    "GOOGL": {"symbol": "GOOGLBUSDT", "name": "Alphabet Inc.", "sector": "Magnificent 7", "ticker": "GOOGL"},
    "META": {"symbol": "METABUSDT", "name": "Meta Platforms, Inc.", "sector": "Magnificent 7", "ticker": "META"},
    "MSTR": {"symbol": "MSTRBUSDT", "name": "MicroStrategy Inc.", "sector": "Crypto Equities", "ticker": "MSTR"},
    "COIN": {"symbol": "COINBUSDT", "name": "Coinbase Global, Inc.", "sector": "Crypto Equities", "ticker": "COIN"},
    "HOOD": {"symbol": "HOODBUSDT", "name": "Robinhood Markets", "sector": "Crypto Equities", "ticker": "HOOD"},
    "IREN": {"symbol": "IRENBUSDT", "name": "Iris Energy Ltd.", "sector": "Crypto Equities", "ticker": "IREN"},
    "PLTR": {"symbol": "PLTRBUSDT", "name": "Palantir Technologies", "sector": "Fintech & Tech", "ticker": "PLTR"},
    "AMD": {"symbol": "AMDBUSDT", "name": "Advanced Micro Devices", "sector": "Semiconductors & AI", "ticker": "AMD"},
    "TSM": {"symbol": "TSMBUSDT", "name": "Taiwan Semiconductor", "sector": "Semiconductors & AI", "ticker": "TSM"},
    "ARM": {"symbol": "ARMBUSDT", "name": "Arm Holdings plc", "sector": "Semiconductors & AI", "ticker": "ARM"},
    "AVGO": {"symbol": "AVGOBUSDT", "name": "Broadcom Inc.", "sector": "Semiconductors & AI", "ticker": "AVGO"},
    "QCOM": {"symbol": "QCOMBUSDT", "name": "Qualcomm Inc.", "sector": "Semiconductors & AI", "ticker": "QCOM"},
    "INTC": {"symbol": "INTCBUSDT", "name": "Intel Corporation", "sector": "Semiconductors & AI", "ticker": "INTC"},
    "SMCI": {"symbol": "SMCIBUSDT", "name": "Super Micro Computer", "sector": "Semiconductors & AI", "ticker": "SMCI"},
    "ASML": {"symbol": "ASMLBUSDT", "name": "ASML Holding N.V.", "sector": "Semiconductors & AI", "ticker": "ASML"},
    "SPY": {"symbol": "SPYBUSDT", "name": "SPDR S&P 500 ETF Trust", "sector": "US Indices & ETFs", "ticker": "SPY"},
    "QQQ": {"symbol": "QQQBUSDT", "name": "Invesco QQQ Trust (Nasdaq 100)", "sector": "US Indices & ETFs", "ticker": "QQQ"},
    "TQQQ": {"symbol": "TQQQBUSDT", "name": "ProShares UltraPro QQQ (3x)", "sector": "US Indices & ETFs", "ticker": "TQQQ"},
    "SMH": {"symbol": "SMHBUSDT", "name": "VanEck Semiconductor ETF", "sector": "US Indices & ETFs", "ticker": "SMH"},
    "SOXL": {"symbol": "SOXLBUSDT", "name": "Direxion Daily Semi Bull 3X", "sector": "US Indices & ETFs", "ticker": "SOXL"},
    "SOXS": {"symbol": "SOXSBUSDT", "name": "Direxion Daily Semi Bear 3X", "sector": "US Indices & ETFs", "ticker": "SOXS"},
    "NFLX": {"symbol": "NFLXBUSDT", "name": "Netflix, Inc.", "sector": "Fintech & Tech", "ticker": "NFLX"},
    "BABA": {"symbol": "BABABUSDT", "name": "Alibaba Group Holding", "sector": "Fintech & Tech", "ticker": "BABA"},
    "GME": {"symbol": "GMEBUSDT", "name": "GameStop Corp.", "sector": "Fintech & Tech", "ticker": "GME"},
    "PYPL": {"symbol": "PYPLBUSDT", "name": "PayPal Holdings, Inc.", "sector": "Fintech & Tech", "ticker": "PYPL"},
    "ORCL": {"symbol": "ORCLBUSDT", "name": "Oracle Corporation", "sector": "Fintech & Tech", "ticker": "ORCL"},
    "IBM": {"symbol": "IBMBUSDT", "name": "International Business Machines", "sector": "Fintech & Tech", "ticker": "IBM"},
    "DELL": {"symbol": "DELLBUSDT", "name": "Dell Technologies Inc.", "sector": "Fintech & Tech", "ticker": "DELL"},
    "GS": {"symbol": "GSBUSDT", "name": "Goldman Sachs Group", "sector": "Fintech & Tech", "ticker": "GS"}
}

# Default Auto-Trader Bot Configurations

DEFAULT_TOTAL_CAPITAL = float(os.getenv("DEFAULT_TOTAL_CAPITAL", "1000.0"))
DEFAULT_SIZING_MODE = os.getenv("DEFAULT_SIZING_MODE", "fixed")  # "fixed", "percent_capital", "risk_pct"
DEFAULT_AMOUNT_PER_TRADE = float(os.getenv("DEFAULT_AMOUNT_PER_TRADE", "50.0"))
DEFAULT_TRADE_SIZE_PCT = float(os.getenv("DEFAULT_TRADE_SIZE_PCT", "5.0"))
DEFAULT_RISK_PER_TRADE_PCT = float(os.getenv("DEFAULT_RISK_PER_TRADE_PCT", "2.0"))
DEFAULT_DAILY_PROFIT_TARGET = float(os.getenv("DEFAULT_DAILY_PROFIT_TARGET", "100.0"))
DEFAULT_TRAILING_STOP_ENABLED = os.getenv("DEFAULT_TRAILING_STOP_ENABLED", "False").lower() in ("true", "1", "yes")
DEFAULT_TRAILING_STOP_CALLBACK_PCT = float(os.getenv("DEFAULT_TRAILING_STOP_CALLBACK_PCT", "1.5"))
DEFAULT_STRATEGY_FILTER = os.getenv("DEFAULT_STRATEGY_FILTER", "ALL")
