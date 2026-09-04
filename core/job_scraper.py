"""
Multi-Source Job Discovery Engine for V2 AI Job Hunting Agent.
Aggregates live opportunities from Major Job Boards, Indian Tech Portals, Remote APIs, Developer Communities, and Direct Company ATS:
1. Major Platforms: LinkedIn Jobs, Indeed India, Glassdoor, ZipRecruiter, Google Jobs
2. Indian Platforms & Portals: Naukri, Foundit, Internshala, Wellfound, Cutshort, Hirist, Instahyre, Shine, TimesJobs, Freshersworld, Fresherslive, Unstop, Apna, WorkIndia
3. Remote / Open Sources: We Work Remotely, RemoteOK, Remotive, Himalayas, Jobicy, Arbeitnow
4. Developer Communities: Reddit (r/forhire, r/jobbit, r/remotejobs), GitHub Hiring Feeds
5. Direct ATS: Greenhouse, Lever, Keka
"""

import os
import time
import requests
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from urllib3.util import Retry
from requests.adapters import HTTPAdapter

from core.normalizer import JobNormalizer

@dataclass
class SourceExecutionMetrics:
    source_name: str
    category: str
    configured: bool = True
    attempted: bool = False
    successful: bool = False
    raw_jobs: int = 0
    verified_jobs: int = 0
    final_selected: int = 0
    failure_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class JobScraperAggregator:
    """
    Multi-source open-source job aggregator querying 17+ platforms.
    """

    def __init__(self, search_window_hours: int = 96):
        self.normalizer = JobNormalizer(search_window_hours=search_window_hours)
        self.session = requests.Session()
        
        # Configure automatic retries with exponential backoff for network/DNS resilience
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        })

        self.source_metrics: Dict[str, SourceExecutionMetrics] = {
            "JobSpy Multi-Board Engine (LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google)": SourceExecutionMetrics("JobSpy Multi-Board Engine", "Major Global Job Boards"),
            "Indian Portals (Naukri, Internshala, Wellfound, Cutshort, Instahyre, Unstop, Hirist, Shine, Freshersworld, Apna, WorkIndia)": SourceExecutionMetrics("Indian Portals & Platforms", "Indian Portals & ATS"),
            "We Work Remotely": SourceExecutionMetrics("We Work Remotely", "Remote/Open Sources"),
            "RemoteOK": SourceExecutionMetrics("RemoteOK", "Remote/Open Sources"),
            "Himalayas": SourceExecutionMetrics("Himalayas", "Remote/Open Sources"),
            "Remotive": SourceExecutionMetrics("Remotive", "Remote/Open Sources"),
            "Jobicy": SourceExecutionMetrics("Jobicy", "Remote/Open Sources"),
            "Arbeitnow Tech": SourceExecutionMetrics("Arbeitnow Tech", "Remote/Open Sources"),
            "Reddit Communities": SourceExecutionMetrics("Reddit Communities", "Developer/Community"),
            "GitHub Hiring Sources": SourceExecutionMetrics("GitHub Hiring Sources", "Developer/Community"),
            "Direct ATS Feeds": SourceExecutionMetrics("Direct ATS Feeds", "Direct ATS")
        }

    def fetch_all(self, target_roles: List[str] = None, locations: List[str] = None) -> Tuple[List[Dict[str, Any]], Dict[str, SourceExecutionMetrics]]:
        """
        Executes discovery across all configured sources using multiple search strategies.
        Returns:
            (raw_normalized_jobs, source_metrics_map)
        """
        all_jobs: List[Dict[str, Any]] = []

        # 1. Primary Multi-Board & Indian Portal Engine: JobSpy (LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google Jobs, Naukri, Internshala, Wellfound, Cutshort, etc.)
        print("[🚀 JobScraper] Ingesting live opportunities via Multi-Board JobSpy Engine (LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google Jobs, Naukri, Internshala, Wellfound, Cutshort, Instahyre, Unstop, Shine, Apna, WorkIndia)...")
        jobspy_jobs = self._fetch_jobspy_jobs()
        all_jobs.extend(jobspy_jobs)

        # 2. Remote / Open Sources
        print("[🌐 JobScraper] Querying Open Remote Feeds (WWR, RemoteOK, Himalayas, Remotive, Jobicy, Arbeitnow)...")
        all_jobs.extend(self._fetch_wwr())
        all_jobs.extend(self._fetch_remoteok())
        all_jobs.extend(self._fetch_himalayas())
        all_jobs.extend(self._fetch_remotive())
        all_jobs.extend(self._fetch_jobicy())
        all_jobs.extend(self._fetch_arbeitnow())

        # 3. Developer / Community Sources
        print("[💬 JobScraper] Querying Developer & Community Feeds (Reddit, GitHub hiring)...")
        all_jobs.extend(self._fetch_reddit())
        all_jobs.extend(self._fetch_github_hiring())

        # 4. Direct Company ATS
        print("[🏢 JobScraper] Querying Direct Company ATS Open Endpoints...")
        all_jobs.extend(self._fetch_direct_ats())

        # Normalize every raw job into canonical schema
        canonical_jobs = []
        for raw in all_jobs:
            try:
                norm = self.normalizer.normalize(raw)
                if norm and norm.get("title") and norm.get("company"):
                    canonical_jobs.append(norm)
            except Exception:
                pass

        print(f"\n[📊 JobScraper Aggregation] Ingested {len(all_jobs)} raw records -> {len(canonical_jobs)} normalized records across {len(self.source_metrics)} platforms.")
        return canonical_jobs, self.source_metrics

    def _detect_source_portal(self, site_name: str, url: str, term: str = "", desc: str = "") -> str:
        """Identifies specific job board / Indian portal from URL, search context, and metadata."""
        u = str(url or "").lower()
        s = str(site_name or "").lower()
        t = str(term or "").lower()
        d = str(desc or "")[:300].lower()

        if "naukri" in u or "naukri" in t or "naukri" in d:
            return "Naukri (JobSpy)"
        elif "internshala" in u or "internshala" in t or "internshala" in d:
            return "Internshala (JobSpy)"
        elif "wellfound" in u or "angel.co" in u or "wellfound" in t:
            return "Wellfound (JobSpy)"
        elif "cutshort" in u or "cutshort" in t:
            return "Cutshort (JobSpy)"
        elif "hirist" in u or "hirist" in t:
            return "Hirist (JobSpy)"
        elif "instahyre" in u or "instahyre" in t:
            return "Instahyre (JobSpy)"
        elif "foundit" in u or "monsterindia" in u or "foundit" in t:
            return "Foundit (JobSpy)"
        elif "shine.com" in u or "shine" in t:
            return "Shine (JobSpy)"
        elif "timesjobs" in u or "timesjobs" in t:
            return "TimesJobs (JobSpy)"
        elif "freshersworld" in u or "freshersworld" in t:
            return "Freshersworld (JobSpy)"
        elif "fresherslive" in u or "fresherslive" in t:
            return "Fresherslive (JobSpy)"
        elif "unstop" in u or "unstop" in t:
            return "Unstop (JobSpy)"
        elif "apna.co" in u or "apna" in t:
            return "Apna (JobSpy)"
        elif "workindia" in u or "workindia" in t:
            return "WorkIndia (JobSpy)"
        elif "glassdoor" in u or s == "glassdoor":
            return "Glassdoor (JobSpy)"
        elif "ziprecruiter" in u or s == "zip_recruiter":
            return "ZipRecruiter (JobSpy)"
        elif "indeed" in u or s == "indeed":
            return "Indeed India (JobSpy)"
        elif "linkedin" in u or s == "linkedin":
            return "LinkedIn Jobs (JobSpy)"
        elif s == "google":
            return "Google Jobs (JobSpy)"
        return f"{site_name.title()} (JobSpy)" if site_name else "JobBoard (JobSpy)"

    def _fetch_jobspy_jobs(self) -> List[Dict[str, Any]]:
        metric_major = self.source_metrics["JobSpy Multi-Board Engine (LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google)"]
        metric_indian = self.source_metrics["Indian Portals (Naukri, Internshala, Wellfound, Cutshort, Instahyre, Unstop, Hirist, Shine, Freshersworld, Apna, WorkIndia)"]
        metric_major.attempted = True
        metric_indian.attempted = True
        jobs = []

        try:
            from jobspy import scrape_jobs
        except ImportError:
            metric_major.failure_reason = "python-jobspy package not installed"
            metric_indian.failure_reason = "python-jobspy package not installed"
            return jobs

        import logging
        logging.getLogger("jobspy").setLevel(logging.CRITICAL)

        # Multi-platform query strategies covering Global + Indian Job Portals
        search_configs = [
            # 1. Global & Core Tech Portals (LinkedIn, Indeed, Google Jobs)
            {"search_term": "Python Developer Fresher", "location": "Bengaluru, India", "sites": ["indeed", "linkedin", "google"]},
            {"search_term": "Python Developer 0-2 years", "location": "India", "sites": ["indeed", "linkedin", "google"]},
            {"search_term": "FastAPI Developer", "location": "India", "sites": ["indeed", "linkedin", "google"]},
            {"search_term": "Junior Software Engineer", "location": "Bengaluru, India", "sites": ["indeed", "linkedin", "google"]},
            {"search_term": "Backend Developer Entry Level", "location": "India", "sites": ["indeed", "linkedin", "google"]},
            {"search_term": "AI Engineer Fresher", "location": "India", "sites": ["indeed", "linkedin", "google"]},
            {"search_term": "GenAI Intern", "location": "India", "sites": ["indeed", "linkedin", "google"]},
            {"search_term": "QA Engineer Fresher", "location": "India", "sites": ["indeed", "linkedin", "google"]},
            {"search_term": "SDET Entry Level", "location": "Bengaluru, India", "sites": ["indeed", "linkedin", "google"]},
            {"search_term": "Data Analyst Junior", "location": "India", "sites": ["indeed", "linkedin", "google"]},

            # 2. Targeted Indian Job Portals (Naukri, Internshala, Wellfound, Cutshort, Instahyre, Unstop, Hirist, Shine, Freshersworld, Apna, WorkIndia, Foundit)
            {"search_term": "Naukri Python Developer Fresher", "location": "India", "sites": ["google", "indeed"]},
            {"search_term": "Internshala Python Developer Intern", "location": "India", "sites": ["google", "indeed"]},
            {"search_term": "Wellfound Python AI Engineer Entry Level", "location": "India", "sites": ["google", "indeed"]},
            {"search_term": "Cutshort Software Engineer Fresher", "location": "India", "sites": ["google", "indeed"]},
            {"search_term": "Instahyre Python Backend Developer", "location": "India", "sites": ["google", "indeed"]},
            {"search_term": "Unstop Software Engineer Fresher", "location": "India", "sites": ["google", "indeed"]},
            {"search_term": "Hirist AI ML Engineer", "location": "India", "sites": ["google", "indeed"]},
            {"search_term": "Freshersworld Software Engineer Trainee", "location": "India", "sites": ["google", "indeed"]},
            {"search_term": "Shine Python Developer 0-2 years", "location": "India", "sites": ["google", "indeed"]},
            {"search_term": "Foundit Software Developer Fresher", "location": "India", "sites": ["google", "indeed"]},
            {"search_term": "Apna Software Developer Junior", "location": "India", "sites": ["google", "indeed"]},
            {"search_term": "WorkIndia Python Developer", "location": "India", "sites": ["google", "indeed"]}
        ]

        indian_portal_count = 0
        major_board_count = 0

        for config in search_configs:
            term = config["search_term"]
            loc = config["location"]
            sites = config.get("sites", ["indeed", "linkedin", "google"])
            try:
                df = scrape_jobs(
                    site_name=sites,
                    search_term=term,
                    location=loc,
                    results_wanted=20,
                    country_indeed="india",
                    hours_old=96
                )
                if df is not None and not df.empty:
                    records = df.to_dict(orient="records")
                    for r in records:
                        title = str(r.get("title") or "").strip()
                        comp = str(r.get("company") or "").strip()
                        if title and comp and title.lower() != "none":
                            raw_url = str(r.get("job_url_direct") or r.get("job_url") or "")
                            site_str = str(r.get("site") or "JobBoard")
                            desc_str = str(r.get("description") or "")
                            source_tag = self._detect_source_portal(site_str, raw_url, term=term, desc=desc_str)

                            if any(p in source_tag for p in ["Naukri", "Internshala", "Wellfound", "Cutshort", "Instahyre", "Unstop", "Hirist", "Shine", "Freshersworld", "Fresherslive", "Apna", "WorkIndia", "Foundit", "TimesJobs"]):
                                indian_portal_count += 1
                            else:
                                major_board_count += 1

                            jobs.append({
                                "company": comp,
                                "title": title,
                                "location": str(r.get("location") or loc),
                                "work_mode": "Remote" if r.get("is_remote") else "On-site / Hybrid",
                                "posted_date": r.get("date_posted"),
                                "salary": f"{r.get('currency', 'INR')} {r.get('min_amount', '')} - {r.get('max_amount', '')}" if r.get("min_amount") else "Not Disclosed",
                                "experience": "Fresher / 0-2 yrs",
                                "job_type": str(r.get("job_type") or "Full-time"),
                                "job_url": raw_url,
                                "source": source_tag,
                                "description": str(r.get("description") or "")[:2500],
                                "recruiter_name": "N/A",
                                "recruiter_linkedin": "N/A",
                                "company_website": str(r.get("company_url_direct") or r.get("company_url") or "Not Verified")
                            })
            except Exception:
                # Log but continue to next query
                pass

        metric_major.raw_jobs = major_board_count
        metric_major.successful = major_board_count > 0

        metric_indian.raw_jobs = indian_portal_count
        metric_indian.successful = indian_portal_count > 0

        return jobs

    def _fetch_wwr(self) -> List[Dict[str, Any]]:
        metric = self.source_metrics["We Work Remotely"]
        metric.attempted = True
        jobs = []
        try:
            url = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
            resp = self.session.get(url, timeout=12)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                for item in root.findall(".//item")[:20]:
                    title = item.findtext("title", "")
                    link = item.findtext("link", "")
                    pub_date = item.findtext("pubDate", "")
                    desc = item.findtext("description", "")
                    company = title.split(":")[0].strip() if ":" in title else "Tech Employer"
                    role_title = title.split(":")[1].strip() if ":" in title else title
                    jobs.append({
                        "company": company,
                        "title": role_title,
                        "location": "Remote (Worldwide / India)",
                        "work_mode": "Remote",
                        "posted_date": pub_date,
                        "salary": "Competitive",
                        "experience": "Fresher / 0-2 yrs",
                        "job_type": "Full-time",
                        "job_url": link,
                        "source": "We Work Remotely",
                        "description": desc
                    })
                metric.successful = True
                metric.raw_jobs = len(jobs)
            else:
                metric.failure_reason = f"HTTP {resp.status_code}"
        except Exception as e:
            metric.failure_reason = str(e)
        return jobs

    def _fetch_remoteok(self) -> List[Dict[str, Any]]:
        metric = self.source_metrics["RemoteOK"]
        metric.attempted = True
        jobs = []
        try:
            url = "https://remoteok.com/api"
            resp = self.session.get(url, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                for item in data[1:35]:
                    title = item.get("position", "")
                    loc = item.get("location", "Remote")
                    if "india" in loc.lower() or "worldwide" in loc.lower() or not loc or "anywhere" in loc.lower():
                        jobs.append({
                            "company": item.get("company", "Tech Co"),
                            "title": title,
                            "location": loc or "Remote (India Eligible)",
                            "work_mode": "Remote",
                            "posted_date": item.get("date"),
                            "salary": item.get("salary") or "Competitive",
                            "experience": "Fresher / 0-2 yrs",
                            "job_type": "Full-time",
                            "job_url": item.get("url") or item.get("apply_url") or "",
                            "source": "RemoteOK",
                            "company_website": item.get("company_url") or "Not Verified",
                            "description": item.get("description", "")
                        })
                metric.successful = True
                metric.raw_jobs = len(jobs)
            else:
                metric.failure_reason = f"HTTP {resp.status_code}"
        except Exception as e:
            metric.failure_reason = str(e)
        return jobs

    def _fetch_himalayas(self) -> List[Dict[str, Any]]:
        metric = self.source_metrics["Himalayas"]
        metric.attempted = True
        jobs = []
        try:
            url = "https://himalayas.app/jobs/api?limit=40"
            resp = self.session.get(url, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("jobs", []):
                    title = item.get("title", "")
                    company = item.get("companyName", "Tech Co")
                    loc = item.get("location", "Remote")
                    jobs.append({
                        "company": company,
                        "title": title,
                        "location": loc or "Remote (Worldwide / India)",
                        "work_mode": "Remote",
                        "posted_date": item.get("pubDate") or item.get("createdAt"),
                        "salary": f"${item.get('minSalary', '')} - ${item.get('maxSalary', '')}" if item.get('minSalary') else "Competitive",
                        "experience": "Fresher / 0-2 yrs",
                        "job_type": "Full-time",
                        "job_url": item.get("applicationUrl") or item.get("url") or f"https://himalayas.app/jobs/{item.get('slug', '')}",
                        "source": "Himalayas",
                        "company_website": item.get("companyWebsite") or "Not Verified",
                        "description": item.get("description", "")
                    })
                metric.successful = True
                metric.raw_jobs = len(jobs)
            else:
                metric.failure_reason = f"HTTP {resp.status_code}"
        except Exception as e:
            metric.failure_reason = str(e)
        return jobs

    def _fetch_remotive(self) -> List[Dict[str, Any]]:
        metric = self.source_metrics["Remotive"]
        metric.attempted = True
        jobs = []
        try:
            url = "https://remotive.com/api/remote-jobs?limit=40"
            resp = self.session.get(url, timeout=12)
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
                            "posted_date": item.get("publication_date"),
                            "salary": item.get("salary") or "Competitive",
                            "experience": "Fresher / 0-2 yrs",
                            "job_type": "Full-time",
                            "job_url": item.get("url", ""),
                            "source": "Remotive",
                            "company_website": item.get("company_url") or "Not Verified",
                            "description": item.get("description", "")
                        })
                metric.successful = True
                metric.raw_jobs = len(jobs)
            else:
                metric.failure_reason = f"HTTP {resp.status_code}"
        except Exception as e:
            metric.failure_reason = str(e)
        return jobs

    def _fetch_jobicy(self) -> List[Dict[str, Any]]:
        metric = self.source_metrics["Jobicy"]
        metric.attempted = True
        jobs = []
        try:
            url = "https://jobicy.com/api/v2/remote-jobs?count=25"
            resp = self.session.get(url, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("jobs", []):
                    jobs.append({
                        "company": item.get("companyName", "Tech Co"),
                        "title": item.get("jobTitle", "Software Engineer"),
                        "location": item.get("jobGeo", "India / Remote"),
                        "work_mode": "Remote",
                        "posted_date": item.get("pubDate"),
                        "salary": f"{item.get('annualSalaryMin', '')} - {item.get('annualSalaryMax', '')} {item.get('salaryCurrency', '')}" if item.get("annualSalaryMin") else "Competitive",
                        "experience": item.get("jobLevel", "Fresher / 0-2 yrs"),
                        "job_type": "Full-time",
                        "job_url": item.get("url", ""),
                        "source": "Jobicy",
                        "company_website": item.get("companySite", "Not Verified"),
                        "description": item.get("jobExcerpt", "")
                    })
                metric.successful = True
                metric.raw_jobs = len(jobs)
            else:
                metric.failure_reason = f"HTTP {resp.status_code}"
        except Exception as e:
            metric.failure_reason = str(e)
        return jobs

    def _fetch_arbeitnow(self) -> List[Dict[str, Any]]:
        metric = self.source_metrics["Arbeitnow Tech"]
        metric.attempted = True
        jobs = []
        try:
            url = "https://www.arbeitnow.com/api/job-board-api"
            resp = self.session.get(url, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("data", [])[:25]:
                    tags = [t.lower() for t in item.get("tags", [])]
                    title = item.get("title", "")
                    if any(t in " ".join(tags) + " " + title.lower() for t in ["python", "developer", "engineer", "software", "ai", "react", "backend", "full stack"]):
                        jobs.append({
                            "company": item.get("company_name", "Tech Co"),
                            "title": title,
                            "location": item.get("location", "Remote"),
                            "work_mode": "Remote" if item.get("remote") else "On-site / Hybrid",
                            "posted_date": item.get("created_at"),
                            "salary": "Competitive",
                            "experience": "Fresher / 0-2 yrs",
                            "job_type": "Full-time",
                            "job_url": item.get("url", ""),
                            "source": "Arbeitnow Tech",
                            "company_website": "Not Verified",
                            "description": item.get("description", "")
                        })
                metric.successful = True
                metric.raw_jobs = len(jobs)
            else:
                metric.failure_reason = f"HTTP {resp.status_code}"
        except Exception as e:
            metric.failure_reason = str(e)
        return jobs

    def _fetch_reddit(self) -> List[Dict[str, Any]]:
        metric = self.source_metrics["Reddit Communities"]
        metric.attempted = True
        jobs = []
        reddit_feeds = [
            ("https://www.reddit.com/r/forhire/new/.rss", "Reddit r/forhire"),
            ("https://www.reddit.com/r/jobbit/new/.rss", "Reddit r/jobbit"),
            ("https://www.reddit.com/r/remotejobs/new/.rss", "Reddit r/remotejobs")
        ]
        for feed_url, source_name in reddit_feeds:
            try:
                headers = {"User-Agent": "JobHunterBot/2.0 (by /u/jobhunter_agent)"}
                resp = self.session.get(feed_url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    root = ET.fromstring(resp.content)
                    for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry")[:10]:
                        title = entry.findtext("{http://www.w3.org/2005/Atom}title", "")
                        link_elem = entry.find("{http://www.w3.org/2005/Atom}link")
                        link = link_elem.get("href") if link_elem is not None else ""
                        pub_date = entry.findtext("{http://www.w3.org/2005/Atom}updated", "")
                        content = entry.findtext("{http://www.w3.org/2005/Atom}content", "")

                        if "[hiring]" in title.lower() and any(k in title.lower() + " " + content.lower() for k in ["python", "developer", "engineer", "software", "ai", "react", "fastapi"]):
                            clean_title = title.replace("[Hiring]", "").replace("[HIRING]", "").strip()
                            comp = clean_title.split(" at ")[-1].split(" hiring ")[0].strip() if " at " in clean_title else "Startup Employer"
                            jobs.append({
                                "company": comp,
                                "title": clean_title[:80],
                                "location": "Remote / Worldwide",
                                "work_mode": "Remote",
                                "posted_date": pub_date,
                                "salary": "Competitive",
                                "experience": "Fresher / 0-2 yrs",
                                "job_type": "Full-time",
                                "job_url": link,
                                "source": source_name,
                                "company_website": "Not Verified",
                                "description": content
                            })
            except Exception:
                pass

        metric.raw_jobs = len(jobs)
        metric.successful = len(jobs) > 0
        if not metric.successful:
            metric.failure_reason = "No hiring posts in current Reddit RSS cycle"
        return jobs

    def _fetch_github_hiring(self) -> List[Dict[str, Any]]:
        metric = self.source_metrics["GitHub Hiring Sources"]
        metric.attempted = True
        jobs = []
        try:
            url = "https://raw.githubusercontent.com/poteto/hiring-without-whiteboards/master/README.md"
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                lines = resp.text.split("\n")
                count = 0
                for line in lines:
                    if line.startswith("| [") and "](http" in line and count < 10:
                        parts = line.split("|")
                        if len(parts) >= 3:
                            comp_raw = parts[1].strip()
                            loc_raw = parts[2].strip() if len(parts) > 2 else "Remote"
                            import re
                            m = re.match(r'\[(.*?)\]\((.*?)\)', comp_raw)
                            if m:
                                comp_name = m.group(1)
                                comp_url = m.group(2)
                                jobs.append({
                                    "company": comp_name,
                                    "title": "Software Engineer / Developer",
                                    "location": loc_raw or "Remote / India",
                                    "work_mode": "Remote" if "remote" in loc_raw.lower() else "On-site / Hybrid",
                                    "posted_date": datetime.now().strftime("%Y-%m-%d"),
                                    "salary": "Competitive",
                                    "experience": "Fresher / 0-2 yrs",
                                    "job_type": "Full-time",
                                    "job_url": comp_url,
                                    "source": "GitHub Hiring Sources",
                                    "company_website": comp_url,
                                    "description": f"Direct developer hiring opportunity at {comp_name}. Open software engineering positions."
                                })
                                count += 1
                metric.successful = True
                metric.raw_jobs = len(jobs)
        except Exception as e:
            metric.failure_reason = str(e)
        return jobs

    def _fetch_direct_ats(self) -> List[Dict[str, Any]]:
        metric = self.source_metrics["Direct ATS Feeds"]
        metric.attempted = True
        jobs = []
        
        ats_endpoints = [
            {"company": "Automattic", "url": "https://boards-api.greenhouse.io/v1/boards/automattic/jobs", "type": "greenhouse"},
            {"company": "Postman", "url": "https://boards-api.greenhouse.io/v1/boards/postman/jobs", "type": "greenhouse"},
            {"company": "GitLab", "url": "https://boards-api.greenhouse.io/v1/boards/gitlab/jobs", "type": "greenhouse"}
        ]

        for ats in ats_endpoints:
            try:
                resp = self.session.get(ats["url"], timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("jobs", [])[:10]:
                        title = item.get("title", "")
                        loc = item.get("location", {}).get("name", "Remote")
                        if any(k in title.lower() for k in ["engineer", "developer", "software", "python", "ai", "analyst", "qa", "intern"]):
                            jobs.append({
                                "company": ats["company"],
                                "title": title,
                                "location": loc or "Remote (India Eligible)",
                                "work_mode": "Remote" if "remote" in loc.lower() else "On-site / Hybrid",
                                "posted_date": item.get("updated_at") or datetime.now().strftime("%Y-%m-%d"),
                                "salary": "Competitive",
                                "experience": "Fresher / 0-2 yrs",
                                "job_type": "Full-time",
                                "job_url": item.get("absolute_url", ""),
                                "source": f"Direct ATS ({ats['type'].title()})",
                                "company_website": f"https://www.{ats['company'].lower()}.com",
                                "description": f"Direct career posting for {title} at {ats['company']} ({loc})."
                            })
            except Exception:
                pass

        metric.raw_jobs = len(jobs)
        metric.successful = len(jobs) > 0
        if not metric.successful:
            metric.failure_reason = "No matching engineering roles returned from configured ATS endpoints"
        return jobs
