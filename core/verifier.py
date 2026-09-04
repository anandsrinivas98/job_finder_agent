"""
Multi-Dimensional Verification Engine for V2 AI Job Hunting Agent.
Validates company legitimacy, application page availability, experience constraints, and India eligibility.
"""

import re
import urllib.parse
from typing import Dict, Any, List, Tuple
from core.models import VerificationStatus, PostedDateStatus, FreshnessState

class JobVerifier:
    """
    Evaluates discovered jobs against 7 verification dimensions:
    1. company_domain_verified
    2. application_page_verified
    3. posting_active
    4. posting_date_verified
    5. location_verified
    6. experience_verified
    7. india_eligibility_verified
    """

    def __init__(self, max_experience_years: int = 3):
        self.max_experience_years = max_experience_years

        # Disqualification regex patterns
        self.senior_keywords = re.compile(
            r'\b(senior|sr\.?|lead|principal|staff|architect|director|vp|head\s+of|manager|expert|specialist\s+iv)\b',
            re.IGNORECASE
        )
        self.high_exp_pattern = re.compile(
            r'\b([4-9]|1[0-9]|20)\s*(?:\+|-\s*\d+)?\s*(?:years?|yrs?)\b',
            re.IGNORECASE
        )
        self.spam_keywords = re.compile(
            r'\b(registration fee|pay to apply|telegram task|earn per click|deposit required|unpaid training fee)\b',
            re.IGNORECASE
        )

    def verify_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes verification checks on a single job record.
        Updates verification flags and returns the verified dictionary.
        """
        title = str(job.get("title", "")).strip()
        company = str(job.get("company", "")).strip()
        desc = str(job.get("description", "")).strip()
        loc = str(job.get("location", "")).strip().lower()
        url = str(job.get("job_url", "")).strip()
        work_mode = str(job.get("work_mode", "")).strip()
        posted_date = str(job.get("posted_date", "")).strip()

        combined_text = f"{title} {desc} {company}"

        # 1. URL Protocol & Safety Check
        is_safe_url = bool(url and (url.startswith("http://") or url.startswith("https://")))
        app_page_verified = is_safe_url and not any(p in url.lower() for p in ["javascript:", "file:", "data:"])

        # 2. Company Domain Verification
        comp_url = str(job.get("company_website", "")).strip()
        domain_verified = bool(comp_url and comp_url.startswith("http") and "google.com/search" not in comp_url)

        # 3. Spam / Fake / Fee Scheme Check
        is_spam = bool(self.spam_keywords.search(combined_text))

        # 4. Experience Constraint Check
        is_senior_title = bool(self.senior_keywords.search(title))
        has_high_exp_req = bool(self.high_exp_pattern.search(desc[:1500]))
        exp_verified = not is_senior_title and not has_high_exp_req and not is_spam

        # 5. Location & India Eligibility Check
        is_remote = "remote" in work_mode.lower() or "remote" in loc or bool(job.get("is_remote"))
        india_eligible = True
        if is_remote:
            # If international remote, check for explicit India exclusion
            if any(k in loc for k in ["us only", "uk only", "eu only", "north america only", "latam only"]):
                india_eligible = False
            else:
                india_eligible = True
        else:
            india_eligible = any(k in loc for k in ["india", "bengaluru", "bangalore", "karnataka", "chennai", "hyderabad", "pune", "mumbai", "delhi", "noida", "gurgaon", "gurugram", "kochi", "coimbatore", "ahmedabad"]) or not loc

        # 6. Posting Date Verification
        date_verified = posted_date not in ["Date not verified", "Recently posted", "", None]

        # 7. Posting Active Check (Rejects obvious closed markers)
        posting_active = not any(k in combined_text.lower() for k in ["no longer accepting applications", "job is closed", "position filled", "expired job"])

        # Compute Overall Status
        if is_spam or not exp_verified or not app_page_verified or not india_eligible or not posting_active:
            overall_status = VerificationStatus.REJECTED.value
        elif domain_verified and app_page_verified and exp_verified and india_eligible and date_verified:
            overall_status = VerificationStatus.VERIFIED.value
        elif app_page_verified and exp_verified and india_eligible:
            overall_status = VerificationStatus.PARTIALLY_VERIFIED.value
        else:
            overall_status = VerificationStatus.UNVERIFIED.value

        # Update record flags
        job["company_domain_verified"] = domain_verified
        job["application_page_verified"] = app_page_verified
        job["posting_active"] = posting_active
        job["posting_date_verified"] = date_verified
        job["location_verified"] = bool(loc)
        job["experience_verified"] = exp_verified
        job["india_eligibility_verified"] = india_eligible
        job["verification_status"] = overall_status

        return job

    def filter_verified_jobs(self, jobs: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """
        Filters and verifies a list of jobs, separating valid opportunities from rejected ones.
        Returns:
            (qualified_jobs, audit_metrics)
        """
        qualified: List[Dict[str, Any]] = []
        metrics = {
            "total_evaluated": len(jobs),
            "fully_verified": 0,
            "partially_verified": 0,
            "unverified": 0,
            "rejected_senior_exp": 0,
            "rejected_ineligible_loc": 0,
            "rejected_spam_broken": 0,
            "total_passed": 0
        }

        for j in jobs:
            v_job = self.verify_job(j)
            status = v_job.get("verification_status")

            if status == VerificationStatus.VERIFIED.value:
                metrics["fully_verified"] += 1
                qualified.append(v_job)
            elif status == VerificationStatus.PARTIALLY_VERIFIED.value:
                metrics["partially_verified"] += 1
                qualified.append(v_job)
            else:
                if not v_job.get("experience_verified"):
                    metrics["rejected_senior_exp"] += 1
                elif not v_job.get("india_eligibility_verified"):
                    metrics["rejected_ineligible_loc"] += 1
                else:
                    metrics["rejected_spam_broken"] += 1

        metrics["total_passed"] = len(qualified)
        return qualified, metrics
