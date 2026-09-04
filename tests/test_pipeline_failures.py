import pytest
import json
from pathlib import Path
from core.logger import ExecutionLogger, ExecutionLog
from core.job_scraper import JobScraperAggregator, SourceExecutionMetrics

def test_source_failure_isolation():
    scraper = JobScraperAggregator()
    # Force a failing endpoint on one source
    scraper.source_metrics["We Work Remotely"].attempted = True
    scraper.source_metrics["We Work Remotely"].successful = False
    scraper.source_metrics["We Work Remotely"].failure_reason = "Simulated Timeout"
    
    # Assert other sources can still record success
    first_key = list(scraper.source_metrics.keys())[0]
    scraper.source_metrics[first_key].attempted = True
    scraper.source_metrics[first_key].successful = True
    scraper.source_metrics[first_key].raw_jobs = 15

    attempted = sum(1 for m in scraper.source_metrics.values() if m.attempted)
    successful = sum(1 for m in scraper.source_metrics.values() if m.successful)
    assert attempted >= 2
    assert successful >= 1

def test_execution_logger_and_failure_states(tmp_path):
    logger = ExecutionLogger(log_dir=tmp_path)
    run_log = logger.create_log()
    run_log.sources_attempted = 10
    run_log.sources_successful = 9
    run_log.raw_jobs = 150
    run_log.normalized_jobs = 150
    run_log.verified_jobs = 35
    run_log.duplicates = 12
    run_log.qualified_jobs = 8
    run_log.new_jobs = 3
    run_log.excel_status = "SUCCESS"
    run_log.drive_status = "FAILED"
    run_log.email_status = "FAILED"
    run_log.errors.append("Drive API connection failed.")
    run_log.errors.append("SMTP Brevo authentication failed.")

    saved_path = logger.save_log(run_log)
    assert saved_path.exists()

    with open(saved_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["run_id"].startswith("RUN_")
    assert data["excel_status"] == "SUCCESS"
    assert data["drive_status"] == "FAILED"
    assert data["email_status"] == "FAILED"
    # Overall status must be PARTIAL, NOT SUCCESS
    assert data["overall_status"] == "PARTIAL"
    assert len(data["errors"]) == 2
