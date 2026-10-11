from pathlib import Path

APP_TITLE = "Comboios Pedro Mata"

ASSETS_DIR = Path(__file__).parent / "assets"
LOGO_WIDE = str(ASSETS_DIR / "logo_wide.png")
LOGO_SQUARE = str(ASSETS_DIR / "logo_square.png")

PAGE_HOME = "views/home.py"
PAGE_CHAT = "views/chat.py"
PAGE_CHAT_URL_PATH = "chat"

SESSION_QUERY_PARAM = "session"
SESSION_STATE_KEY = "session_id"
OPEN_DIALOG_STATE_KEY = "open_dialog"

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
