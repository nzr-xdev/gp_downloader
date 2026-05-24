import os
import json
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
SETTINGS_FILE = "settings.json"

def _load() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        return {}
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(data: dict):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_plan_limits(plan_name: str) -> dict:
    data = _load()
    return data.get("plans", {}).get(plan_name, {})

def update_plan_limit(plan_name: str, limit_key: str, new_value: int):
    data = _load()
    if "plans" in data and plan_name in data["plans"] and limit_key in data["plans"][plan_name]:
        data["plans"][plan_name][limit_key] = new_value
        _save(data)

def get_switches() -> dict:
    data = _load()
    return {
        "maintenance_mode": data.get("maintenance_mode", False),
        "module_Spotify": data.get("module_Spotify", True),
        "module_YouTube": data.get("module_YouTube", True),
        "module_SoundCloud": data.get("module_SoundCloud", True)
    }

def toggle_switch(switch_name: str) -> bool:
    data = _load()
    if switch_name in data:
        data[switch_name] = not data[switch_name]
        _save(data)
        return data[switch_name]
    return False