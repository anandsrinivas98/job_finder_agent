# 🚀 Automated Daily AI Job Hunting Agent

An autonomous, self-hosted AI Recruiter and Job Hunter that scans multiple job boards (via **Apify** & free open APIs), matches and ranks openings (0–100%) against your **Resume**, builds a professional **6-sheet Excel report**, and sends daily digests directly to **WhatsApp, Email, or Google Drive**.

---

## ⚡ Quick Start in 3 Steps

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env` and fill in your settings:
```bash
cp .env.example .env
```
- Place your resume in `resume/` (`.pdf`, `.docx`, or edit `sample_resume.md`).
- (Optional) Add your free Apify token.
- (Optional) Enable WhatsApp alerts via CallMeBot (100% free) or Gmail SMTP for email attachments.

### 3. Run Pipeline
```bash
# Test run (generates Excel report without sending alerts)
python main.py --dry-run

# Run full pipeline with notifications
python main.py --run-now
```

---

## 📊 Excel Output Structure (`reports/Daily_Job_Hunt_YYYY-MM-DD.xlsx`)

The generated Excel workbook contains 6 specialized sheets:
- **Sheet 1: DAILY JOBS** — All filtered 20–30 matching jobs with clickable links, filters, and status badges (`🆕 NEW`, `🔄 UPDATED`, `⏳ STILL OPEN`).
- **Sheet 2: TOP MATCHES** — Top 5–10 urgent high-match roles.
- **Sheet 3: REMOTE** — India-eligible remote opportunities.
- **Sheet 4: AI & GENAI** — AI, ML, GenAI, LLM, RAG, and NLP roles.
- **Sheet 5: INTERNSHIPS** — Internships and Intern-to-FTE positions.
- **Sheet 6: TESTING & ANALYST** — QA, Automation, Data Analyst, and Business Analyst roles.

---

## ⏰ Daily Automation Options

### 1. Free Cloud Automation (GitHub Actions — 24/7 Zero Cost)
- Push to a private GitHub repo.
- Configure secrets under GitHub repo settings.
- The `.github/workflows/daily_job_hunt.yml` action runs every morning at 08:00 AM IST automatically.

### 2. Local Windows Task Scheduler
Run the PowerShell script once as Administrator:
```powershell
powershell -ExecutionPolicy Bypass -File .\setup_windows_task.ps1
```

---

## 📖 Complete Documentation
For detailed architecture, scoring rules, and integration guides, see **[WORKFLOW.md](WORKFLOW.md)**.
