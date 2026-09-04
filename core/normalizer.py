"""
Canonical Normalization and Freshness Engine for V2 AI Job Hunting Agent.
Transforms raw scraped records into standardized JobRecord entities with verified freshness states.
"""

import re
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from core.models import JobRecord, FreshnessState, PostedDateStatus, VerificationStatus

class JobNormalizer:
    """
    Normalizes:
    - Company names (clean corporate suffixes, casing)
    - Role titles (clean tags, canonical mapping)
    - Locations & Work Mode (Bengaluru, Remote, Hybrid, On-site)
    - Dates & Freshness (FRESH_24H, FRESH_72H, FRESH_7D, OLDER, DATE_UNKNOWN)
    - Skills, Responsibilities, and Requirements extraction
    """

    CORP_SUFFIXES = re.compile(
        r'\b(pvt\.?\s*ltd\.?|private\s+limited|technologies\s+limited|services\s+limited|solutions\s+limited|limited|ltd\.?|llc|inc\.?|technologies|services|solutions|corp\.?|corporation|group|consulting)\b',
        re.IGNORECASE
    )

    ROLE_CATEGORIES = [
        ("AI / ML / GenAI", ["ai", "genai", "llm", "rag", "machine learning", "deep learning", "nlp", "computer vision", "artificial intelligence"]),
        ("Testing / QA", ["qa", "testing", "quality assurance", "sdet", "test engineer", "automation tester"]),
        ("Analyst / Entry Level", ["data analyst", "business analyst", "technology analyst", "operations analyst", "junior analyst"]),
        ("Software / Development", ["software engineer", "developer", "backend", "frontend", "full stack", "python", "react", "fastapi", "sde", "programmer"])
    ]

    def __init__(self, search_window_hours: int = 96):
        self.search_window_hours = search_window_hours

    def clean_company_name(self, name: str) -> str:
        if not name:
            return ""
        # Iteratively strip suffixes
        cleaned = name
        for _ in range(3):
            cleaned = self.CORP_SUFFIXES.sub('', cleaned).strip()
        # Clean special chars
        cleaned = re.sub(r'[\(\)\[\]\{\}]', '', cleaned).strip()
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned.title() if cleaned.islower() or cleaned.isupper() else cleaned

    def normalize(self, raw_job: Dict[str, Any]) -> Dict[str, Any]:
        """Performs full canonical normalization on a raw job record."""
        raw_company = str(raw_job.get("company") or "").strip()
        raw_title = str(raw_job.get("title") or "").strip()
        raw_loc = str(raw_job.get("location") or "").strip()
        raw_url = str(raw_job.get("job_url") or raw_job.get("url") or "").strip()
        raw_desc = str(raw_job.get("description") or "").strip()
        raw_date = raw_job.get("posted_date") or raw_job.get("date_posted") or raw_job.get("pubDate") or raw_job.get("created_at")

        # 1. Company Normalization
        cleaned_company = self.clean_company_name(raw_company)
        normalized_company = self.normalize_text(cleaned_company)

        # 2. Title Normalization & Category
        cleaned_title = self.clean_title(raw_title)
        normalized_title = self.normalize_text(cleaned_title)
        category = self.determine_category(cleaned_title, raw_desc)

        # 3. Location & Work Mode Normalization
        norm_location, work_mode, is_remote = self.normalize_location(raw_loc, raw_desc)

        # 4. Freshness & Posting Date Analysis (Strict V2 Freshness != Novelty)
        posted_date, date_status, freshness_state, age_hours = self.compute_freshness(raw_date)

        # 5. Extract Skills, Requirements & Responsibilities
        skills = self.extract_skills(raw_desc, cleaned_title)
        responsibilities = self.extract_responsibilities(raw_desc)
        requirements = self.extract_requirements(raw_desc)

        # 6. Sanitize URLs
        clean_url = self.clean_url(raw_url)

        # 7. Job Type & Experience
        job_type = self.normalize_job_type(raw_job.get("job_type"), cleaned_title, raw_desc)
        experience = str(raw_job.get("experience") or "Fresher / 0-2 yrs").strip()

        # Build normalized job dictionary
        return {
            "job_id": raw_job.get("job_id") or f"{normalized_company}_{normalized_title[:30]}_{hash(clean_url) & 0xffffff}",
            "company": cleaned_company or "Tech Employer",
            "normalized_company": normalized_company or "tech employer",
            "title": cleaned_title or "Software Developer",
            "normalized_title": normalized_title or "software developer",
            "location": norm_location,
            "normalized_location": self.normalize_text(norm_location),
            "work_mode": work_mode,
            "is_remote": is_remote,
            "category": category,
            "posted_date": posted_date,
            "posted_date_status": date_status,
            "posting_age_hours": age_hours,
            "freshness_state": freshness_state,
            "salary": raw_job.get("salary") or "Not Disclosed / Competitive",
            "experience": experience,
            "job_type": job_type,
            "source": raw_job.get("source") or "JobBoard",
            "source_url": raw_job.get("source_url") or clean_url,
            "job_url": clean_url,
            "canonical_url": clean_url,
            "company_website": raw_job.get("company_website") or "Not Verified",
            "recruiter_name": raw_job.get("recruiter_name") or "N/A",
            "recruiter_linkedin": raw_job.get("recruiter_linkedin") or "N/A",
            "description": raw_desc,
            "skills": skills,
            "responsibilities": responsibilities,
            "requirements": requirements
        }


    def clean_title(self, title: str) -> str:
        if not title:
            return ""
        # Remove common job post tags like [HIRING], (Urgent), - Full Time, etc.
        t = re.sub(r'\[.*?\]|\(.*?\)', '', title)
        t = re.sub(r'\s*-\s*(full\s*time|part\s*time|remote|urgent|fresher)\b.*$', '', t, flags=re.IGNORECASE)
        return re.sub(r'\s+', ' ', t).strip()

    def normalize_text(self, text: str) -> str:
        if not text:
            return ""
        s = text.lower().strip()
        s = self.CORP_SUFFIXES.sub('', s)
        s = re.sub(r'[^a-z0-9\s]', ' ', s)
        return re.sub(r'\s+', ' ', s).strip()

    def determine_category(self, title: str, desc: str) -> str:
        combined = f"{title} {desc}".lower()
        for cat_name, keywords in self.ROLE_CATEGORIES:
            if any(k in title.lower() for k in keywords):
                return cat_name
        for cat_name, keywords in self.ROLE_CATEGORIES:
            if any(k in combined for k in keywords):
                return cat_name
        return "Software / Development"

    def normalize_location(self, loc: str, desc: str) -> Tuple[str, str, bool]:
        loc_lower = (loc or "").lower()
        desc_lower = (desc or "").lower()

        is_remote = "remote" in loc_lower or "wfh" in loc_lower or "work from home" in loc_lower
        if not is_remote and any(k in desc_lower[:300] for k in ["100% remote", "fully remote", "remote work"]):
            is_remote = True

        is_hybrid = "hybrid" in loc_lower or "hybrid" in desc_lower[:300]

        if is_remote:
            work_mode = "Remote"
            norm_loc = "Remote (India Eligible)" if ("india" in loc_lower or not loc) else loc.title()
        elif is_hybrid:
            work_mode = "Hybrid"
            norm_loc = self._standardize_city(loc)
        else:
            work_mode = "On-site"
            norm_loc = self._standardize_city(loc)

        return norm_loc, work_mode, is_remote

    def _standardize_city(self, loc: str) -> str:
        if not loc or loc.strip().lower() in ["none", "nan", ""]:
            return "Bengaluru, Karnataka, India"
        l = loc.lower()
        if "bangalore" in l or "bengaluru" in l:
            return "Bengaluru, Karnataka, India"
        if "hyderabad" in l:
            return "Hyderabad, Telangana, India"
        if "pune" in l:
            return "Pune, Maharashtra, India"
        if "chennai" in l:
            return "Chennai, Tamil Nadu, India"
        if "delhi" in l or "noida" in l or "gurgaon" in l or "gurugram" in l:
            return "Delhi NCR, India"
        if "mumbai" in l:
            return "Mumbai, Maharashtra, India"
        return loc.title()

    def compute_freshness(self, raw_date: Any) -> Tuple[str, str, str, Optional[float]]:
        """
        Parses date and returns:
        (formatted_posted_date, PostedDateStatus, FreshnessState, age_hours)
        """
        if not raw_date or str(raw_date).strip().lower() in ["none", "nan", "", "date not verified"]:
            return "Date not verified", PostedDateStatus.NOT_VERIFIED.value, FreshnessState.DATE_UNKNOWN.value, None

        parsed_dt = None
        now = datetime.now()

        # Handle numeric epoch timestamp
        try:
            if isinstance(raw_date, (int, float)) or (isinstance(raw_date, str) and raw_date.replace('.', '', 1).isdigit()):
                parsed_dt = datetime.fromtimestamp(float(raw_date))
        except Exception:
            pass

        # Handle string formats
        if not parsed_dt and isinstance(raw_date, str):
            clean_str = raw_date.strip()
            # Try ISO formats
            for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"]:
                try:
                    parsed_dt = datetime.strptime(clean_str[:19], fmt[:len(clean_str[:19])])
                    break
                except Exception:
                    continue

        if not parsed_dt:
            return "Date not verified", PostedDateStatus.NOT_VERIFIED.value, FreshnessState.DATE_UNKNOWN.value, None

        # Calculate age in hours
        age_hours = max(0.0, (now - parsed_dt).total_seconds() / 3600.0)
        formatted_date = parsed_dt.strftime("%Y-%m-%d")

        if age_hours <= 24.0:
            state = FreshnessState.FRESH_24H.value
        elif age_hours <= 72.0:
            state = FreshnessState.FRESH_72H.value
        elif age_hours <= 168.0:
            state = FreshnessState.FRESH_7D.value
        else:
            state = FreshnessState.OLDER.value

        return formatted_date, PostedDateStatus.VERIFIED.value, state, round(age_hours, 1)

    def extract_skills(self, desc: str, title: str) -> List[str]:
        common_skills = [
            "Python", "FastAPI", "Django", "Flask", "React", "Next.js", "JavaScript",
            "TypeScript", "SQL", "PostgreSQL", "MongoDB", "Redis", "Docker", "Kubernetes",
            "AWS", "GCP", "Git", "GitHub", "CI/CD", "REST API", "GraphQL", "PyTest",
            "Selenium", "Playwright", "LangChain", "LlamaIndex", "RAG", "GenAI", "LLM",
            "Pandas", "NumPy", "Scikit-Learn", "TensorFlow", "PyTorch"
        ]
        text = f"{title} {desc}".lower()
        found = []
        for s in common_skills:
            if re.search(r'\b' + re.escape(s.lower()) + r'\b', text):
                found.append(s)
        return found

    def extract_responsibilities(self, desc: str) -> List[str]:
        if not desc:
            return []
        lines = [line.strip("-•* ").strip() for line in desc.split("\n") if line.strip()]
        resp = [l for l in lines if len(l) > 20 and any(w in l.lower() for w in ["develop", "build", "maintain", "design", "collaborate", "test", "deploy", "implement"])]
        return resp[:5]

    def extract_requirements(self, desc: str) -> List[str]:
        if not desc:
            return []
        lines = [line.strip("-•* ").strip() for line in desc.split("\n") if line.strip()]
        reqs = [l for l in lines if len(l) > 15 and any(w in l.lower() for w in ["experience", "bachelor", "degree", "proficiency", "knowledge of", "hands-on", "understanding"])]
        return reqs[:5]

    def normalize_job_type(self, raw_type: Any, title: str, desc: str) -> str:
        if raw_type and isinstance(raw_type, str) and raw_type.lower() not in ["none", "nan", ""]:
            return raw_type.title()
        combined = f"{title} {desc}".lower()
        if any(k in combined for k in ["intern", "internship", "trainee"]):
            return "Internship"
        if any(k in combined for k in ["contract", "freelance", "contractor"]):
            return "Contract"
        if any(k in combined for k in ["part-time", "part time"]):
            return "Part-time"
        return "Full-time"

    def clean_url(self, url: str) -> str:
        if not url:
            return ""
        parsed = urllib.parse.urlparse(url)
        # Strip tracking queries
        query = urllib.parse.parse_qs(parsed.query)
        clean_query = {k: v for k, v in query.items() if not k.lower().startswith(("utm_", "ref", "trk", "session", "fbclid"))}
        encoded_query = urllib.parse.urlencode(clean_query, doseq=True)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), parsed.params, encoded_query, ""))
