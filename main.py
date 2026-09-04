import os
import sys
import argparse
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

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
from core.models import JobRecord, MatchBreakdown, VerificationStatus, FreshnessState, JobStatus
from core.resume_parser import ResumeParser
from core.job_scraper import JobScraperAggregator, SourceExecutionMetrics
from core.verifier import JobVerifier
from core.deduplicator import SemanticDeduplicator
from core.matcher import JobMatcher
from core.db import JobHistoryDB
from core.excel_generator import ExcelReportGenerator
from core.logger import ExecutionLogger, ExecutionLog
from notifiers.email_notifier import EmailNotifier
from notifiers.whatsapp_notifier import WhatsAppNotifier
from notifiers.telegram_notifier import TelegramNotifier
from notifiers.ntfy_notifier import NtfyNotifier
from notifiers.discord_notifier import DiscordNotifier
from notifiers.gdrive_uploader import GDriveUploader

def run_job_hunt_pipeline(dry_run: bool = False):
    """Executes the complete V2 daily job hunt workflow with structured audit logging."""
    start_time = datetime.now()
    today_str = start_time.strftime("%Y-%m-%d")

    exec_logger = ExecutionLogger()
    run_log = exec_logger.create_log()

    print("\n" + "="*70)
    print(f"🚀 STARTING V2 AI JOB HUNTING PIPELINE — {today_str} [{run_log.run_id}]")
    print("="*70)

    try:
        # 1. Parse Resume (Source of Truth)
        print(f"\n[1/7] 📄 Parsing Candidate Profile: {config.resume_path}")
        parser = ResumeParser(config.resume_path)
        profile = parser.parse()
        skills_count = len(profile.get("skills", []))
        target_roles = profile.get("target_roles", ["Software Engineer", "AI Engineer"])
        print(f"      ✅ Extracted {skills_count} skills, {len(target_roles)} target roles.")

        # 2. Multi-Source Discovery & Normalization
        print("\n[2/7] 🔍 Multi-Source Discovery & Normalization (Major Boards, Remote APIs, Dev Communities, ATS)...")
        scraper = JobScraperAggregator(search_window_hours=config.search_window_hours)
        raw_normalized_jobs, source_metrics = scraper.fetch_all(
            target_roles=target_roles,
            locations=config.locations
        )

        run_log.sources_attempted = sum(1 for m in source_metrics.values() if m.attempted)
        run_log.sources_successful = sum(1 for m in source_metrics.values() if m.successful)
        run_log.raw_jobs = len(raw_normalized_jobs)
        run_log.normalized_jobs = len(raw_normalized_jobs)
        run_log.source_breakdown = {k: v.to_dict() for k, v in source_metrics.items()}

        print("\n--- 📊 Source Execution Metrics ---")
        for name, m in source_metrics.items():
            status_icon = "✅" if m.successful else "⚠️"
            print(f"  {status_icon} [{m.category}] {name}: Attempted={m.attempted}, Raw={m.raw_jobs}, Success={m.successful}" + (f" ({m.failure_reason})" if m.failure_reason else ""))

        if not raw_normalized_jobs:
            print("[⚠️ Pipeline] No jobs retrieved. Check network connection or search criteria.")
            run_log.warnings.append("No jobs retrieved during discovery.")
            run_log.excel_status = "SKIPPED_EMPTY"
            exec_logger.save_log(run_log)
            return

        # 3. Active Job Verification (7-Dimension Check)
        print(f"\n[3/7] 🛡️ Verifying Job Legitimacy, Experience Limits & India Eligibility...")
        verifier = JobVerifier(max_experience_years=config.max_experience_years)
        verified_jobs, verification_metrics = verifier.filter_verified_jobs(raw_normalized_jobs)
        
        run_log.verified_jobs = len(verified_jobs)
        run_log.rejected_jobs = verification_metrics['rejected_senior_exp'] + verification_metrics['rejected_ineligible_loc'] + verification_metrics['rejected_spam_broken']

        print(f"      Evaluated: {verification_metrics['total_evaluated']} | Verified: {verification_metrics['fully_verified']} | Partially: {verification_metrics['partially_verified']}")
        print(f"      Rejected Senior/Exp: {verification_metrics['rejected_senior_exp']} | Ineligible Loc: {verification_metrics['rejected_ineligible_loc']} | Spam/Invalid: {verification_metrics['rejected_spam_broken']}")
        print(f"      ✅ Total Passed Verification: {len(verified_jobs)}")

        # 4. Semantic Cross-Board Deduplication (4-Tier Engine)
        print(f"\n[4/7] 🧬 Performing 4-Tier Semantic Deduplication across sources...")
        deduplicator = SemanticDeduplicator()
        deduped_jobs, dedup_metrics = deduplicator.deduplicate(verified_jobs)

        run_log.duplicates = dedup_metrics['exact_duplicates'] + dedup_metrics['strong_duplicates'] + dedup_metrics['semantic_duplicates']

        print(f"      Raw Ingested: {dedup_metrics['total_raw']} | Exact Dupes: {dedup_metrics['exact_duplicates']} | Strong Dupes: {dedup_metrics['strong_duplicates']} | Semantic Dupes: {dedup_metrics['semantic_duplicates']}")
        print(f"      ✅ Unique Canonical Opportunities: {len(deduped_jobs)}")

        # 5. Profile Match Scoring & Qualification Ranking (V2 7-Factor Matrix)
        print(f"\n[5/7] 🎯 Scoring & Qualifying against Candidate Profile (Threshold: {config.min_match_score}%)...")
        matcher = JobMatcher(
            profile=profile,
            min_match_score=config.min_match_score,
            gemini_api_key=config.gemini_api_key,
            groq_api_key=config.groq_api_key,
            llm_provider=config.llm_provider
        )
        ranked_jobs = matcher.filter_and_rank(deduped_jobs, target_count=config.target_daily_jobs)
        run_log.qualified_jobs = len(ranked_jobs)
        print(f"      ✅ Selected {len(ranked_jobs)} top qualified opportunities matching threshold.")

        # 6. Database History & State Machine (NEW, UPDATED, STILL OPEN, EXPIRED)
        print(f"\n[6/7] 💾 Updating Job History State Machine (SQLite / Cloud PostgreSQL)...")
        db = JobHistoryDB(db_path=config.db_path, database_url=config.database_url)
        final_jobs = []
        for job in ranked_jobs:
            enriched_job = db.upsert_and_classify_job(job)
            final_jobs.append(enriched_job)

        # Calculate Breakdown & Category Stats
        new_count = sum(1 for j in final_jobs if j.get("status") == "NEW")
        updated_count = sum(1 for j in final_jobs if j.get("status") == "UPDATED")
        still_open_count = sum(1 for j in final_jobs if j.get("status") == "STILL OPEN")
        software_count = sum(1 for j in final_jobs if j.get("category") == "Software / Development")
        ai_count = sum(1 for j in final_jobs if j.get("category") == "AI / ML / GenAI")
        qa_count = sum(1 for j in final_jobs if j.get("category") == "Testing / QA")
        analyst_count = sum(1 for j in final_jobs if j.get("category") == "Analyst / Entry Level")
        intern_count = sum(1 for j in final_jobs if j.get("job_type") == "Internship" or j.get("is_internship", False))
        remote_count = sum(1 for j in final_jobs if j.get("work_mode") == "Remote" or j.get("is_remote", False))

        run_log.new_jobs = new_count
        run_log.updated_jobs = updated_count
        run_log.still_open_jobs = still_open_count

        best_job = final_jobs[0] if final_jobs else {}
        best_company = best_job.get("company", "N/A")
        best_role = best_job.get("title", "N/A")
        best_score = best_job.get("match_score", 0)

        print(f"      State Machine: NEW={new_count}, UPDATED={updated_count}, STILL_OPEN={still_open_count}")

        # 7. Multi-Sheet Professional Excel Report
        print(f"\n[7/7] 📊 Generating Professional 6-Sheet Excel Report...")
        try:
            excel_gen = ExcelReportGenerator(output_dir=config.reports_dir)
            excel_path = excel_gen.generate_daily_report(final_jobs, custom_date=today_str)
            run_log.excel_status = "SUCCESS"
        except Exception as e:
            run_log.excel_status = "FAILED"
            run_log.errors.append(f"Excel Generation Error: {e}")
            raise e

        # Google Drive Sync (Owner-Only Private Mode)
        drive_link = None
        if config.gdrive_enabled and not dry_run:
            print("\n[☁️ GDrive] Syncing report to Google Drive...")
            try:
                uploader = GDriveUploader(
                    folder_id=config.gdrive_folder_id,
                    service_account_path=config.gdrive_cred_path,
                    local_sync_path=config.gdrive_local_path
                )
                drive_link = uploader.upload_file(excel_path)
                run_log.drive_status = "SUCCESS" if drive_link else "FAILED"
            except Exception as e:
                run_log.drive_status = "FAILED"
                run_log.errors.append(f"Drive Upload Error: {e}")
                print(f"[⚠️ GDrive Error] Upload failed: {e}")
        elif not dry_run:
            run_log.drive_status = "SKIPPED_NOT_CONFIGURED"

        # Format Standard Notification Text with APPLY FIRST Section
        top_apply_first = [j for j in final_jobs if j.get("status") == "NEW"][:3]
        apply_first_text = ""
        if top_apply_first:
            apply_first_text = "\n\n🎯 APPLY FIRST (Top New Opportunities):\n"
            for i, j in enumerate(top_apply_first, start=1):
                apply_first_text += f"{i}. {j.get('company')} — {j.get('title')} ({j.get('match_score')}%)\n   👉 {j.get('job_url')}\n"

        notification_msg = (
            f"📅 Daily Job Hunt — {today_str}\n\n"
            f"🆕 New: {new_count:02d} | 🔄 Updated: {updated_count:02d} | ⏳ Still Open: {still_open_count:02d}\n"
            f"💻 Software: {software_count:02d} | 🤖 AI: {ai_count:02d} | 🧪 QA: {qa_count:02d} | 📊 Analyst: {analyst_count:02d}\n"
            f"🎓 Internships: {intern_count:02d} | 🌐 Remote: {remote_count:02d}\n\n"
            f"🔥 Best Match: {best_company} — {best_role} — {best_score}%\n"
            f"📊 Excel Report: {drive_link if drive_link else excel_path.name}"
            f"{apply_first_text}"
        )

        print("\n" + "-"*40)
        print("📋 DAILY SUMMARY NOTIFICATION:")
        print("-"*40)
        print(notification_msg)
        print("-"*40)

        # Dispatch Notifications with graceful isolation
        if dry_run:
            print("\n[ℹ️ Dry Run] Notifications skipped (--dry-run flag is active).")
            run_log.email_status = "SKIPPED_DRY_RUN"
        else:
            print("\n[📡 Notifier] Dispatching Notifications...")
            stats_dict = {
                "date": today_str,
                "total": len(final_jobs),
                "new_count": new_count,
                "updated_count": updated_count,
                "still_open_count": still_open_count,
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

            # Email Notification (Brevo SMTP)
            if config.email_enabled:
                try:
                    email_notifier = EmailNotifier(
                        smtp_server=config.smtp_server,
                        smtp_port=config.smtp_port,
                        sender=config.email_sender,
                        user=config.smtp_user,
                        password=config.smtp_password,
                        recipient=config.email_recipient
                    )
                    email_success = email_notifier.send_report(notification_msg, excel_path, stats_dict)
                    run_log.email_status = "SUCCESS" if email_success else "FAILED"
                except Exception as e:
                    run_log.email_status = "FAILED"
                    run_log.errors.append(f"Email Dispatch Error: {e}")
                    print(f"[⚠️ Email Error] {e}")

            # WhatsApp Notification
            if config.whatsapp_enabled:
                try:
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
                except Exception as e:
                    run_log.warnings.append(f"WhatsApp Error: {e}")

            # Telegram Notification
            if config.telegram_enabled:
                try:
                    tg_notifier = TelegramNotifier(
                        bot_token=config.telegram_bot_token,
                        chat_id=config.telegram_chat_id
                    )
                    tg_notifier.send_summary_and_file(notification_msg, excel_path)
                except Exception as e:
                    run_log.warnings.append(f"Telegram Error: {e}")

            # Ntfy.sh Notification
            if config.ntfy_enabled:
                try:
                    ntfy_notifier = NtfyNotifier(topic=config.ntfy_topic)
                    ntfy_notifier.send_notification(notification_msg, excel_path)
                except Exception as e:
                    run_log.warnings.append(f"Ntfy Error: {e}")

            # Discord Webhook Notification
            if config.discord_enabled:
                try:
                    discord_notifier = DiscordNotifier(webhook_url=config.discord_webhook_url)
                    discord_notifier.send_notification(notification_msg, excel_path)
                except Exception as e:
                    run_log.warnings.append(f"Discord Error: {e}")

    except Exception as e:
        run_log.errors.append(f"Fatal Pipeline Exception: {e}")
        print(f"\n[❌ Pipeline Fatal Error] {e}")
    finally:
        duration = (datetime.now() - start_time).total_seconds()
        run_log.duration_seconds = round(duration, 1)
        exec_logger.save_log(run_log)
        print(f"\n✨ Daily Pipeline finished in {duration:.1f}s. Have a great day!")
        print("="*70 + "\n")

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
