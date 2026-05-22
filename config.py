import os
import json
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
SETTINGS_FILE = "settings.json"

def get_settings(key, default=None):
    if not os.path.exists(SETTINGS_FILE):
        return default
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get(key, default)
    
def update_settings(key, value):
    data = {}
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    data[key] = value
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)