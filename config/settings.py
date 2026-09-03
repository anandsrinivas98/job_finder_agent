import os
from pathlib import Path
from typing import Dict, Any, List
import yaml
from dotenv import load_dotenv

# Base Directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / ".env")

class AppConfig:
    """Application Configuration Holder"""

    def __init__(self):
        # Config file path
        self.yaml_path = BASE_DIR / "config" / "settings.yaml"
        self.yaml_data = self._load_yaml()

        # Apify
        self.apify_api_token = os.getenv("APIFY_API_TOKEN", "").strip()

        # Resume
        resume_env = os.getenv("RESUME_PATH", "resume/sample_resume.md")
        self.resume_path = (BASE_DIR / resume_env) if not Path(resume_env).is_absolute() else Path(resume_env)

        # LLM Provider
        self.llm_provider = os.getenv("LLM_PROVIDER", "gemini").lower()
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()

        # Email
        self.email_enabled = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "").strip() or os.getenv("EMAIL_SENDER", "").strip()
        self.smtp_password = os.getenv("SMTP_PASSWORD", "").strip() or os.getenv("EMAIL_PASSWORD", "").strip()
        self.email_sender = os.getenv("EMAIL_SENDER", "").strip()
        self.email_recipient = os.getenv("EMAIL_RECIPIENT", self.email_sender).strip()

        # WhatsApp
        self.whatsapp_enabled = os.getenv("WHATSAPP_ENABLED", "false").lower() == "true"
        self.whatsapp_provider = os.getenv("WHATSAPP_PROVIDER", "green_api").lower()
        self.callmebot_phone = os.getenv("CALLMEBOT_PHONE", "")
        self.callmebot_api_key = os.getenv("CALLMEBOT_API_KEY", "")
        self.twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.twilio_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.twilio_from = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
        self.twilio_to = os.getenv("TWILIO_WHATSAPP_TO", "")
        self.green_instance_id = os.getenv("GREEN_API_INSTANCE_ID", "").strip()
        self.green_api_token = os.getenv("GREEN_API_TOKEN", "").strip()

        # Telegram (100% Free & Unlimited Mobile Alerts + Direct File Attachment)
        self.telegram_enabled = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

        # Ntfy.sh (100% Open Source Free Push Notifications - Zero Accounts/No Limits)
        self.ntfy_enabled = os.getenv("NTFY_ENABLED", "false").lower() == "true"
        self.ntfy_topic = os.getenv("NTFY_TOPIC", "").strip()

        # Discord Webhook (100% Free Forever)
        self.discord_enabled = os.getenv("DISCORD_ENABLED", "false").lower() == "true"
        self.discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

        # Google Drive
        self.gdrive_enabled = os.getenv("GDRIVE_ENABLED", "false").lower() == "true"
        self.gdrive_folder_id = os.getenv("GDRIVE_FOLDER_ID", "")
        gdrive_cred = os.getenv("GDRIVE_SERVICE_ACCOUNT_JSON", "config/gdrive_service_account.json")
        self.gdrive_cred_path = (BASE_DIR / gdrive_cred) if not Path(gdrive_cred).is_absolute() else Path(gdrive_cred)

        # Execution parameters
        self.daily_run_time = os.getenv("DAILY_RUN_TIME", "08:00")
        self.target_daily_jobs = int(os.getenv("TARGET_DAILY_JOBS", "25"))
        self.min_match_score = float(os.getenv("MIN_MATCH_SCORE", "70.0"))

        # Paths & Database
        self.reports_dir = BASE_DIR / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = BASE_DIR / "jobs_history.db"
        self.database_url = os.getenv("DATABASE_URL", "").strip()

    def _load_yaml(self) -> Dict[str, Any]:
        if self.yaml_path.exists():
            with open(self.yaml_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    @property
    def target_categories(self) -> Dict[str, Any]:
        return self.yaml_data.get("target_categories", {})

    @property
    def locations(self) -> List[str]:
        return self.yaml_data.get("search_criteria", {}).get("locations", {}).get("priority_order", ["India", "Remote"])

    @property
    def max_experience_years(self) -> float:
        return float(self.yaml_data.get("search_criteria", {}).get("max_experience_years", 2.0))

config = AppConfig()
