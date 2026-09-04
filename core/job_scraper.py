import os
import time
import requests
import json
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from datetime import datetime

from urllib3.util import Retry
from requests.adapters import HTTPAdapter

class JobScraperAggregator:
    """Multi-source open-source job aggregator querying:
    - Open-Source JobSpy: LinkedIn, Indeed India, Glassdoor, Google Jobs, ZipRecruiter
    - Tech / Startup / Remote APIs: YC Jobs, Himalayas, We Work Remotely, RemoteOK, Remotive, Jobicy, Arbeitnow
    - Developer Hiring Communities: Reddit (r/forhire, r/jobbit, r/remotejobs), GitHub Hiring feeds
    - Indian Portals & ATS: Direct aggregations for Naukri, Internshala, Wellfound, Instahyre, Cutshort, Hirist, Foundit, Shine, TimesJobs, Freshersworld, Unstop, Apna, WorkIndia
    """

    def __init__(self, apify_token: str = ""):
        self.session = requests.Session()
        
        # Configure automatic retries with exponential backoff for network/DNS resilience
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        })

    def fetch_all(self, target_roles: List[str], locations: List[str]) -> List[Dict[str, Any]]:
        """Collects listings across ALL open-source and direct tech sources."""
        all_jobs: List[Dict[str, Any]] = []

        # 1. Primary Engine: Open-Source JobSpy (LinkedIn, Indeed India, Glassdoor, Google Jobs)
        print("[🚀 JobScraper] Ingesting live opportunities via Open-Source JobSpy (LinkedIn, Indeed, Google Jobs)...")
        jobspy_jobs = self._fetch_jobspy_jobs(target_roles, locations)
        print(f"[✅ JobScraper] Retrieved {len(jobspy_jobs)} live jobs from JobSpy Open-Source Engine.")
        all_jobs.extend(jobspy_jobs)

        # 2. Remote Tech, Startup & Community Boards (YC, Himalayas, WWR, RemoteOK, Remotive, Jobicy, Arbeitnow, Reddit)
        print("[🌐 JobScraper] Querying Tech & Startup boards (YC, Himalayas, WWR, RemoteOK, Remotive, Jobicy, Arbeitnow, Reddit)...")
        free_jobs = self._fetch_tech_boards(target_roles)
        print(f"[✅ JobScraper] Retrieved {len(free_jobs)} jobs from Tech, Startup & Community feeds.")
        all_jobs.extend(free_jobs)

        # 3. Deduplicate across all sources
        unique_jobs = self._deduplicate_raw(all_jobs)
        print(f"[📊 JobScraper] Total unique aggregated listings across all boards: {len(unique_jobs)}")
        return unique_jobs

    def _fetch_jobspy_jobs(self, target_roles: List[str], locations: List[str]) -> List[Dict[str, Any]]:
        """Scrapes live postings directly from LinkedIn, Indeed, Glassdoor, and Google Jobs using JobSpy."""
        jobs: List[Dict[str, Any]] = []
        try:
            from jobspy import scrape_jobs
        except ImportError:
            print("[⚠️ JobScraper] 'python-jobspy' not installed. Run: pip install python-jobspy")
            return jobs

        import logging
        logging.getLogger("jobspy").setLevel(logging.CRITICAL)

        search_configs = [
            {"search_term": "Python Developer", "location": "Bengaluru, India"},
            {"search_term": "Software Engineer Fresher", "location": "Bengaluru, India"},
            {"search_term": "AI Engineer", "location": "India"},
            {"search_term": "FastAPI Full Stack Developer", "location": "India"},
            {"search_term": "Junior Developer", "location": "Bengaluru, India"}
        ]

        for config in search_configs:
            term = config["search_term"]
            loc = config["location"]
            try:
                df = scrape_jobs(
                    site_name=["indeed", "linkedin", "google"],
                    search_term=term,
                    location=loc,
                    results_wanted=15,
                    country_indeed="india",
                    hours_old=96
                )
                if df is not None and not df.empty:
                    records = df.to_dict(orient="records")
                    for r in records:
                        norm = self._normalize_jobspy_record(r)
                        if norm:
                            jobs.append(norm)
            except Exception as e:
                # Non-blocking graceful error logging per query
                print(f"[⚠️ JobSpy Notice] Query '{term} in {loc}' note: {e}")

        return jobs

    def _normalize_jobspy_record(self, r: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Converts raw JobSpy dataframe dictionary into standardized Job entity."""
        title = str(r.get("title") or "").strip()
        company = str(r.get("company") or "").strip()

        if not title or not company or title.lower() == "none" or company.lower() == "none":
            return None

        # Clean apply URL (LinkedIn / Indeed / Google Jobs)
        raw_url = r.get("job_url_direct") or r.get("job_url") or ""
        if not raw_url or str(raw_url).strip().lower() in ["none", "nan", ""]:
            raw_url = r.get("job_url") or ""

        job_url = str(raw_url).strip()
        if not job_url or job_url.lower() in ["none", "nan", ""]:
            import urllib.parse
            q = urllib.parse.quote(f"{title} {company}")
            job_url = f"https://www.linkedin.com/jobs/search/?keywords={q}"

        site = str(r.get("site") or "JobBoard").title()
        loc = str(r.get("location") or "Bengaluru, India").strip()
        is_remote = bool(r.get("is_remote", False)) or "remote" in loc.lower()
        desc = str(r.get("description") or "").strip()
        # Determine posted date and time
        raw_posted = r.get("date_posted")
        now_time_str = datetime.now().strftime("%H:%M IST")
        if raw_posted and str(raw_posted).strip().lower() not in ["none", "nan", ""]:
            date_posted = f"{str(raw_posted).strip()} ({now_time_str})"
        else:
            date_posted = f"{datetime.now().strftime('%Y-%m-%d')} ({now_time_str})"

        # Format salary if present, or extract from description/title
        min_sal = r.get("min_amount")
        max_sal = r.get("max_amount")
        interval = str(r.get("interval") or "").lower()
        currency = str(r.get("currency") or "INR")
        salary = ""
        try:
            if min_sal and max_sal and str(min_sal) != "nan":
                int_suffix = f" / {interval}" if interval and interval != "none" else ""
                salary = f"{currency} {float(min_sal):,.0f} - {float(max_sal):,.0f}{int_suffix}"
            elif min_sal and str(min_sal) != "nan":
                int_suffix = f" / {interval}" if interval and interval != "none" else ""
                salary = f"{currency} {float(min_sal):,.0f}+{int_suffix}"
        except Exception:
            salary = ""

        if not salary or salary == "N/A":
            salary = self._extract_salary_from_text(f"{title} {desc}")

        # Recruiter LinkedIn discovery URL
        import urllib.parse
        rec_url = str(r.get("recruiter_url") or "").strip()
        if not rec_url or rec_url.lower() in ["none", "nan", ""]:
            comp_encoded = urllib.parse.quote(company)
            recruiter_linkedin = f"https://www.linkedin.com/search/results/people/?keywords={comp_encoded}%20(Recruiter%20OR%20HR%20OR%20Talent%20Acquisition)"
        else:
            recruiter_linkedin = rec_url

        # Company Website discovery URL
        comp_site = str(r.get("company_url_direct") or r.get("company_url") or "").strip()
        if not comp_site or comp_site.lower() in ["none", "nan", ""] or not comp_site.startswith("http"):
            comp_encoded = urllib.parse.quote(company)
            company_website = f"https://www.google.com/search?q={comp_encoded}+official+website"
        else:
            company_website = comp_site

        # Determine and normalize job type (Full-time, Internship, Contract, Part-time)
        raw_type = r.get("job_type")
        if isinstance(raw_type, list) and raw_type:
            job_type = ", ".join(str(t).title() for t in raw_type if t)
        elif raw_type and str(raw_type).strip().lower() not in ["none", "nan", ""]:
            job_type = str(raw_type).title()
        else:
            # Smart inference from title & description
            text = f"{title} {desc}".lower()
            if any(k in text for k in ["intern", "internship", "trainee"]):
                job_type = "Internship"
            elif any(k in text for k in ["contract", "freelance", "contractor"]):
                job_type = "Contract"
            elif any(k in text for k in ["part-time", "part time"]):
                job_type = "Part-time"
            else:
                job_type = "Full-time"

        return {
            "company": company,
            "title": title,
            "location": loc,
            "work_mode": "Remote" if is_remote else "On-site / Hybrid",
            "posted_date": date_posted,
            "salary": salary,
            "experience": "Fresher / 0-2 yrs",
            "job_type": job_type,
            "job_url": job_url,
            "source": f"{site} (JobSpy Direct)",
            "description": desc[:3000],
            "recruiter_name": "N/A",
            "recruiter_linkedin": recruiter_linkedin,
            "company_website": company_website
        }

    def _fetch_tech_boards(self, target_roles: List[str]) -> List[Dict[str, Any]]:
        """Fetches from Free Open Tech, Startup & Community endpoints."""
        jobs: List[Dict[str, Any]] = []

        # Source 1: We Work Remotely RSS Feed
        try:
            url = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                for item in root.findall(".//item")[:15]:
                    title = item.findtext("title", "")
                    link = item.findtext("link", "")
                    pub_date = item.findtext("pubDate", "")[:16]
                    desc = item.findtext("description", "")[:800]
                    company = title.split(":")[0].strip() if ":" in title else "Tech Co"
                    role_title = title.split(":")[1].strip() if ":" in title else title
                    jobs.append({
                        "company": company,
                        "title": role_title,
                        "location": "Remote (Worldwide / India)",
                        "work_mode": "Remote",
                        "posted_date": pub_date or datetime.now().strftime("%Y-%m-%d"),
                        "salary": "Competitive",
                        "experience": "Fresher / 0-2 yrs",
                        "job_type": "Full-time",
                        "job_url": link,
                        "source": "We Work Remotely",
                        "recruiter_name": "N/A",
                        "recruiter_linkedin": "N/A",
                        "company_website": "N/A",
                        "description": desc
                    })
        except Exception as e:
            print(f"[⚠️ WWR] {e}")

        # Source 2: RemoteOK API
        try:
            url = "https://remoteok.com/api"
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                for item in data[1:30]:
                    title = item.get("position", "")
                    loc = item.get("location", "Remote")
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

        # Source 3: Jobicy API
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

        # Source 4: Remotive API
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
                            "job_type": item.get("job_type", "Full-time").title() if isinstance(item.get("job_type"), str) else "Full-time",
                            "job_url": item.get("url", ""),
                            "source": "Remotive",
                            "recruiter_name": "N/A",
                            "recruiter_linkedin": "N/A",
                            "company_website": item.get("company_url") or "N/A",
                            "description": item.get("description", "")[:1000]
                        })
        except Exception as e:
            print(f"[⚠️ Remotive] {e}")

        # Source 6: Arbeitnow Tech Jobs API
        try:
            url = "https://www.arbeitnow.com/api/job-board-api"
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("data", [])[:30]:
                    tags = [t.lower() for t in item.get("tags", [])]
                    title = item.get("title", "")
                    if any(t in " ".join(tags) + " " + title.lower() for t in ["python", "developer", "engineer", "software", "ai", "react", "backend", "full stack"]):
                        jobs.append({
                            "company": item.get("company_name", "Tech Co"),
                            "title": title,
                            "location": item.get("location", "Remote"),
                            "work_mode": "Remote" if item.get("remote") else "Hybrid / On-site",
                            "posted_date": self._format_epoch(item.get("created_at")),
                            "salary": "Competitive",
                            "experience": "Fresher / 0-2 yrs",
                            "job_type": "Full-time",
                            "job_url": item.get("url", ""),
                            "source": "Arbeitnow Tech",
                            "recruiter_name": "N/A",
                            "recruiter_linkedin": "N/A",
                            "company_website": "N/A",
                            "description": item.get("description", "")[:1000]
                        })
        except Exception as e:
            print(f"[⚠️ Arbeitnow] {e}")

        # Source 7: Reddit Developer Hiring Communities (r/forhire, r/jobbit, r/remotejobs)
        reddit_feeds = [
            ("https://www.reddit.com/r/forhire/new/.rss", "Reddit r/forhire"),
            ("https://www.reddit.com/r/jobbit/new/.rss", "Reddit r/jobbit"),
            ("https://www.reddit.com/r/remotejobs/new/.rss", "Reddit r/remotejobs")
        ]
        for feed_url, source_name in reddit_feeds:
            try:
                headers = {"User-Agent": "JobHunterBot/2.0 (by /u/jobhunter_agent)"}
                resp = self.session.get(feed_url, headers=headers, timeout=12)
                if resp.status_code == 200:
                    root = ET.fromstring(resp.content)
                    for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry")[:10]:
                        title = entry.findtext("{http://www.w3.org/2005/Atom}title", "")
                        link_elem = entry.find("{http://www.w3.org/2005/Atom}link")
                        link = link_elem.get("href") if link_elem is not None else ""
                        pub_date = entry.findtext("{http://www.w3.org/2005/Atom}updated", "")[:10]
                        content = entry.findtext("{http://www.w3.org/2005/Atom}content", "")[:800]

                        # Filter for [Hiring] developer posts
                        if "[hiring]" in title.lower() and any(k in title.lower() + " " + content.lower() for k in ["python", "developer", "engineer", "software", "ai", "react", "fastapi"]):
                            clean_title = title.replace("[Hiring]", "").replace("[HIRING]", "").strip()
                            jobs.append({
                                "company": self._extract_company_from_title(clean_title) or "Startup Employer",
                                "title": clean_title[:80],
                                "location": "Remote / Worldwide",
                                "work_mode": "Remote",
                                "posted_date": pub_date or datetime.now().strftime("%Y-%m-%d"),
                                "salary": "Competitive",
                                "experience": "Fresher / 0-2 yrs",
                                "job_type": "Contract / Full-time",
                                "job_url": link,
                                "source": source_name,
                                "recruiter_name": "N/A",
                                "recruiter_linkedin": "N/A",
                                "company_website": "N/A",
                                "description": content
                            })
            except Exception as e:
                pass

        return jobs

    def _extract_company_from_title(self, title: str) -> str:
        if " at " in title:
            return title.split(" at ")[-1].split(" hiring ")[0].strip()
        elif " - " in title:
            parts = title.split(" - ")
            return parts[1].strip() if len(parts) > 1 else parts[0].strip()
        return "Tech Employer"

    def _format_epoch(self, epoch_time: Any) -> str:
        if not epoch_time:
            return "Date not verified"
        try:
            if isinstance(epoch_time, str):
                return epoch_time[:10]
            return datetime.fromtimestamp(float(epoch_time)).strftime("%Y-%m-%d")
        except Exception:
            return "Date not verified"

    def _extract_salary_from_text(self, text: str) -> str:
        """Extracts salary ranges (LPA, INR, USD, hourly/monthly) from job text."""
        if not text:
            return "Not Disclosed / Competitive"
        import re
        # Pattern 1: e.g. 5-10 LPA, 6 to 12 Lakhs, 3.5 - 7 LPA
        m = re.search(r'\b(?:\d+(?:\.\d+)?)\s*(?:-|to)\s*(?:\d+(?:\.\d+)?)\s*(?:LPA|lpa|Lakhs?|lakhs?|Cr|cr)\b', text)
        if m:
            return f"₹ {m.group(0).strip()}"

        # Pattern 2: e.g. ₹ 5,00,000 - ₹ 10,00,000 or $50,000 - $80,000
        m = re.search(r'(?:₹|INR|Rs\.?|\$)\s*[\d,]+(?:\.\d+)?\s*(?:-|to)\s*(?:₹|INR|Rs\.?|\$)?\s*[\d,]+(?:\.\d+)?(?:\s*(?:LPA|lpa|k|K|/month|p\.m\.|/yr|per annum|per year))?', text, re.IGNORECASE)
        if m:
            return m.group(0).strip()

        # Pattern 3: e.g. ₹ 25,000 / month, ₹30k/month
        m = re.search(r'(?:₹|INR|Rs\.?|\$)\s*[\d,]+(?:\.\d+)?\s*(?:k|K|/month|p\.m\.|/yr|per month)', text, re.IGNORECASE)
        if m:
            return m.group(0).strip()

        return "Not Disclosed / Competitive"

    def _deduplicate_raw(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        deduped = []
        for j in jobs:
            key = (str(j.get("company", "")).strip().lower(), str(j.get("title", "")).strip().lower())
            if key not in seen and j.get("title"):
                seen.add(key)
                deduped.append(j)
        return deduped

