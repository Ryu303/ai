import datetime
import json
import asyncio
import uuid
from typing import List, Dict, Any, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy.ext.asyncio import AsyncSession
from app import crud
from app.database import async_session
from app.config import decrypt_token

async def get_google_creds(user_id: uuid.UUID) -> Optional[Credentials]:
    """사용자의 OAuth2 Credentials 정보를 DB에서 로드하여 google.oauth2.credentials.Credentials 객체로 복원합니다."""
    from sqlalchemy import select, and_
    from app.models import UserApiIntegration
    async with async_session() as db:
        try:
            stmt = select(UserApiIntegration).where(
                and_(
                    UserApiIntegration.user_id == user_id,
                    UserApiIntegration.service_name == "google"
                )
            )
            result = await db.execute(stmt)
            integration = result.scalar_one_or_none()
        except Exception:
            integration = None
            
        if not integration:
            from app.crud import _MOCK_INTEGRATIONS
            integration = next((item for item in _MOCK_INTEGRATIONS if item.user_id == user_id and item.service_name == "google"), None)
            
        if not integration:
            return None
        
        try:
            decrypted_str = decrypt_token(integration.encrypted_api_key)
            try:
                cred_dict = json.loads(decrypted_str)
                return Credentials.from_authorized_user_info(cred_dict)
            except json.JSONDecodeError:
                return Credentials(token=decrypted_str)
        except Exception as e:
            print(f"[Google Auth Error] Failed to reconstruct credentials for user {user_id}: {e}")
            return None

# ==========================================
# 1. Google Calendar 연동 비서
# ==========================================

async def get_today_calendar(user_id: uuid.UUID) -> List[Dict[str, Any]]:
    """당일 00:00:00부터 23:59:59 사이의 구글 캘린더 일정을 시간순 조회합니다."""
    creds = await get_google_creds(user_id)
    
    # 캘린더 조회 기준 시간 설정 (로컬 타임존 반영)
    now = datetime.datetime.now()
    start_of_day = datetime.datetime(now.year, now.month, now.day, 0, 0, 0).isoformat() + "Z"
    end_of_day = datetime.datetime(now.year, now.month, now.day, 23, 59, 59).isoformat() + "Z"

    if not creds:
        # Mock 데이터 반환 (실제 연동 증명이 없을 경우의 Fallback)
        print(f"[Google Workspace Fallback] Mocking calendar events for {user_id}")
        return [
            {
                "summary": "ARGOS 백엔드 아키텍처 리뷰 회의",
                "start": (now.replace(hour=11, minute=0, second=0)).strftime("%Y-%m-%dT%H:%M:%S"),
                "end": (now.replace(hour=12, minute=0, second=0)).strftime("%Y-%m-%dT%H:%M:%S")
            },
            {
                "summary": "스마트홈 IoT 연동 테스트 세션",
                "start": (now.replace(hour=15, minute=30, second=0)).strftime("%Y-%m-%dT%H:%M:%S"),
                "end": (now.replace(hour=16, minute=30, second=0)).strftime("%Y-%m-%dT%H:%M:%S")
            }
        ]

    def _fetch_calendar():
        service = build('calendar', 'v3', credentials=creds)
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_of_day,
            timeMax=end_of_day,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        return events_result.get('items', [])

    try:
        events = await asyncio.to_thread(_fetch_calendar)
        formatted_events = []
        for event in events:
            formatted_events.append({
                "summary": event.get("summary", "제목 없음"),
                "start": event.get("start", {}).get("dateTime") or event.get("start", {}).get("date"),
                "end": event.get("end", {}).get("dateTime") or event.get("end", {}).get("date")
            })
        return formatted_events
    except Exception as e:
        print(f"[Google Calendar API Error] {e}")
        return []

async def Calendar(user_id: uuid.UUID, summary: str, start_time: str, end_time: str) -> Dict[str, Any]:
    """일정을 동적 생성합니다. (명세에 기술된 'Calendar' 함수 명칭 및 파라미터 요구사항 준수)"""
    creds = await get_google_creds(user_id)
    
    event_body = {
        'summary': summary,
        'start': {
            'dateTime': start_time, # '2026-06-24T12:00:00+09:00' 포맷 권장
            'timeZone': 'Asia/Seoul',
        },
        'end': {
            'dateTime': end_time,
            'timeZone': 'Asia/Seoul',
        }
    }

    if not creds:
        # Mock 데이터 반환
        print(f"[Google Workspace Fallback] Mocking calendar event creation for {user_id}")
        return {
            "status": "success",
            "message": f"일정 '{summary}'이 성공적으로 예약되었습니다 (Mock).",
            "event": event_body
        }

    def _create_event():
        service = build('calendar', 'v3', credentials=creds)
        return service.events().insert(calendarId='primary', body=event_body).execute()

    try:
        event = await asyncio.to_thread(_create_event)
        return {
            "status": "success",
            "message": f"일정 '{summary}'이 성공적으로 생성되었습니다.",
            "event_id": event.get("id"),
            "link": event.get("htmlLink")
        }
    except Exception as e:
        print(f"[Google Calendar Create Error] {e}")
        return {"status": "error", "message": str(e)}

# ==========================================
# 2. Gmail 연동 비서
# ==========================================

async def get_unread_emails(user_id: uuid.UUID) -> List[Dict[str, Any]]:
    """읽지 않은 Gmail 사서함에서 최신 5개의 메일을 송신자, 제목, 본문 일부와 함께 요약 반환합니다."""
    creds = await get_google_creds(user_id)

    if not creds:
        # Mock 데이터 반환
        print(f"[Google Workspace Fallback] Mocking unread emails for {user_id}")
        return [
            {
                "sender": "argos-alerts@argos.security",
                "subject": "[경고] 스마트 플러그 전력 2100W 초과 감지",
                "snippet": "귀하의 스마트 홈 내 거실 난방 기기의 소비 전력이 2000W 제한 수치를 초과하였습니다. 즉시 제어가 필요합니다."
            },
            {
                "sender": "github-updates@github.com",
                "subject": "[GitHub] argos-backend repository pull request #12",
                "snippet": "User dev-john proposed a pull request to optimize DTW similarity calculation speed. Please review."
            },
            {
                "sender": "newsletter@techcrunch.com",
                "subject": "Daily Tech Digest: Generative AI on the Edge",
                "snippet": "Here is today's summary of trending tech topics. Edge devices are performing local speech stress analysis."
            }
        ]

    def _fetch_emails():
        service = build('gmail', 'v1', credentials=creds)
        # 읽지 않은 메시지 5개 쿼리
        results = service.users().messages().list(userId='me', q='is:unread', maxResults=5).execute()
        messages = results.get('messages', [])
        
        email_list = []
        for msg in messages:
            msg_detail = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
            
            headers = msg_detail.get('payload', {}).get('headers', [])
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), "알 수 없음")
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "제목 없음")
            snippet = msg_detail.get('snippet', "")
            
            email_list.append({
                "sender": sender,
                "subject": subject,
                "snippet": snippet
            })
        return email_list

    try:
        emails = await asyncio.to_thread(_fetch_emails)
        return emails
    except Exception as e:
        print(f"[Google Gmail API Error] {e}")
        return []

# ==========================================
# 3. Google Sheets 연동
# ==========================================

async def append_sheet_data(user_id: uuid.UUID, spreadsheet_id: str, row_data: List[Any]) -> Dict[str, Any]:
    """지정된 구글 스프레드시트 최하단 빈 행에 전달받은 데이터를 누적 기록합니다."""
    creds = await get_google_creds(user_id)

    if not creds:
        # Mock 데이터 반환
        print(f"[Google Workspace Fallback] Mocking spreadsheet append for {user_id}")
        return {
            "status": "success",
            "message": f"스프레드시트({spreadsheet_id}) 최하단 빈 행에 데이터 {row_data}가 추가되었습니다 (Mock)."
        }

    def _append():
        service = build('sheets', 'v4', credentials=creds)
        body = {
            'values': [row_data]
        }
        # A1 범위를 기준으로 append하면 알아서 데이터가 누적됩니다.
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range="Sheet1!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body
        ).execute()
        return result

    try:
        res = await asyncio.to_thread(_append)
        return {
            "status": "success",
            "message": "데이터가 구글 스프레드시트에 성공적으로 기록되었습니다.",
            "updated_range": res.get("updates", {}).get("updatedRange")
        }
    except Exception as e:
        print(f"[Google Sheets API Error] {e}")
        return {"status": "error", "message": str(e)}

# ==========================================
# 4. Google Drive 연동
# ==========================================

async def search_drive_files(user_id: uuid.UUID, keyword: str) -> List[Dict[str, Any]]:
    """구글 드라이브 파일 중 이름에 키워드가 포함된 파일을 검색합니다."""
    creds = await get_google_creds(user_id)

    if not creds:
        # Mock 데이터 반환
        print(f"[Google Workspace Fallback] Mocking Google Drive search for {user_id}")
        return [
            {
                "id": "mock-doc-file-id-1234",
                "name": f"상담일지 - 2026년 06월 24일",
                "mimeType": "application/vnd.google-apps.document"
            }
        ]

    def _search():
        service = build('drive', 'v3', credentials=creds)
        # 키워드 필터링 쿼리 구성
        query = f"name contains '{keyword}' and trashed = false"
        results = service.files().list(
            q=query,
            spaces='drive',
            fields='nextPageToken, files(id, name, mimeType)',
            maxResults=10
        ).execute()
        return results.get('files', [])

    try:
        files = await asyncio.to_thread(_search)
        return files
    except Exception as e:
        print(f"[Google Drive Search Error] {e}")
        return []

async def read_drive_file_content(user_id: uuid.UUID, file_id: str) -> str:
    """구글 드라이브 파일 ID를 받아 해당 파일 본문의 텍스트 내용을 추출합니다."""
    creds = await get_google_creds(user_id)

    if not creds:
        # Mock 데이터 반환
        print(f"[Google Workspace Fallback] Mocking Google Drive file read for {user_id}")
        return "상담일지 본문 내용:\n- 주요 호소: 사용자가 스마트홈 연동 지연으로 인한 불편을 겪고 있음.\n- 상담 내용: 백엔드 I/O 비동기 최적화 및 gRPC 스레드 연동 개선 예정 안내.\n- 다음 과제: DTW 알고리즘의 최적화 진행."

    def _read_content():
        # 파일 타입(MimeType)에 따라 Docs 문서 텍스트 또는 raw 텍스트 파일로 처리
        drive_service = build('drive', 'v3', credentials=creds)
        meta = drive_service.files().get(fileId=file_id, fields='mimeType, name').execute()
        mime_type = meta.get('mimeType')
        
        if mime_type == 'application/vnd.google-apps.document':
            # Google Docs 포맷인 경우 Docs API를 활용해 텍스트를 추출
            docs_service = build('docs', 'v1', credentials=creds)
            doc = docs_service.documents().get(documentId=file_id).execute()
            
            # 본문 구조에서 텍스트 축적
            text_runs = []
            for element in doc.get('body', {}).get('content', []):
                if 'paragraph' in element:
                    for part in element.get('paragraph', {}).get('elements', []):
                        if 'textRun' in part:
                            text_runs.append(part.get('textRun', {}).get('content', ""))
            return "".join(text_runs)
        else:
            # 기타 일반 텍스트 파일인 경우 드라이브 미디어 파일 다운로드 처리
            request = drive_service.files().get_media(fileId=file_id)
            import io
            from googleapiclient.http import MediaIoBaseDownload
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            return fh.getvalue().decode('utf-8', errors='ignore')

    try:
        content = await asyncio.to_thread(_read_content)
        return content
    except Exception as e:
        print(f"[Google Drive Read Error] {e}")
        return f"파일 내용을 읽어오는 데 실패하였습니다: {str(e)}"

async def create_or_append_drive_doc(user_id: uuid.UUID, filename: str, text_content: str) -> str:
    """구글 드라이브에서 특정 이름의 문서를 찾고, 존재하면 끝에 내용을 추가하며 없으면 새로 생성하여 내용을 씁니다. 문서의 공유 URL을 반환합니다."""
    creds = await get_google_creds(user_id)

    if not creds:
        # Mock 작동
        print(f"[Google Workspace Fallback] Mocking Doc create/append for {user_id}")
        return f"https://docs.google.com/document/d/mock-doc-id-{uuid.uuid4().hex[:8]}/edit"

    def _execute():
        drive_service = build('drive', 'v3', credentials=creds)
        docs_service = build('docs', 'v1', credentials=creds)

        # 1. 파일 존재 여부 검색
        query = f"name = '{filename}' and mimeType = 'application/vnd.google-apps.document' and trashed = false"
        results = drive_service.files().list(q=query, spaces='drive', fields='files(id)').execute()
        files = results.get('files', [])

        if files:
            file_id = files[0]['id']
            # 기존 문서 본문 끝에 추가 (Append)
            doc = docs_service.documents().get(documentId=file_id).execute()
            # 문서의 마지막 글자 위치(Index) 파악
            # body content의 마지막 요소의 endIdx를 찾습니다.
            body_content = doc.get('body', {}).get('content', [])
            end_idx = 1
            if body_content:
                end_idx = body_content[-1].get('endIndex', 1) - 1
                if end_idx < 1:
                    end_idx = 1

            requests = [
                {
                    'insertText': {
                        'location': {
                            'index': end_idx,
                        },
                        'text': "\n" + text_content
                    }
                }
            ]
            docs_service.documents().batchUpdate(documentId=file_id, body={'requests': requests}).execute()
        else:
            # 신규 생성
            file_metadata = {
                'name': filename,
                'mimeType': 'application/vnd.google-apps.document'
            }
            file = drive_service.files().create(body=file_metadata, fields='id').execute()
            file_id = file.get('id')

            # 초기 텍스트 삽입
            requests = [
                {
                    'insertText': {
                        'location': {
                            'index': 1,
                        },
                        'text': text_content
                    }
                }
            ]
            docs_service.documents().batchUpdate(documentId=file_id, body={'requests': requests}).execute()

        return f"https://docs.google.com/document/d/{file_id}/edit"

    try:
        url = await asyncio.to_thread(_execute)
        return url
    except Exception as e:
        print(f"[Google Doc Create/Append Error] {e}")
        return f"Error creating doc: {e}"

async def send_test_email(user_id: uuid.UUID, to_email: str, subject: str, body: str) -> Dict[str, Any]:
    """Gmail API를 사용하여 테스트 메일을 발송합니다. Credentials가 없을 경우 Mock 전송으로 Fallback합니다."""
    creds = await get_google_creds(user_id)
    if not creds:
        # Mock 데이터 전송 모사
        print(f"[Google Workspace Fallback] Mocking Gmail send for {user_id}")
        return {
            "status": "success",
            "message": "테스트 메일이 성공적으로 전송되었습니다 (Mock).",
            "message_id": f"mock-msg-id-{uuid.uuid4().hex[:12]}"
        }
        
    def _send():
        from email.mime.text import MIMEText
        import base64
        service = build('gmail', 'v1', credentials=creds)
        
        message = MIMEText(body)
        message['to'] = to_email
        message['from'] = 'me'
        message['subject'] = subject
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        return service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
        
    try:
        res = await asyncio.to_thread(_send)
        return {
            "status": "success",
            "message": "테스트 메일이 성공적으로 전송되었습니다.",
            "message_id": res.get("id")
        }
    except Exception as e:
        print(f"[Gmail Send Error] {e}")
        return {"status": "error", "message": str(e)}

