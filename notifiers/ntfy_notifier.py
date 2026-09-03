import requests
from pathlib import Path
from typing import Optional

class NtfyNotifier:
    """Sends 100% Open-Source, Free Forever Push Notifications to phone via Ntfy (https://ntfy.sh).
    Zero accounts, zero subscriptions, zero trial limits.
    """

    def __init__(self, topic: str):
        self.topic = topic.strip()

    def send_notification(self, summary_text: str, excel_path: Optional[Path] = None) -> bool:
        if not self.topic:
            print("[⚠️ Ntfy Notifier] Topic name not configured.")
            return False

        try:
            url = f"https://ntfy.sh/{self.topic}"
            headers = {
                "Title": "🚀 Daily AI Job Hunt Summary",
                "Priority": "high",
                "Tags": "briefcase,rocket"
            }

            # If Excel file is present, attach it directly to the push notification
            if excel_path and excel_path.exists():
                headers["Filename"] = excel_path.name
                with open(excel_path, "rb") as f:
                    headers["X-Message"] = summary_text.replace("\n", " | ")
                    resp = requests.post(url, data=f, headers=headers, timeout=20)
            else:
                resp = requests.post(url, data=summary_text.encode("utf-8"), headers=headers, timeout=20)

            if resp.status_code == 200:
                print(f"[🔔 Ntfy Notifier] Instant push notification delivered to topic: {self.topic}")
                return True
            else:
                print(f"[❌ Ntfy Error] Status: {resp.status_code}, Response: {resp.text}")
                return False

        except Exception as e:
            print(f"[❌ Ntfy Exception] {e}")
            return False
