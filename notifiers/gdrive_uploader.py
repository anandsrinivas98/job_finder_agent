import os
import shutil
from pathlib import Path
from typing import Optional

class GDriveUploader:
    """Uploads/Syncs daily Excel reports to Google Drive.
    Supports:
    1. Local Google Drive / OneDrive desktop folder sync (Zero API keys needed).
    2. Google Drive API via Service Account JSON.
    """

    def __init__(self, folder_id: str = "", service_account_path: Optional[Path] = None, local_sync_path: str = ""):
        self.folder_id = folder_id.strip() if folder_id else ""
        self.service_account_path = Path(service_account_path) if service_account_path else None
        self.local_sync_path = local_sync_path.strip() if local_sync_path else ""

    def upload_file(self, file_path: Path) -> Optional[str]:
        """Saves file to Drive sync folder or uploads via Google Drive API."""
        # Method 1: Local Google Drive / Cloud Sync Folder (Super fast, 0 API setup)
        if self.local_sync_path:
            dest_dir = Path(self.local_sync_path)
            try:
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_file = dest_dir / file_path.name
                shutil.copy2(str(file_path), str(dest_file))
                print(f"[☁️ Google Drive Sync] Report copied to local Drive folder: {dest_file}")
                return str(dest_file)
            except Exception as e:
                print(f"[⚠️ Drive Sync Warning] Could not copy to local sync folder: {e}")

        # Method 2: Google Drive Cloud API
        if not self.folder_id or not self.service_account_path or not self.service_account_path.exists():
            if not self.local_sync_path:
                print("[ℹ️ GDrive] Drive sync not configured (Set GDRIVE_LOCAL_PATH or GDRIVE_FOLDER_ID in .env).")
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
            print(f"[☁️ Google Drive] Uploaded successfully to Cloud Drive! Link: {link}")
            return link

        except ImportError:
            print("[⚠️ GDrive] google-api-python-client not installed. (Run: pip install google-api-python-client)")
            return None
        except Exception as e:
            print(f"[❌ GDrive Upload Error] {e}")
            return None
