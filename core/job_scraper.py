import os
import time
import requests
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

class JobScraperAggregator:
    """Aggregates jobs from Apify Actors and Free Direct Sources (RemoteOK, Himalayas, Jobicy, etc.)."""

    def __init__(self, apify_token: str = ""):
        self.apify_token = apify_token.strip()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def fetch_all(self, target_roles: List[str], locations: List[str]) -> List[Dict[str, Any]]:
        """Collects listings from Apify and free APIs."""
        all_jobs: List[Dict[str, Any]] = []

        # 1. Apify Search (if token provided)
        if self.apify_token:
            print("[🔍 JobScraper] Apify Token detected. Querying Apify Actors...")
            apify_jobs = self._fetch_apify_jobs(target_roles, locations)
            print(f"[✅ JobScraper] Retrieved {len(apify_jobs)} jobs from Apify.")
            all_jobs.extend(apify_jobs)
        else:
            print("[ℹ️ JobScraper] No Apify token set. Utilizing Free Open Job Sources & APIs...")

        # 2. Free Open Job Sources (Always active as baseline or enrichment)
        free_jobs = self._fetch_free_sources(target_roles)
        print(f"[✅ JobScraper] Retrieved {len(free_jobs)} jobs from Free Tech Job Boards.")
        all_jobs.extend(free_jobs)

        # 3. Deduplicate across sources before scoring
        unique_jobs = self._deduplicate_raw(all_jobs)
        print(f"[📊 JobScraper] Total unique aggregated listings: {len(unique_jobs)}")
        return unique_jobs

    def _fetch_apify_jobs(self, target_roles: List[str], locations: List[str]) -> List[Dict[str, Any]]:
        """Queries Apify actors across LinkedIn, Indeed, Google Jobs, Naukri, Internshala."""
        jobs: List[Dict[str, Any]] = []
        if not self.apify_token:
            return jobs

        # Search queries focused on candidate roles and locations
        query_terms = [
            "Python Developer Fresher India",
            "AI ML Engineer Entry Level Bengaluru",
            "Full Stack Developer 0-2 years Remote"
        ]

        # Configured Apify Actors
        actors = [
            ("curious_coder~linkedin-post-search-scraper", "LinkedIn (Apify)", {"searchQueries": query_terms[:2], "maxPosts": 15}),
            ("dan.scraper~google-jobs-scraper", "Google Jobs (Apify)", {"queries": query_terms[:2], "maxResults": 20}),
            ("misceres~indeed-scraper", "Indeed (Apify)", {"position": "Software Engineer Fresher", "location": "India", "maxItems": 15})
        ]

        for actor_id, source_name, payload in actors:
            try:
                url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items?token={self.apify_token}&timeout=60"
                resp = self.session.post(url, json=payload, timeout=45)
                if resp.status_code in [200, 201]:
                    items = resp.json()
                    if isinstance(items, list):
                        for item in items:
                            jobs.append(self._normalize_apify_item(item, source=source_name))
            except Exception as e:
                print(f"[⚠️ Apify] Actor {actor_id} notice: {e}")

        return jobs

    def _fetch_free_sources(self, target_roles: List[str]) -> List[Dict[str, Any]]:
        """Fetches fresh listings from open tech job APIs (RemoteOK, Himalayas, Jobicy, Arbeitnow)."""
        jobs: List[Dict[str, Any]] = []

        # Source 1: RemoteOK API
        try:
            url = "https://remoteok.com/api"
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                for item in data[1:30]:  # Skip first legal element
                    title = item.get("position", "")
                    tags = [t.lower() for t in item.get("tags", [])]
                    loc = item.get("location", "Remote")
                    # Check if India eligible or global remote
                    if "india" in loc.lower() or "worldwide" in loc.lower() or not loc or "anywhere" in loc.lower():
                        jobs.append({
                            "company": item.get("company", "Tech Co"),
                            "title": title,
                            "location": loc or "Remote (India Eligible)",
                            "work_mode": "Remote",
                            "posted_date": self._format_epoch(item.get("date")),
                            "salary": item.get("salary") or f"${item.get('salary_min', '')} - ${item.get('salary_max', '')}" if item.get("salary_min") else "N/A",
                            "experience": "Fresher / 0-2 yrs",
                            "job_type": "Full-time",
                            "job_url": item.get("url") or item.get("apply_url") or "",
                            "source": "RemoteOK",
                            "recruiter_name": "N/A",
                            "recruiter_linkedin": "N/A",
                            "company_website": item.get("company_url") or "N/A",
                            "description": item.get("description", "")[:1000]
                        })
        except Exception as e:
            print(f"[⚠️ RemoteOK] {e}")

        # Source 2: Jobicy API (Free remote tech jobs)
        try:
            url = "https://jobicy.com/api/v2/remote-jobs?count=25&geo=india"
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("jobs", []):
                    jobs.append({
                        "company": item.get("companyName", "Tech Co"),
                        "title": item.get("jobTitle", "Software Engineer"),
                        "location": item.get("jobGeo", "India / Remote"),
                        "work_mode": "Remote",
                        "posted_date": item.get("pubDate", "Date not verified")[:10] if item.get("pubDate") else "Date not verified",
                        "salary": f"{item.get('annualSalaryMin', '')} - {item.get('annualSalaryMax', '')} {item.get('salaryCurrency', '')}" if item.get("annualSalaryMin") else "N/A",
                        "experience": item.get("jobLevel", "Fresher / 0-2 yrs"),
                        "job_type": item.get("jobType", ["Full-Time"])[0] if isinstance(item.get("jobType"), list) else "Full-time",
                        "job_url": item.get("url", ""),
                        "source": "Jobicy",
                        "recruiter_name": "N/A",
                        "recruiter_linkedin": "N/A",
                        "company_website": item.get("companySite", "N/A"),
                        "description": item.get("jobExcerpt", "")
                    })
        except Exception as e:
            print(f"[⚠️ Jobicy] {e}")

        # Source 3: Remotive Free API
        try:
            url = "https://remotive.com/api/remote-jobs?limit=50"
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("jobs", []):
                    loc = item.get("candidate_required_location", "Worldwide")
                    if any(kw in loc.lower() for kw in ["worldwide", "anywhere", "india", "apac", "all"]):
                        jobs.append({
                            "company": item.get("company_name", "Tech Co"),
                            "title": item.get("title", ""),
                            "location": loc or "Remote (India Eligible)",
                            "work_mode": "Remote",
                            "posted_date": item.get("publication_date", "Date not verified")[:10] if item.get("publication_date") else "Date not verified",
                            "salary": item.get("salary") or "N/A",
                            "experience": "Fresher / 0-2 yrs",
                            "job_type": item.get("job_type", "Full-time").title(),
                            "job_url": item.get("url", ""),
                            "source": "Remotive",
                            "recruiter_name": "N/A",
                            "recruiter_linkedin": "N/A",
                            "company_website": item.get("company_url") or "N/A",
                            "description": item.get("description", "")[:1000]
                        })
        except Exception as e:
            print(f"[⚠️ Remotive] {e}")

        # Source 4: Arbeitnow Free API
        try:
            url = "https://www.arbeitnow.com/api/job-board-api"
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("data", [])[:30]:
                    if item.get("remote", False):
                        jobs.append({
                            "company": item.get("company_name", "Tech Co"),
                            "title": item.get("title", ""),
                            "location": item.get("location", "Remote"),
                            "work_mode": "Remote",
                            "posted_date": datetime.fromtimestamp(item.get("created_at", time.time())).strftime("%Y-%m-%d"),
                            "salary": "N/A",
                            "experience": "0-2 yrs",
                            "job_type": "Full-time",
                            "job_url": item.get("url", ""),
                            "source": "Arbeitnow",
                            "recruiter_name": "N/A",
                            "recruiter_linkedin": "N/A",
                            "company_website": "N/A",
                            "description": item.get("description", "")[:800]
                        })
        except Exception as e:
            print(f"[⚠️ Arbeitnow] {e}")

        return jobs

    def _normalize_apify_item(self, item: Dict[str, Any], source: str) -> Dict[str, Any]:
        """Maps raw Apify output to standardized job dictionary."""
        return {
            "company": item.get("companyName") or item.get("company") or "Tech Company",
            "title": item.get("title") or item.get("jobTitle") or item.get("position") or "Software Engineer",
            "location": item.get("location") or "Bengaluru / Remote",
            "work_mode": "Remote" if "remote" in str(item.get("location", "")).lower() else "Hybrid / On-site",
            "posted_date": item.get("postedTime") or item.get("postedDate") or datetime.now().strftime("%Y-%m-%d"),
            "salary": item.get("salary") or item.get("salaryText") or "N/A",
            "experience": item.get("experience") or item.get("experienceLevel") or "Fresher / 0-2 yrs",
            "job_type": item.get("employmentType") or item.get("jobType") or "Full-time",
            "job_url": item.get("jobUrl") or item.get("url") or item.get("link") or "",
            "source": source,
            "recruiter_name": item.get("recruiterName") or item.get("authorName") or "N/A",
            "recruiter_linkedin": item.get("recruiterProfile") or item.get("authorProfile") or "N/A",
            "company_website": item.get("companyWebsite") or item.get("companyUrl") or "N/A",
            "description": item.get("description") or item.get("text") or ""
        }

    def _format_epoch(self, epoch_time: Any) -> str:
        if not epoch_time:
            return "Date not verified"
        try:
            if isinstance(epoch_time, str):
                return epoch_time[:10]
            return datetime.fromtimestamp(float(epoch_time)).strftime("%Y-%m-%d")
        except Exception:
            return "Date not verified"

    def _deduplicate_raw(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        deduped = []
        for j in jobs:
            key = (j.get("company", "").strip().lower(), j.get("title", "").strip().lower())
            if key not in seen and j.get("title"):
                seen.add(key)
                deduped.append(j)
        return deduped
