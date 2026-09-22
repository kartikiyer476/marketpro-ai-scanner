import os
import requests

BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")

def send_telegram_alert(message: str) -> bool:
    """
    Telegram bot ke through alert message bhejta hai.
    Environment variables: TG_BOT_TOKEN, TG_CHAT_ID
    """
    if not BOT_TOKEN or not CHAT_ID:
        print("[ERROR] TG_BOT_TOKEN ya TG_CHAT_ID environment variables nahi mile.")
        return False
        
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=payload, timeout=12)
        response.raise_for_status()
        print("[OK] Alert Telegram par successfully deliver ho gaya.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Telegram alert fail ho gaya: {e}")
        return False
