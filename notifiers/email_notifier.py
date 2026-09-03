import html
import smtplib
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Dict, Any

class EmailNotifier:
    """Sends daily job hunting digest with attached Excel report via SMTP."""

    def __init__(self, smtp_server: str, smtp_port: int, sender: str, password: str, recipient: str, user: str = ""):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender = sender
        self.user = user or sender
        self.password = password
        # Process recipients list
        raw_recipients = recipient or sender
        if isinstance(raw_recipients, str):
            self.recipients = [r.strip() for r in raw_recipients.split(",") if r.strip()]
        else:
            self.recipients = list(raw_recipients)

    def send_report(self, summary_text: str, excel_path: Path, stats: Dict[str, Any]) -> bool:
        if not self.user or not self.password or not self.recipients:
            print("[⚠️ Email Notifier] Email credentials or recipients not configured. Skipping email dispatch.")
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = f"AI Job Hunter <{self.sender}>"
            msg['To'] = ", ".join(self.recipients)
            msg['Subject'] = f"📅 Daily Job Hunt Report — {stats.get('date', 'Today')} ({stats.get('total', 0)} Jobs Found)"

            # HTML Body with safe escaping
            safe_date = html.escape(str(stats.get('date', 'Today')))
            safe_company = html.escape(str(stats.get('best_company', 'N/A')))
            safe_role = html.escape(str(stats.get('best_role', 'N/A')))

            html_content = f"""
            <html>
            <body style="font-family: 'Segoe UI', Arial, sans-serif; color: #1e293b; background-color: #f8fafc; padding: 20px;">
                <div style="max-width: 600px; margin: auto; background: #ffffff; border-radius: 10px; padding: 24px; border: 1px solid #e2e8f0;">
                    <h2 style="color: #2563eb; margin-top: 0;">🚀 Daily AI Job Hunt Summary</h2>
                    <p style="font-size: 14px; color: #64748b;">Here is your curated job hunt report matched against your resume profile.</p>

                    <div style="background: #f1f5f9; border-radius: 8px; padding: 16px; margin: 16px 0;">
                        <table style="width: 100%; font-size: 14px;">
                            <tr><td><strong>📅 Date:</strong></td><td>{safe_date}</td></tr>
                            <tr><td><strong>🆕 New Jobs:</strong></td><td><span style="color: #16a34a; font-weight: bold;">{stats.get('new_count', 0)}</span></td></tr>
                            <tr><td><strong>💻 Software / Dev:</strong></td><td>{stats.get('software_count', 0)}</td></tr>
                            <tr><td><strong>🤖 AI / ML / GenAI:</strong></td><td>{stats.get('ai_count', 0)}</td></tr>
                            <tr><td><strong>🧪 Testing / QA:</strong></td><td>{stats.get('qa_count', 0)}</td></tr>
                            <tr><td><strong>📊 Analyst:</strong></td><td>{stats.get('analyst_count', 0)}</td></tr>
                            <tr><td><strong>🎓 Internships:</strong></td><td>{stats.get('intern_count', 0)}</td></tr>
                            <tr><td><strong>🌐 Remote:</strong></td><td>{stats.get('remote_count', 0)}</td></tr>
                        </table>
                    </div>

                    <div style="background: #eff6ff; border-left: 4px solid #3b82f6; padding: 12px; margin: 16px 0;">
                        <h4 style="margin: 0 0 6px 0; color: #1d4ed8;">🔥 Top Match</h4>
                        <p style="margin: 0; font-size: 14px;"><strong>{safe_company}</strong> — {safe_role} ({stats.get('best_score', 0)}% Match)</p>
                    </div>

                    <p style="font-size: 13px; color: #475569;">📎 <strong>The complete 6-sheet Excel report is attached to this email.</strong> Open it to view direct apply links, recruiter contacts, and status badges.</p>

                    <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 20px 0;">
                    <p style="font-size: 12px; color: #94a3b8; text-align: center;">Automated by your Self-Hosted Daily AI Job Hunting Agent</p>
                </div>
            </body>
            </html>
            """
            msg.attach(MIMEText(html_content, 'html'))

            # Attach Excel File
            if excel_path.exists():
                with open(excel_path, 'rb') as f:
                    part = MIMEApplication(f.read(), Name=excel_path.name)
                    part['Content-Disposition'] = f'attachment; filename="{excel_path.name}"'
                    msg.attach(part)

            # Send Email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.user, self.password)
            server.send_message(msg)
            server.quit()

            print(f"[✉️ Email Notifier] Report successfully sent to {', '.join(self.recipients)}")
            return True

        except Exception as e:
            print(f"[❌ Email Notifier Error] {e}")
            return False
