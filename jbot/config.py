import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
SANDBOX_DIR = Path(os.getenv("JBOT_SANDBOX", str(ROOT_DIR))).resolve()
MEMORY_FILE = Path(os.getenv("JBOT_MEMORY_FILE", str(SANDBOX_DIR / "memory.json")))
HISTORY_FILE = Path(os.getenv("JBOT_HISTORY_FILE", str(SANDBOX_DIR / "history.json")))
SESSIONS_DIR = Path(os.getenv("JBOT_SESSIONS_DIR", str(SANDBOX_DIR / "sessions")))

LLM_API_KEY = os.getenv("USER_LLM_API_KEY") or os.getenv("MERCURY_API_KEY", "")
LLM_BASE_URL = os.getenv("USER_LLM_BASE_URL", "https://api.inceptionlabs.ai/v1").rstrip("/")
LLM_MODEL = os.getenv("USER_LLM_MODEL", "mercury-2")

NEWS_API_KEY = os.getenv("NEWS_API_KEY") or os.getenv("news_api_key", "")
TINYFISH_KEY = os.getenv("TINYFISH_KEY") or os.getenv("tinyfish_key", "")
PAXSENIX_API_KEY = os.getenv(
    "PAXSENIX_API_KEY",
    "sk-paxsenix-9us673unVsPleNg0Kt0yiPWZqjnisgscDZzlHYumKD7DnMDu",
)
PAXSENIX_BASE_URL = os.getenv("PAXSENIX_BASE_URL", "https://api.paxsenix.org").rstrip("/")

MAX_STEPS = int(os.getenv("JBOT_MAX_STEPS", "8"))
REQUEST_TIMEOUT = int(os.getenv("JBOT_TIMEOUT", "60"))
TEMPERATURE = float(os.getenv("JBOT_TEMPERATURE", "0.2"))
HISTORY_LIMIT = int(os.getenv("JBOT_HISTORY_LIMIT", "20"))
