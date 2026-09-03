import urllib.parse
import requests
from typing import Dict, Any

class WhatsAppNotifier:
    """Sends concise daily summary alerts to WhatsApp."""

    def __init__(self, provider: str = "callmebot", phone: str = "", api_key: str = "",
                 twilio_sid: str = "", twilio_token: str = "", twilio_from: str = "", twilio_to: str = ""):
        self.provider = provider.lower()
        self.phone = phone.strip()
        self.api_key = api_key.strip()
        self.twilio_sid = twilio_sid.strip()
        self.twilio_token = twilio_token.strip()
        self.twilio_from = twilio_from.strip()
        self.twilio_to = twilio_to.strip()

    def send_summary(self, summary_text: str) -> bool:
        if self.provider == "callmebot":
            return self._send_callmebot(summary_text)
        elif self.provider == "twilio":
            return self._send_twilio(summary_text)
        elif self.provider == "pywhatkit":
            return self._send_pywhatkit(summary_text)
        else:
            print(f"[⚠️ WhatsApp Notifier] Unknown provider: {self.provider}")
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
