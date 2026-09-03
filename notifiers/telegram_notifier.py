import requests
from pathlib import Path
from typing import Optional

class TelegramNotifier:
    """Sends instant daily job alerts & attaches the Excel report via Telegram Bot (100% Free & Unlimited)."""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token.strip()
        self.chat_id = chat_id.strip()

    def send_summary_and_file(self, summary_text: str, excel_path: Optional[Path] = None) -> bool:
        if not self.bot_token or not self.chat_id:
            print("[⚠️ Telegram Notifier] Bot token or Chat ID missing.")
            return False

        try:
            # 1. Send Text Summary
            url_msg = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": summary_text
            }
            resp = requests.post(url_msg, json=payload, timeout=20)

            # 2. Send Excel File Document directly to phone
            if excel_path and excel_path.exists():
                url_doc = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"
                with open(excel_path, "rb") as doc:
                    files = {"document": (excel_path.name, doc, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
                    data = {"chat_id": self.chat_id, "caption": "📊 Attached: Daily 6-Sheet Excel Report"}
                    requests.post(url_doc, data=data, files=files, timeout=30)

            if resp.status_code == 200:
                print(f"[📱 Telegram Notifier] Alert & Excel delivered successfully to Telegram!")
                return True
            else:
                print(f"[❌ Telegram Notifier Error] {resp.text}")
                return False

        except Exception as e:
            print(f"[❌ Telegram Notifier Error] {e}")
            return False
