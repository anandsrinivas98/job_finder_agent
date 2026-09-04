"""
Execution Logging Engine for V2 AI Job Hunting Agent.
Records structured JSON and text logs for each execution cycle under reports/logs/
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict, field

@dataclass
class ExecutionLog:
    run_id: str
    run_start: str
    run_end: str = ""
    duration_seconds: float = 0.0
    sources_attempted: int = 0
    sources_successful: int = 0
    raw_jobs: int = 0
    normalized_jobs: int = 0
    verified_jobs: int = 0
    duplicates: int = 0
    rejected_jobs: int = 0
    qualified_jobs: int = 0
    new_jobs: int = 0
    updated_jobs: int = 0
    still_open_jobs: int = 0
    expired_jobs: int = 0
    removed_jobs: int = 0
    excel_status: str = "PENDING"
    drive_status: str = "SKIPPED"
    email_status: str = "SKIPPED"
    overall_status: str = "PENDING"
    source_breakdown: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class ExecutionLogger:
    """Manages creation, updating, and saving of structured run logs."""

    def __init__(self, log_dir: Optional[Path] = None):
        base_dir = Path(__file__).resolve().parent.parent
        self.log_dir = log_dir or (base_dir / "reports" / "logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def create_log(self) -> ExecutionLog:
        now = datetime.now()
        run_id = f"RUN_{now.strftime('%Y%m%d_%H%M%S')}"
        return ExecutionLog(
            run_id=run_id,
            run_start=now.strftime("%Y-%m-%d %H:%M:%S")
        )

    def save_log(self, log: ExecutionLog) -> Path:
        """Saves both a structured JSON log and a human-readable text summary."""
        now = datetime.now()
        log.run_end = now.strftime("%Y-%m-%d %H:%M:%S")

        # Determine overall status
        if log.errors:
            if log.excel_status == "SUCCESS":
                log.overall_status = "PARTIAL"
            else:
                log.overall_status = "FAILED"
        elif log.excel_status == "SUCCESS":
            log.overall_status = "SUCCESS"
        else:
            log.overall_status = "PARTIAL"

        # Save JSON
        json_file = self.log_dir / f"{log.run_id}.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(log.to_dict(), f, indent=2)

        # Save latest.json pointer
        latest_file = self.log_dir / "latest_run.json"
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(log.to_dict(), f, indent=2)

        print(f"[📋 ExecutionLogger] Structured run log saved to: {json_file}")
        return json_file
