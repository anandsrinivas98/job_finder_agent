import os
import sys
import argparse
import time
from datetime import datetime
from pathlib import Path
# Optional schedule library for background daemon mode
try:
    import schedule
except ImportError:
    schedule = None

# Ensure Windows stdout supports UTF-8 emojis without charmap errors
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config.settings import config
from core.resume_parser import ResumeParser
from core.job_scraper import JobScraperAggregator
from core.matcher import JobMatcher
from core.db import JobHistoryDB
from core.excel_generator import ExcelReportGenerator
from notifiers.email_notifier import EmailNotifier
from notifiers.whatsapp_notifier import WhatsAppNotifier
from notifiers.telegram_notifier import TelegramNotifier
from notifiers.ntfy_notifier import NtfyNotifier
from notifiers.discord_notifier import DiscordNotifier
from notifiers.gdrive_uploader import GDriveUploader

def run_job_hunt_pipeline(dry_run: bool = False):
    """Executes the complete daily job hunt workflow."""
    start_time = datetime.now()
    today_str = start_time.strftime("%Y-%m-%d")

    print("\n" + "="*60)
    print(f"🚀 STARTING DAILY AI JOB HUNTING PIPELINE — {today_str}")
    print("="*60)

    # 1. Parse Resume (Source of Truth)
    print(f"\n[1/6] 📄 Parsing Resume from: {config.resume_path}")
    parser = ResumeParser(config.resume_path)
    profile = parser.parse()
    skills_count = len(profile.get("skills", []))
    print(f"      Extracted {skills_count} skills, {len(profile.get('target_roles', []))} target roles.")

    # 2. Fetch Jobs from Apify + Free Direct Sources
    print("\n[2/6] 🔍 Aggregating Job Opportunities (Apify & Free Tech Boards)...")
    scraper = JobScraperAggregator(apify_token=config.apify_api_token)
    raw_jobs = scraper.fetch_all(
        target_roles=profile.get("target_roles", ["Software Engineer", "AI Engineer"]),
        locations=config.locations
    )

    if not raw_jobs:
        print("[⚠️ Pipeline] No jobs retrieved. Check network connection or search criteria.")
        return

    # 3. Match & Rank against Candidate Profile
    print(f"\n[3/6] 🎯 Scoring & Filtering against Resume (Min Score: {config.min_match_score}%)...")
    matcher = JobMatcher(
        profile=profile,
        min_match_score=config.min_match_score,
        gemini_api_key=config.gemini_api_key,
        groq_api_key=config.groq_api_key,
        llm_provider=config.llm_provider
    )
    ranked_jobs = matcher.filter_and_rank(raw_jobs, target_count=config.target_daily_jobs)
    print(f"      Selected {len(ranked_jobs)} top qualified opportunities.")

    # 4. Deduplicate and Update Database History (SQLite / Cloud PostgreSQL)
    print("\n[4/6] 💾 Updating Job History & Classifying (NEW, UPDATED, STILL OPEN)...")
    db = JobHistoryDB(db_path=config.db_path, database_url=config.database_url)
    final_jobs = []
    for job in ranked_jobs:
        enriched_job = db.upsert_and_classify_job(job)
        final_jobs.append(enriched_job)

    # Calculate Summary Stats
    new_count = sum(1 for j in final_jobs if j.get("status") == "NEW")
    software_count = sum(1 for j in final_jobs if j.get("category") == "Software / Development")
    ai_count = sum(1 for j in final_jobs if j.get("category") == "AI / ML / GenAI")
    qa_count = sum(1 for j in final_jobs if j.get("category") == "Testing / QA")
    analyst_count = sum(1 for j in final_jobs if j.get("category") == "Analyst / Entry Level")
    intern_count = sum(1 for j in final_jobs if j.get("is_internship", False))
    remote_count = sum(1 for j in final_jobs if j.get("is_remote", False))

    best_job = final_jobs[0] if final_jobs else {}
    best_company = best_job.get("company", "N/A")
    best_role = best_job.get("title", "N/A")
    best_score = best_job.get("match_score", 0)

    # 5. Generate Multi-Sheet Excel Report
    print("\n[5/6] 📊 Generating Professional 6-Sheet Excel Report...")
    excel_gen = ExcelReportGenerator(output_dir=config.reports_dir)
    excel_path = excel_gen.generate_daily_report(final_jobs, custom_date=today_str)

    # Google Drive Sync (if enabled)
    drive_link = None
    if config.gdrive_enabled and not dry_run:
        print("\n[☁️ GDrive] Syncing report to Google Drive...")
        uploader = GDriveUploader(
            folder_id=config.gdrive_folder_id,
            service_account_path=config.gdrive_cred_path,
            local_sync_path=config.gdrive_local_path
        )
        drive_link = uploader.upload_file(excel_path)

    # Format Standard Notification Text
    notification_msg = (
        f"📅 Daily Job Hunt — {today_str}\n\n"
        f"🆕 New: {new_count:02d}\n"
        f"💻 Software: {software_count:02d}\n"
        f"🤖 AI/ML/GenAI: {ai_count:02d}\n"
        f"🧪 Testing/QA: {qa_count:02d}\n"
        f"📊 Analyst: {analyst_count:02d}\n"
        f"🎓 Internships: {intern_count:02d}\n"
        f"🌐 Remote: {remote_count:02d}\n\n"
        f"🔥 Best Match: {best_company} — {best_role} — {best_score}%\n\n"
        f"📊 Excel Report: {drive_link if drive_link else excel_path.name}"
    )

    print("\n" + "-"*40)
    print("📋 DAILY SUMMARY NOTIFICATION:")
    print("-"*40)
    print(notification_msg)
    print("-"*40)

    # 6. Dispatch Notifications
    if dry_run:
        print("\n[ℹ️ Dry Run] Notifications skipped (--dry-run flag is active).")
    else:
        print("\n[6/6] 📡 Dispatching Notifications...")
        stats_dict = {
            "date": today_str,
            "total": len(final_jobs),
            "new_count": new_count,
            "software_count": software_count,
            "ai_count": ai_count,
            "qa_count": qa_count,
            "analyst_count": analyst_count,
            "intern_count": intern_count,
            "remote_count": remote_count,
            "best_company": best_company,
            "best_role": best_role,
            "best_score": best_score
        }

        # Email Notification
        if config.email_enabled:
            email_notifier = EmailNotifier(
                smtp_server=config.smtp_server,
                smtp_port=config.smtp_port,
                sender=config.email_sender,
                user=config.smtp_user,
                password=config.smtp_password,
                recipient=config.email_recipient
            )
            email_notifier.send_report(notification_msg, excel_path, stats_dict)

        # WhatsApp Notification
        if config.whatsapp_enabled:
            wa_notifier = WhatsAppNotifier(
                provider=config.whatsapp_provider,
                phone=config.callmebot_phone,
                api_key=config.callmebot_api_key,
                twilio_sid=config.twilio_sid,
                twilio_token=config.twilio_token,
                twilio_from=config.twilio_from,
                twilio_to=config.twilio_to,
                green_instance_id=config.green_instance_id,
                green_api_token=config.green_api_token
            )
            wa_notifier.send_summary(notification_msg, excel_path)

        # Telegram Notification (Instant Mobile + Excel File)
        if config.telegram_enabled:
            tg_notifier = TelegramNotifier(
                bot_token=config.telegram_bot_token,
                chat_id=config.telegram_chat_id
            )
            tg_notifier.send_summary_and_file(notification_msg, excel_path)

        # Ntfy.sh Notification (100% Open-Source, Zero Accounts, Free Phone Push)
        if config.ntfy_enabled:
            ntfy_notifier = NtfyNotifier(topic=config.ntfy_topic)
            ntfy_notifier.send_notification(notification_msg, excel_path)

        # Discord Webhook Notification (100% Free Forever)
        if config.discord_enabled:
            discord_notifier = DiscordNotifier(webhook_url=config.discord_webhook_url)
            discord_notifier.send_notification(notification_msg, excel_path)

    duration = (datetime.now() - start_time).total_seconds()
    print(f"\n✨ Daily Pipeline finished in {duration:.1f}s. Have a great day!")
    print("="*60 + "\n")

def start_scheduler():
    """Runs the scheduler continuously in the background."""
    if schedule is None:
        print("[⚠️ Error] 'schedule' package is not installed. Please run: pip install schedule")
        return

    run_time = config.daily_run_time
    print(f"⏰ Daily Job Hunter scheduler started. Scheduled to run every day at {run_time}...")
    schedule.every().day.at(run_time).do(run_job_hunt_pipeline)

    # Run initial pipeline once at startup
    run_job_hunt_pipeline()

    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily AI Job Hunting Agent")
    parser.add_argument("--run-now", action="store_true", help="Run the job hunt pipeline immediately once")
    parser.add_argument("--dry-run", action="store_true", help="Run search & Excel generation without sending notifications")
    parser.add_argument("--schedule", action="store_true", help="Run scheduler daemon at configured daily time")

    args = parser.parse_args()

    if args.schedule:
        start_scheduler()
    elif args.dry_run:
        run_job_hunt_pipeline(dry_run=True)
    else:
        # Default action: run now
        run_job_hunt_pipeline(dry_run=False)
