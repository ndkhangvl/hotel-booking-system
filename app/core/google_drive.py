import os
import pickle
from io import BytesIO
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Đổi thông tin này thành file mới tải về
CREDENTIALS_FILE = 'credentials.json' 
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "ĐIỀN_ID_THƯ_MỤC_CỦA_BẠN_VÀO_ĐÂY")

# Quyền truy cập toàn bộ Drive
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    creds = None
    # File token.pickle sẽ tự động được tạo ra sau lần đăng nhập đầu tiên
    # Để lưu lại phiên đăng nhập, lần sau chạy code không cần mở trình duyệt nữa
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
            
    # Nếu chưa có file token hoặc token hết hạn, yêu cầu đăng nhập
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES)
            # Dòng này sẽ mở tab trình duyệt lên để bạn click cho phép
            creds = flow.run_local_server(port=0)
            
        # Lưu lại thông tin đăng nhập cho các lần chạy sau
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('drive', 'v3', credentials=creds)

# Hàm upload file của bạn gần như giữ nguyên
def upload_file_to_drive(file_bytes: bytes, filename: str, content_type: str) -> str:
    if not GOOGLE_DRIVE_FOLDER_ID:
        raise RuntimeError("GOOGLE_DRIVE_FOLDER_ID is missing")

    service = get_drive_service()

    file_metadata = {
        "name": filename,
        "parents": [GOOGLE_DRIVE_FOLDER_ID] # ID thư mục trên Drive cá nhân
    }

    media = MediaIoBaseUpload(
        BytesIO(file_bytes),
        mimetype=content_type,
        resumable=True # Nên để True cho file lớn
    )

    created_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()

    file_id = created_file["id"]

    # Cấp quyền cho bất kỳ ai có link đều xem được
    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"}
    ).execute()

    return f"https://drive.google.com/uc?id={file_id}"