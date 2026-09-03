import os
from pathlib import Path
from typing import Optional

class GDriveUploader:
    """Uploads daily Excel job hunt reports to a specific Google Drive folder."""

    def __init__(self, folder_id: str, service_account_path: Path):
        self.folder_id = folder_id.strip()
        self.service_account_path = Path(service_account_path)

    def upload_file(self, file_path: Path) -> Optional[str]:
        """Uploads file to Google Drive and returns shareable link if successful."""
        if not self.folder_id:
            print("[⚠️ GDrive Uploader] Google Drive Folder ID not configured.")
            return None

        if not self.service_account_path.exists():
            print(f"[⚠️ GDrive Uploader] Service account credentials not found at: {self.service_account_path}")
            return None

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            SCOPES = ['https://www.googleapis.com/auth/drive.file']
            creds = service_account.Credentials.from_service_account_file(
                str(self.service_account_path), scopes=SCOPES
            )
            service = build('drive', 'v3', credentials=creds)

            file_metadata = {
                'name': file_path.name,
                'parents': [self.folder_id]
            }
            media = MediaFileUpload(
                str(file_path),
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                resumable=True
            )

            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()

            link = file.get('webViewLink')
            print(f"[☁️ Google Drive] Uploaded successfully! File Link: {link}")
            return link

        except ImportError:
            print("[⚠️ GDrive Uploader] google-api-python-client not installed. Skipping Drive upload.")
            return None
        except Exception as e:
            print(f"[❌ GDrive Uploader Error] {e}")
            return None
