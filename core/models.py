"""
Core Data Models and Enums for the V2 AI Job Hunting Agent.
Provides canonical data structures for job records, candidate profiles, and verification states.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

class JobStatus(str, Enum):
    NEW = "NEW"
    UPDATED = "UPDATED"
    STILL_OPEN = "STILL OPEN"
    EXPIRED = "EXPIRED"
    REMOVED = "REMOVED"

class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    REJECTED = "REJECTED"

class PostedDateStatus(str, Enum):
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"
    ESTIMATED = "ESTIMATED"

class FreshnessState(str, Enum):
    FRESH_24H = "FRESH_24H"
    FRESH_72H = "FRESH_72H"
    FRESH_7D = "FRESH_7D"
    OLDER = "OLDER"
    DATE_UNKNOWN = "DATE_UNKNOWN"

class DuplicateStatus(str, Enum):
    UNIQUE = "UNIQUE"
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    SEMANTIC_DUPLICATE = "SEMANTIC_DUPLICATE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"

@dataclass
class MatchBreakdown:
    skills: float = 0.0          # Max 35
    responsibilities: float = 0.0 # Max 25
    projects: float = 0.0        # Max 15
    experience: float = 0.0      # Max 10
    education: float = 0.0       # Max 5
    location: float = 0.0        # Max 5
    other: float = 0.0           # Max 5

    def total(self) -> float:
        return round(
            self.skills + self.responsibilities + self.projects + 
            self.experience + self.education + self.location + self.other, 
            1
        )

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)

    def to_summary_str(self) -> str:
        return f"Skills: {self.skills}/35 | Resp: {self.responsibilities}/25 | Proj: {self.projects}/15 | Exp: {self.experience}/10 | Edu: {self.education}/5 | Loc: {self.location}/5"

@dataclass
class JobRecord:
    # 1. Identifiers & Normalized Names
    job_id: str
    company: str
    normalized_company: str
    title: str
    normalized_title: str
    location: str = "India"
    normalized_location: str = "india"
    work_mode: str = "On-site / Hybrid"

    # 2. Freshness & Dates
    posted_date: str = "Date not verified"
    posted_date_status: str = PostedDateStatus.NOT_VERIFIED.value
    posting_age_hours: Optional[float] = None
    freshness_state: str = FreshnessState.DATE_UNKNOWN.value

    # 3. Employment Details
    salary: str = "Not Disclosed / Competitive"
    experience: str = "Fresher / 0-2 yrs"
    job_type: str = "Full-time"

    # 4. URLs & Origin
    source: str = "JobBoard"
    source_url: str = ""
    job_url: str = ""
    canonical_url: str = ""
    official_apply_url: str = ""
    company_website: str = "Not Verified"

    # 5. Content & Semantic Extraction
    description: str = ""
    requirements: List[str] = field(default_factory=list)
    responsibilities: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)

    # 6. Scoring & Classification
    match_score: float = 0.0
    match_breakdown: MatchBreakdown = field(default_factory=MatchBreakdown)
    category: str = "Software / Development"

    # 7. Verification Flags
    verification_status: str = VerificationStatus.UNVERIFIED.value
    company_domain_verified: bool = False
    application_page_verified: bool = False
    posting_active: bool = True
    posting_date_verified: bool = False
    location_verified: bool = True
    experience_verified: bool = True
    india_eligibility_verified: bool = True

    # 8. State Machine & Novelty Tracking
    status: str = JobStatus.NEW.value
    first_seen: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    last_seen: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    first_delivered_as_new: Optional[str] = None
    last_delivered: Optional[str] = None
    run_count: int = 1

    # 9. Change Tracking
    previous_status: Optional[str] = None
    previous_match_score: Optional[float] = None
    last_change_detected: Optional[str] = None

    # 10. Recruiter Info
    recruiter_name: Optional[str] = None
    recruiter_linkedin: Optional[str] = None
    recruiter_verification_status: str = "NOT_FOUND"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if isinstance(self.match_breakdown, MatchBreakdown):
            d["match_breakdown"] = self.match_breakdown.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobRecord":
        mb = data.get("match_breakdown")
        if isinstance(mb, dict):
            data["match_breakdown"] = MatchBreakdown(**mb)
        elif not isinstance(mb, MatchBreakdown):
            data["match_breakdown"] = MatchBreakdown()
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
