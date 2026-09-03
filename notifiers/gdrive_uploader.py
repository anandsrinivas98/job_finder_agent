import os
import shutil
from pathlib import Path
from typing import Optional

class GDriveUploader:
    """Uploads/Syncs daily Excel reports to Google Drive.
    Supports:
    1. Local Google Drive / OneDrive desktop folder sync (Zero API keys needed, 100% reliable).
    2. Google Drive OAuth2 User Credentials (for personal @gmail.com accounts).
    3. Google Drive Service Account (for Google Workspace / Shared Drives).
    """

    def __init__(self, folder_id: str = "", service_account_path: Optional[Path] = None, local_sync_path: str = ""):
        raw_id = folder_id.strip() if folder_id else ""
        if "folders/" in raw_id:
            raw_id = raw_id.split("folders/")[-1].split("?")[0].split("/")[0]
        self.folder_id = raw_id
        self.service_account_path = Path(service_account_path) if service_account_path else None
        self.local_sync_path = local_sync_path.strip() if local_sync_path else ""

    def upload_file(self, file_path: Path) -> Optional[str]:
        """Saves file to Drive sync folder or uploads via Google Drive API."""
        # Method 1: Local Google Drive / OneDrive Sync Folder (Recommended for Personal PCs)
        if self.local_sync_path:
            dest_dir = Path(self.local_sync_path)
            try:
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_file = dest_dir / file_path.name
                shutil.copy2(str(file_path), str(dest_file))
                print(f"[☁️ Google Drive Sync] Report copied to your Drive sync folder: {dest_file}")
                return str(dest_file)
            except Exception as e:
                print(f"[⚠️ Drive Sync Warning] Could not copy to local sync folder: {e}")

        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
            from google.oauth2 import service_account
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request

            SCOPES = ['https://www.googleapis.com/auth/drive.file']
            creds = None

            oauth_cred_path = Path("config/gdrive_oauth_credentials.json")
            token_path = Path("config/token.json")

            # Try OAuth2 User Flow (No quota restrictions on personal Gmail accounts)
            if token_path.exists():
                creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            elif oauth_cred_path.exists():
                flow = InstalledAppFlow.from_client_secrets_file(str(oauth_cred_path), SCOPES)
                creds = flow.run_local_server(port=0)
                with open(token_path, "w") as token_file:
                    token_file.write(creds.to_json())

            # Fallback to Service Account
            if not creds and self.service_account_path and self.service_account_path.exists():
                creds = service_account.Credentials.from_service_account_file(
                    str(self.service_account_path), scopes=SCOPES
                )

            if not creds:
                print("[⚠️ GDrive] No valid Google Drive credentials or token found in config/.")
                return None

            if hasattr(creds, "expired") and creds.expired and hasattr(creds, "refresh_token") and creds.refresh_token:
                creds.refresh(Request())

            service = build('drive', 'v3', credentials=creds)

            file_metadata = {'name': file_path.name}
            if self.folder_id:
                file_metadata['parents'] = [self.folder_id]

            media = MediaFileUpload(
                str(file_path),
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                resumable=True
            )

            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink',
                supportsAllDrives=True
            ).execute()

            link = file.get('webViewLink')
            print(f"[☁️ Google Drive] Uploaded successfully to Cloud Drive! Link: {link}")
            return link

        except ImportError:
            print("[⚠️ GDrive] Google API packages missing. Run: pip install google-api-python-client google-auth-oauthlib")
            return None
        except Exception as e:
            if "storageQuotaExceeded" in str(e):
                print("\n[⚠️ Google Drive Note] Google blocks Service Accounts from creating files in personal @gmail.com folders.")
                print("💡 Solution: Use GDRIVE_LOCAL_PATH in .env (e.g. your Google Drive/OneDrive Desktop folder) OR create an OAuth Desktop credential.\n")
            else:
                print(f"[❌ GDrive Upload Error] {e}")
            return None
