import os
import requests

BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")

def send_telegram_alert(message: str) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        print("[ERROR] TG_BOT_TOKEN ya TG_CHAT_ID environment variables nahi mile.")
        return False
        
    url = f"https://api.telegram.org/bot{BOT_TOKEN.strip()}/sendMessage"
    payload = {
        "chat_id": CHAT_ID.strip(),
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=payload, timeout=12)
        
        # Agar Telegram reject kare toh exact reason print karega
        if response.status_code != 200:
            print(f"[ERROR] Telegram API Response: {response.text}")
            return False
            
        print("[OK] Alert Telegram par successfully deliver ho gaya.")
        return True
    except Exception as e:
        print(f"[ERROR] Request failed: {e}")
        return False
