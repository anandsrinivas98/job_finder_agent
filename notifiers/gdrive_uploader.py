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
            env_token = os.getenv("GDRIVE_TOKEN_JSON", "").strip()

            # 1. Try OAuth2 User Flow from Token File
            if token_path.exists():
                try:
                    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
                except Exception as e:
                    print(f"[⚠️ GDrive] Failed reading config/token.json: {e}")

            # 2. Try OAuth2 User Flow directly from Environment Variable JSON string
            if not creds and env_token:
                try:
                    import json
                    token_dict = json.loads(env_token)
                    creds = Credentials.from_authorized_user_info(token_dict, SCOPES)
                    print("[☁️ GDrive] Loaded Google Drive OAuth2 credentials from GDRIVE_TOKEN_JSON environment variable.")
                except Exception as e:
                    print(f"[⚠️ GDrive] Failed parsing GDRIVE_TOKEN_JSON env var: {e}")

            # 3. Interactive Local OAuth2 Flow
            elif not creds and oauth_cred_path.exists():
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(str(oauth_cred_path), SCOPES)
                    creds = flow.run_local_server(port=0)
                    with open(token_path, "w") as token_file:
                        token_file.write(creds.to_json())
                except Exception as e:
                    print(f"[⚠️ GDrive] OAuth flow notice: {e}")

            # 4. Fallback to Service Account
            if not creds and self.service_account_path and self.service_account_path.exists():
                try:
                    creds = service_account.Credentials.from_service_account_file(
                        str(self.service_account_path), scopes=SCOPES
                    )
                except Exception as e:
                    print(f"[⚠️ GDrive] Service account notice: {e}")

            if not creds:
                print("[⚠️ GDrive] No valid Google Drive credentials or token found. Upload skipped.")
                print("💡 To enable cloud upload in GitHub Actions, add your GDRIVE_TOKEN_JSON secret.")
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

            try:
                file = service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, webViewLink, webContentLink',
                    supportsAllDrives=True
                ).execute()
            except Exception as e:
                # If specific folder upload fails, retry upload to root Drive
                if self.folder_id and "notFound" in str(e) or "access" in str(e).lower():
                    print(f"[⚠️ GDrive] Target folder ID error. Retrying upload to root Drive...")
                    file_metadata.pop('parents', None)
                    file = service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id, webViewLink, webContentLink',
                        supportsAllDrives=True
                    ).execute()
                else:
                    raise e

            file_id = file.get('id')

            # V2 Privacy Rule: Default to PRIVATE (Owner Only). Only grant public read if explicitly configured.
            sharing_mode = os.getenv("DRIVE_SHARING_MODE", "PRIVATE").upper().strip()
            if sharing_mode in ["PUBLIC", "EXPLICITLY_SHARED"]:
                try:
                    service.permissions().create(
                        fileId=file_id,
                        body={'type': 'anyone', 'role': 'reader'},
                        supportsAllDrives=True
                    ).execute()
                    print(f"[☁️ Google Drive] Public sharing enabled (mode: {sharing_mode}).")
                except Exception as e:
                    print(f"[⚠️ Google Drive] Permission update note: {e}")
            else:
                print(f"[🔒 Google Drive] Report saved with PRIVATE / OWNER-ONLY permissions.")

            link = f"https://docs.google.com/spreadsheets/d/{file_id}/edit?usp=sharing"
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
