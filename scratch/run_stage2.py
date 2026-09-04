import sys
import os
import json
from pathlib import Path
from datetime import datetime

# Fix stdout encoding for Windows PowerShell
sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.resume_parser import ResumeParser
from core.job_scraper import JobScraperAggregator
from core.matcher import JobMatcher
from core.db import JobHistoryDB
from core.excel_generator import ExcelReportGenerator

def main():
    print("=== STAGE 2: LIVE JOB DISCOVERY & VERIFICATION ===")
    
    # 1. Parse Profile
    resume_path = Path("resume/sample_resume.md")
    parser = ResumeParser(resume_path)
    profile = parser.parse()
    print(f"Candidate: {profile.get('name', 'Srinivas A')}")
    print(f"Skills parsed: {len(profile.get('skills', []))} skills")

    # 2. Ingest Multi-Source Live Postings
    scraper = JobScraperAggregator()
    raw_jobs = scraper.fetch_all(profile.get('target_roles', []), ['Bengaluru, India', 'India', 'Remote'])
    print(f"\n[Raw Ingestion] Discovered {len(raw_jobs)} unique listings.")

    # 3. Match, Score & Rank against Resume
    matcher = JobMatcher(profile=profile, min_match_score=70.0)
    scored_jobs = matcher.filter_and_rank(raw_jobs, target_count=50)
    print(f"[Matching Engine] Filtered & Scored {len(scored_jobs)} qualified jobs (Score >= 70%).")

    # 4. State Tracking & Deduplication
    db = JobHistoryDB(Path("jobs_history.db"))
    classified_jobs = [db.upsert_and_classify_job(j) for j in scored_jobs]
    print(f"[Database Engine] Classified {len(classified_jobs)} opportunities.")

    # 5. Output detailed JSON summary
    output_path = Path("scratch/stage2_results.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_raw": len(raw_jobs),
            "total_scored": len(scored_jobs),
            "jobs": classified_jobs
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\nSaved structured stage 2 results to {output_path}")

if __name__ == "__main__":
    main()
