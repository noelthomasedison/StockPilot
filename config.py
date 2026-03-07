import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile") 
STOCKPILOT_MODE = os.getenv("STOCKPILOT_MODE", "free").lower()
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "6"))
DEFAULT_HISTORY_FREE = 6
DEFAULT_HISTORY_PRO = 20

if STOCKPILOT_MODE == "pro":
    MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", DEFAULT_HISTORY_PRO))
else:
    MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", DEFAULT_HISTORY_FREE))
def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}

FAST_PATH = _env_bool("FAST_PATH", True)

APP_TITLE = "StockPilot"
APP_SUBTITLE = "AI-Powered Stock Research Assistant"