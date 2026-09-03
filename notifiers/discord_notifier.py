import requests
from pathlib import Path
from typing import Optional

class DiscordNotifier:
    """Sends 100% Free Forever alerts & attaches Excel to Discord Webhook."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url.strip()

    def send_notification(self, summary_text: str, excel_path: Optional[Path] = None) -> bool:
        if not self.webhook_url:
            print("[⚠️ Discord Notifier] Webhook URL not configured.")
            return False

        try:
            payload = {"content": f"```\n{summary_text}\n```"}
            if excel_path and excel_path.exists():
                with open(excel_path, "rb") as f:
                    files = {"file": (excel_path.name, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
                    resp = requests.post(self.webhook_url, data=payload, files=files, timeout=25)
            else:
                resp = requests.post(self.webhook_url, json=payload, timeout=20)

            if resp.status_code in [200, 204]:
                print(f"[🎮 Discord Notifier] Alert delivered to Discord channel!")
                return True
            else:
                print(f"[❌ Discord Error] {resp.text}")
                return False

        except Exception as e:
            print(f"[❌ Discord Exception] {e}")
            return False
