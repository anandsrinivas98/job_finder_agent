import sys
import urllib.parse
import requests
from pathlib import Path
from typing import Dict, Any, Optional

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

class WhatsAppNotifier:
    """Sends concise daily summary alerts and Excel files to WhatsApp."""

    def __init__(self, provider: str = "green_api", phone: str = "", api_key: str = "",
                 twilio_sid: str = "", twilio_token: str = "", twilio_from: str = "", twilio_to: str = "",
                 green_instance_id: str = "", green_api_token: str = ""):
        self.provider = provider.lower().strip()
        self.phone = phone.strip()
        self.api_key = api_key.strip()
        self.twilio_sid = twilio_sid.strip()
        self.twilio_token = twilio_token.strip()
        self.twilio_from = twilio_from.strip()
        self.twilio_to = twilio_to.strip()
        self.green_instance_id = green_instance_id.strip()
        self.green_api_token = green_api_token.strip()

    def send_summary(self, summary_text: str, excel_path: Optional[Path] = None) -> bool:
        if self.provider in ["green_api", "greenapi"]:
            return self._send_green_api(summary_text, excel_path)
        elif self.provider == "callmebot":
            return self._send_callmebot(summary_text)
        elif self.provider == "twilio":
            return self._send_twilio(summary_text)
        elif self.provider == "pywhatkit":
            return self._send_pywhatkit(summary_text)
        else:
            print(f"[⚠️ WhatsApp Notifier] Unknown provider: {self.provider}")
            return False

    def _send_green_api(self, message: str, excel_path: Optional[Path] = None) -> bool:
        """Sends WhatsApp message & optional Excel file via 100% Free Green API Developer instance."""
        if not self.green_instance_id or not self.green_api_token or not self.phone:
            print("[⚠️ WhatsApp Green-API] Instance ID, API Token, or Phone Number missing in .env.")
            return False

        try:
            # Format phone to 91XXXXXXXXXX@c.us
            clean_digits = "".join(filter(str.isdigit, self.phone))
            chat_id = f"{clean_digits}@c.us"

            # 1. Send text message
            msg_url = f"https://api.green-api.com/waInstance{self.green_instance_id}/sendMessage/{self.green_api_token}"
            payload = {
                "chatId": chat_id,
                "message": message
            }
            resp = requests.post(msg_url, json=payload, timeout=25)

            if resp.status_code == 200:
                print(f"[📱 WhatsApp Green-API] Summary text delivered to {chat_id}")
            else:
                print(f"[❌ WhatsApp Green-API Error] Status: {resp.status_code}, Response: {resp.text}")
                return False

            # 2. Send Excel file if provided
            if excel_path and excel_path.exists():
                file_url = f"https://api.green-api.com/waInstance{self.green_instance_id}/sendFileByUpload/{self.green_api_token}"
                with open(excel_path, "rb") as f:
                    files = {"file": (excel_path.name, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
                    file_data = {
                        "chatId": chat_id,
                        "fileName": excel_path.name,
                        "caption": "📊 Here is your Daily Job Hunt Excel Report!"
                    }
                    file_resp = requests.post(file_url, data=file_data, files=files, timeout=40)
                    if file_resp.status_code == 200:
                        print(f"[📎 WhatsApp Green-API] Excel file attachment delivered to {chat_id}")

            return True

        except Exception as e:
            print(f"[❌ WhatsApp Green-API Exception] {e}")
            return False

    def _send_pywhatkit(self, message: str) -> bool:
        """Sends WhatsApp message via local WhatsApp Web session (100% Free, Zero API keys)."""
        if not self.phone:
            print("[⚠️ WhatsApp pywhatkit] Phone number missing.")
            return False
        try:
            import pywhatkit
            clean_phone = self.phone if self.phone.startswith("+") else f"+{self.phone}"
            print(f"[📱 WhatsApp pywhatkit] Opening WhatsApp Web to dispatch message to {clean_phone}...")
            pywhatkit.sendwhatmsg_instantly(clean_phone, message, wait_time=15, tab_close=True)
            print(f"[✅ WhatsApp pywhatkit] Message sent successfully to {clean_phone}")
            return True
        except ImportError:
            print("[⚠️ WhatsApp pywhatkit] Please install pywhatkit: pip install pywhatkit")
            return False
        except Exception as e:
            print(f"[❌ WhatsApp pywhatkit Error] {e}")
            return False

    def _send_callmebot(self, message: str) -> bool:
        """Sends WhatsApp message using free CallMeBot gateway."""
        if not self.phone or not self.api_key:
            print("[⚠️ WhatsApp CallMeBot] Phone number or API key missing.")
            return False

        try:
            clean_phone = self.phone.replace("+", "").replace(" ", "").replace("-", "")
            encoded_text = urllib.parse.quote(message)
            url = f"https://api.callmebot.com/whatsapp.php?phone={clean_phone}&text={encoded_text}&apikey={self.api_key}"

            resp = requests.get(url, timeout=20)
            if resp.status_code == 200:
                print(f"[📱 WhatsApp Notifier] Message sent via CallMeBot to +{clean_phone}")
                return True
            else:
                print(f"[❌ WhatsApp CallMeBot Error] Status: {resp.status_code}, Response: {resp.text}")
                return False
        except Exception as e:
            print(f"[❌ WhatsApp CallMeBot Exception] {e}")
            return False

    def _send_twilio(self, message: str) -> bool:
        """Sends WhatsApp message using Twilio REST API."""
        if not self.twilio_sid or not self.twilio_token or not self.twilio_to:
            print("[⚠️ WhatsApp Twilio] Twilio credentials or destination missing.")
            return False

        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_sid}/Messages.json"
            payload = {
                "From": self.twilio_from,
                "To": self.twilio_to,
                "Body": message
            }
            resp = requests.post(url, data=payload, auth=(self.twilio_sid, self.twilio_token), timeout=20)
            if resp.status_code in [200, 201]:
                print(f"[📱 WhatsApp Notifier] Message sent via Twilio to {self.twilio_to}")
                return True
            else:
                print(f"[❌ WhatsApp Twilio Error] Status: {resp.status_code}, Response: {resp.text}")
                return False
        except Exception as e:
            print(f"[❌ WhatsApp Twilio Exception] {e}")
            return False
