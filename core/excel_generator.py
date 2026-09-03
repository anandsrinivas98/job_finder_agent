import os
import urllib.parse
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

class ExcelReportGenerator:
    """Generates a professional 6-sheet Excel report with styling, hyperlinks, and filters."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Aesthetics & Palettes
        self.font_family = "Segoe UI"
        self.header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid") # Dark Slate
        self.header_font = Font(name=self.font_family, size=11, bold=True, color="FFFFFF")
        self.regular_font = Font(name=self.font_family, size=10, color="1E293B")
        self.bold_font = Font(name=self.font_family, size=10, bold=True, color="0F172A")
        self.link_font = Font(name=self.font_family, size=10, color="2563EB", underline="single") # Hyperlink blue

        self.border_thin = Border(
            left=Side(style='thin', color='E2E8F0'),
            right=Side(style='thin', color='E2E8F0'),
            top=Side(style='thin', color='E2E8F0'),
            bottom=Side(style='thin', color='E2E8F0')
        )

        self.columns = [
            ("#", 6),
            ("Company", 24),
            ("Role", 30),
            ("Location", 22),
            ("Work Mode", 14),
            ("Posted", 14),
            ("Match %", 12),
            ("Experience", 18),
            ("Salary", 18),
            ("Job Type", 14),
            ("Source", 18),
            ("Apply Link", 18),
            ("Find Referral (LinkedIn)", 24),
            ("Recruiter LinkedIn", 20),
            ("Company Website", 20),
            ("Status", 14)
        ]

    def generate_daily_report(self, jobs: List[Dict[str, Any]], custom_date: str = "") -> Path:
        """Builds and saves the complete 6-sheet Excel report."""
        date_str = custom_date or datetime.now().strftime("%Y-%m-%d")
        filename = f"Daily_Job_Hunt_{date_str}.xlsx"
        file_path = self.output_dir / filename

        wb = openpyxl.Workbook()
        # Remove default sheet
        wb.remove(wb.active)

        # 1. Sheet 1 - DAILY JOBS (All)
        self._populate_sheet(wb, "DAILY JOBS", jobs)

        # 2. Sheet 2 - TOP MATCHES (Top 10)
        top_matches = sorted(jobs, key=lambda x: x.get("match_score", 0), reverse=True)[:10]
        self._populate_sheet(wb, "TOP MATCHES", top_matches)

        # 3. Sheet 3 - REMOTE (Remote Only)
        remote_jobs = [j for j in jobs if j.get("is_remote", False)]
        self._populate_sheet(wb, "REMOTE", remote_jobs)

        # 4. Sheet 4 - AI & GENAI
        ai_jobs = [j for j in jobs if j.get("category") == "AI / ML / GenAI"]
        self._populate_sheet(wb, "AI & GENAI", ai_jobs)

        # 5. Sheet 5 - INTERNSHIPS
        intern_jobs = [j for j in jobs if j.get("is_internship", False)]
        self._populate_sheet(wb, "INTERNSHIPS", intern_jobs)

        # 6. Sheet 6 - TESTING & ANALYST
        qa_analyst_jobs = [j for j in jobs if j.get("category") in ["Testing / QA", "Analyst / Entry Level"]]
        self._populate_sheet(wb, "TESTING & ANALYST", qa_analyst_jobs)

        wb.save(file_path)
        print(f"[📊 Excel Generator] Saved report with 6 sheets to: {file_path}")
        return file_path

    def _sanitize_cell_value(self, val: Any) -> Any:
        """Sanitizes text to prevent Spreadsheet Formula Injection (CWE-1236)."""
        if isinstance(val, str):
            # If string starts with risky formula triggers, prepend a single quote
            if val.startswith(("=", "+", "-", "@", "\t", "\r")):
                return f"'{val}"
        return val

    def _is_safe_url(self, url: str) -> bool:
        """Validates that a URL strictly uses http or https schemes."""
        if not url or not isinstance(url, str):
            return False
        clean = url.strip().lower()
        return clean.startswith("http://") or clean.startswith("https://")

    def _populate_sheet(self, wb: openpyxl.Workbook, title: str, job_list: List[Dict[str, Any]]):
        ws = wb.create_sheet(title=title)
        ws.views.sheetView[0].showGridLines = True

        # Header Row
        header_row = [c[0] for c in self.columns]
        ws.append(header_row)

        for col_idx in range(1, len(self.columns) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = self.header_fill
            cell.font = self.header_font
            cell.alignment = Alignment(horizontal="center" if col_idx in [1, 5, 6, 7, 10, 15] else "left", vertical="center")
            cell.border = self.border_thin

        ws.row_dimensions[1].height = 28

        # Populate Data Rows
        for idx, job in enumerate(job_list, start=1):
            status = job.get("status", "NEW")
            status_badge = f"🆕 {status}" if status == "NEW" else (f"🔄 {status}" if status == "UPDATED" else f"⏳ {status}")
            company_name = job.get("company", "N/A")

            # Dynamic LinkedIn employee search URL for finding alumni & referral connections
            clean_comp_encoded = urllib.parse.quote(company_name.replace("'", "").replace('"', ''))
            referral_url = f"https://www.linkedin.com/search/results/people/?keywords={clean_comp_encoded}%20Software%20Engineer"

            raw_row = [
                idx,
                company_name,
                job.get("title", "N/A"),
                job.get("location", "India"),
                job.get("work_mode", "N/A"),
                job.get("posted_date", "Date not verified"),
                f"{job.get('match_score', 0)}%",
                job.get("experience", "Fresher / 0-2 yrs"),
                job.get("salary", "N/A"),
                job.get("job_type", "Full-time"),
                job.get("source", "N/A"),
                "Apply Here",
                "Find Referral ↗",
                "View Recruiter" if job.get("recruiter_linkedin") not in ["N/A", "", None] else "N/A",
                "Company Site" if job.get("company_website") not in ["N/A", "", None] else "N/A",
                status_badge
            ]
            row_data = [self._sanitize_cell_value(item) for item in raw_row]
            ws.append(row_data)
            row_idx = idx + 1
            ws.row_dimensions[row_idx].height = 22

            # Styling individual cells
            for col_idx in range(1, len(self.columns) + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.font = self.regular_font
                cell.border = self.border_thin
                cell.alignment = Alignment(horizontal="center" if col_idx in [1, 5, 6, 7, 10, 16] else "left", vertical="center")

                # Format Match % with highlight
                if col_idx == 7:
                    score = float(job.get("match_score", 0))
                    cell.font = self.bold_font
                    if score >= 85:
                        cell.fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid") # light green
                    elif score >= 70:
                        cell.fill = PatternFill(start_color="FEF9C3", end_color="FEF9C3", fill_type="solid") # light yellow

                # Apply Link Hyperlink (Col 12)
                if col_idx == 12:
                    url = job.get("job_url", "")
                    if self._is_safe_url(url):
                        cell.value = "Apply Link ↗"
                        cell.hyperlink = url
                        cell.font = self.link_font
                    else:
                        cell.value = "N/A"

                # Find Referral LinkedIn Link (Col 13)
                if col_idx == 13:
                    cell.value = "Ask Referral ↗"
                    cell.hyperlink = referral_url
                    cell.font = self.link_font

                # Recruiter LinkedIn Hyperlink (Col 14)
                if col_idx == 14:
                    rec_url = job.get("recruiter_linkedin", "")
                    if self._is_safe_url(rec_url):
                        cell.value = "Recruiter ↗"
                        cell.hyperlink = rec_url
                        cell.font = self.link_font
                    else:
                        cell.value = "N/A"

                # Company Website Hyperlink (Col 15)
                if col_idx == 15:
                    comp_url = job.get("company_website", "")
                    if self._is_safe_url(comp_url):
                        cell.value = "Website ↗"
                        cell.hyperlink = comp_url
                        cell.font = self.link_font
                    else:
                        cell.value = "N/A"

        # Auto-adjust column widths & add auto-filter
        for col_idx, (name, width) in enumerate(self.columns, start=1):
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = max(width, 12)

        if len(job_list) > 0:
            last_col_letter = get_column_letter(len(self.columns))
            ws.auto_filter.ref = f"A1:{last_col_letter}{len(job_list) + 1}"
            ws.freeze_panes = "A2"
