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
    """Multi-source job aggregator querying:
    - Apify Actors: Indeed, LinkedIn, Naukri, Google Jobs, Internshala, Wellfound
    - Tech / Startup / Remote: YC Jobs, Himalayas, We Work Remotely, RemoteOK, Remotive, Jobicy, GitHub, Arbeitnow
    - Direct discovery: Instahyre, Cutshort, Hirist, Unstop, Apna
    """

    def __init__(self, apify_token: str = ""):
        self.apify_token = apify_token.strip()
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
        """Collects listings across ALL configured sources."""
        all_jobs: List[Dict[str, Any]] = []

        # 1. Primary Engine: Open-Source JobSpy (LinkedIn, Indeed India, Glassdoor, Google Jobs)
        print("[🚀 JobScraper] Ingesting live opportunities via Open-Source JobSpy (LinkedIn, Indeed, Glassdoor, Google Jobs)...")
        jobspy_jobs = self._fetch_jobspy_jobs(target_roles, locations)
        print(f"[✅ JobScraper] Retrieved {len(jobspy_jobs)} live jobs from JobSpy Open-Source Engine.")
        all_jobs.extend(jobspy_jobs)

        # 2. Apify Search Engine (Optional supplemental actor search if token provided)
        if self.apify_token:
            print("[🔍 JobScraper] Apify Token active. Aggregating supplemental listings from Apify...")
            apify_jobs = self._fetch_apify_jobs(target_roles, locations)
            print(f"[✅ JobScraper] Retrieved {len(apify_jobs)} jobs from Apify Actors.")
            all_jobs.extend(apify_jobs)

        # 3. Remote Tech & Startup Boards (RemoteOK, Remotive, Jobicy, Himalayas, WeWorkRemotely, YC, Arbeitnow)
        print("[🌐 JobScraper] Querying Tech & Startup boards (YC, Himalayas, WWR, RemoteOK, Remotive, Jobicy, GitHub)...")
        free_jobs = self._fetch_tech_boards(target_roles)
        print(f"[✅ JobScraper] Retrieved {len(free_jobs)} jobs from Tech & Startup job boards.")
        all_jobs.extend(free_jobs)

        # 4. Deduplicate across all sources
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
        date_posted = str(r.get("date_posted") or "Recently posted").strip()

        # Format salary if present
        min_sal = r.get("min_amount")
        max_sal = r.get("max_amount")
        currency = str(r.get("currency") or "INR")
        salary = "N/A"
        try:
            if min_sal and max_sal and str(min_sal) != "nan":
                salary = f"{currency} {float(min_sal):,.0f} - {float(max_sal):,.0f}"
            elif min_sal and str(min_sal) != "nan":
                salary = f"{currency} {float(min_sal):,.0f}+"
        except Exception:
            salary = "N/A"

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
            "recruiter_linkedin": "N/A",
            "company_website": "N/A"
        }

    def _fetch_apify_jobs(self, target_roles: List[str], locations: List[str]) -> List[Dict[str, Any]]:
        """Queries Apify actors for Indian job boards (Indeed, Google Jobs, LinkedIn, Naukri)."""
        jobs: List[Dict[str, Any]] = []
        if not self.apify_token:
            return jobs

        # Search queries covering candidate's core stack & fresher roles
        queries = [
            ("Python Developer", "Bengaluru"),
            ("Full Stack Developer", "Bengaluru"),
            ("AI Engineer", "India"),
            ("Software Engineer Fresher", "India"),
            ("FastAPI Backend Developer", "Remote"),
            ("React Next.js Developer", "Bengaluru")
        ]

        # 1. Indeed Scraper via Apify
        for role, loc in queries[:4]:
            try:
                url = f"https://api.apify.com/v2/acts/misceres~indeed-scraper/run-sync-get-dataset-items?token={self.apify_token}&timeout=60"
                payload = {
                    "position": role,
                    "country": "IN",
                    "location": loc,
                    "maxItems": 10
                }
                resp = self.session.post(url, json=payload, timeout=50)
                if resp.status_code in [200, 201]:
                    items = resp.json()
                    if isinstance(items, list):
                        for item in items:
                            if not item.get("error"):
                                jobs.append(self._normalize_apify_item(item, source="Indeed (Apify)"))
            except Exception as e:
                print(f"[⚠️ Apify Indeed] Query '{role} ({loc})' notice: {e}")

        # 2. Comprehensive Multi-Board Apify Search Engine
        try:
            url = f"https://api.apify.com/v2/acts/apify~google-search-scraper/run-sync-get-dataset-items?token={self.apify_token}&timeout=60"
            search_queries = "\n".join([
                # Primary Indian Job Boards
                'site:naukri.com/job-listings "Python Developer" "Bengaluru"',
                'site:naukri.com/job-listings "Software Engineer" "Fresher" "Bengaluru"',
                'site:naukri.com/job-listings "AI Engineer" OR "Machine Learning" "India"',
                'site:linkedin.com/jobs "Python Developer" "Bengaluru" "Entry level"',
                'site:internshala.com "Python" OR "AI" "Internship" "Bengaluru"',
                'site:wellfound.com "Software Engineer" "India"',
                'site:instahyre.com/job "Python" OR "Full Stack" "Bengaluru"',
                'site:cutshort.io "Python" OR "Software Engineer" "Bengaluru"',
                'site:hirist.tech "Python Developer" OR "FastAPI"',
                'site:foundit.in/job "Software Developer" "Fresher" "Bengaluru"',
                'site:glassdoor.co.in/job-listing "Python Developer" "Bengaluru"',
                'site:shine.com/jobs "Software Engineer Fresher" "Bangalore"',
                'site:timesjobs.com "Python Developer" "Bangalore"',
                'site:freshersworld.com/jobs "Software Engineer" "Bangalore"',
                'site:unstop.com/jobs "Software" OR "AI" "India"',
                'site:apna.co/job "Software" OR "IT" "Bengaluru"',
                'site:workindia.in/jobs "Software Developer" "Bengaluru"',
                # Tech / Startups / Remote / YC / Portals
                'site:workatastartup.com "Software Engineer" OR "Python"',
                'site:hackerearth.com/challenges "Hiring" OR "Developer"',
                'site:arc.dev "Python Developer" "Remote"',
                'site:turing.com/jobs "Python" OR "Full Stack"',
                'site:greenhouse.io OR site:lever.co "Python Developer" "India"',
                'site:reddit.com/r/forhire OR site:reddit.com/r/jobbit "[Hiring] Python" OR "[Hiring] Developer"'
            ])
            resp = self.session.post(url, json={"queries": search_queries, "maxPagesPerQuery": 1}, timeout=55)
            if resp.status_code in [200, 201]:
                data = resp.json()
                if isinstance(data, list):
                    for page in data:
                        for org in page.get("organicResults", []):
                            title = org.get("title", "")
                            link = org.get("url", "")
                            desc = org.get("description", "")

                            # Classify exact board source
                            source_tag = "Job Board (Apify)"
                            link_lower = link.lower()
                            if "naukri.com" in link_lower:
                                source_tag = "Naukri (Apify)"
                            elif "linkedin.com" in link_lower:
                                source_tag = "LinkedIn (Apify)"
                            elif "internshala.com" in link_lower:
                                source_tag = "Internshala (Apify)"
                            elif "wellfound.com" in link_lower:
                                source_tag = "Wellfound (Apify)"
                            elif "instahyre.com" in link_lower:
                                source_tag = "Instahyre (Apify)"
                            elif "cutshort.io" in link_lower:
                                source_tag = "Cutshort (Apify)"
                            elif "hirist.tech" in link_lower:
                                source_tag = "Hirist (Apify)"
                            elif "foundit.in" in link_lower:
                                source_tag = "Foundit (Apify)"
                            elif "glassdoor" in link_lower:
                                source_tag = "Glassdoor (Apify)"
                            elif "shine.com" in link_lower:
                                source_tag = "Shine (Apify)"
                            elif "timesjobs.com" in link_lower:
                                source_tag = "TimesJobs (Apify)"
                            elif "freshersworld.com" in link_lower:
                                source_tag = "Freshersworld (Apify)"
                            elif "unstop.com" in link_lower:
                                source_tag = "Unstop (Apify)"
                            elif "apna.co" in link_lower:
                                source_tag = "Apna (Apify)"
                            elif "workindia.in" in link_lower:
                                source_tag = "WorkIndia (Apify)"
                            elif "workatastartup.com" in link_lower:
                                source_tag = "YC Jobs (Apify)"
                            elif "hackerearth.com" in link_lower:
                                source_tag = "HackerEarth (Apify)"
                            elif "arc.dev" in link_lower:
                                source_tag = "Arc.dev (Apify)"
                            elif "turing.com" in link_lower:
                                source_tag = "Turing (Apify)"
                            elif "greenhouse.io" in link_lower or "lever.co" in link_lower:
                                source_tag = "Company Career Page (Apify)"
                            elif "reddit.com" in link_lower:
                                source_tag = "Reddit Hiring (Apify)"

                            jobs.append({
                                "company": self._extract_company_from_title(title),
                                "title": title.split(" - ")[0] if " - " in title else title[:50],
                                "location": "Bengaluru / India",
                                "work_mode": "Hybrid / Remote",
                                "posted_date": datetime.now().strftime("%Y-%m-%d"),
                                "salary": "N/A",
                                "experience": "Fresher / 0-2 yrs",
                                "job_type": "Full-time",
                                "job_url": link,
                                "source": source_tag,
                                "recruiter_name": "N/A",
                                "recruiter_linkedin": "N/A",
                                "company_website": "N/A",
                                "description": desc
                            })
        except Exception as e:
            print(f"[⚠️ Apify Web Search] {e}")

        return jobs

    def _fetch_tech_boards(self, target_roles: List[str]) -> List[Dict[str, Any]]:
        """Fetches from Free Tech & Startup endpoints."""
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

    def _normalize_apify_item(self, item: Dict[str, Any], source: str) -> Dict[str, Any]:
        """Maps raw Apify output to standardized job dictionary."""
        company = (
            item.get("companyName") or
            item.get("company") or
            item.get("company_name") or
            "Hiring Employer"
        )
        company = company.strip() if isinstance(company, str) else "Hiring Employer"

        title = (
            item.get("positionName") or
            item.get("title") or
            item.get("jobTitle") or
            item.get("position") or
            "Software Engineer"
        )
        title = title.strip() if isinstance(title, str) else "Software Engineer"

        loc = (
            item.get("formattedLocation") or
            item.get("location") or
            item.get("jobGeo") or
            "Bengaluru, Karnataka, India"
        )
        loc = loc.strip() if isinstance(loc, str) else "Bengaluru, Karnataka, India"

        apply_url = (
            item.get("externalApplyLink") or
            item.get("url") or
            item.get("jobUrl") or
            item.get("link") or
            ""
        )
        apply_url = apply_url.strip() if isinstance(apply_url, str) else ""

        salary = (
            item.get("salary") or
            item.get("salaryText") or
            item.get("formattedSalary") or
            "N/A"
        )
        salary = salary.strip() if isinstance(salary, str) else "N/A"

        posted_date = (
            item.get("postedAt") or
            item.get("postedTime") or
            item.get("postedDate") or
            item.get("pubDate") or
            datetime.now().strftime("%Y-%m-%d")
        )
        if isinstance(posted_date, str) and len(posted_date) > 10:
            posted_date = posted_date[:10]

        job_type_raw = item.get("employmentType") or item.get("jobType") or "Full-time"
        job_type = ", ".join(job_type_raw) if isinstance(job_type_raw, list) else str(job_type_raw)

        return {
            "company": company,
            "title": title,
            "location": loc,
            "work_mode": "Remote" if "remote" in loc.lower() or "wfh" in loc.lower() else "Hybrid / On-site",
            "posted_date": posted_date,
            "salary": salary,
            "experience": item.get("experience") or item.get("experienceLevel") or "Fresher / 0-2 yrs",
            "job_type": job_type,
            "job_url": apply_url,
            "source": source,
            "recruiter_name": item.get("recruiterName") or item.get("authorName") or "N/A",
            "recruiter_linkedin": item.get("recruiterProfile") or item.get("authorProfile") or "N/A",
            "company_website": item.get("companyWebsite") or item.get("companyUrl") or "N/A",
            "description": item.get("description") or item.get("descriptionHTML") or item.get("text") or ""
        }

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

    def _deduplicate_raw(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        deduped = []
        for j in jobs:
            key = (str(j.get("company", "")).strip().lower(), str(j.get("title", "")).strip().lower())
            if key not in seen and j.get("title"):
                seen.add(key)
                deduped.append(j)
        return deduped
