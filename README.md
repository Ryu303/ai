# ARGOS 프로젝트 백엔드 시스템

본 프로젝트는 외부 상용 유료 SaaS/솔루션을 완전히 배제하고, 직접 빌드한 비동기 Python 백엔드 및 DSP(Digital Signal Processing) 알고리즘을 결합한 FastAPI 애플리케이션입니다.

---

## 1. 아키텍처 및 디렉토리 구조

```
c:/Users/onekt/Desktop/ai 비서/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 진입점 및 라우터 정의
│   ├── config.py               # 설정 및 JWT/토큰 복호화 키 제어
│   ├── database.py             # SQLAlchemy 비동기 DB 커넥션 설정
│   ├── models.py               # SQLAlchemy 멀티테넌시 ORM 모델 (pgvector 지원)
│   ├── schemas.py              # Pydantic 데이터 검증 스키마
│   ├── background.py           # 60초 주기 모니터 및 일일 브리핑 제너레이터
│   └── services/
│       ├── __init__.py
│       ├── ai.py               # Gemini 2.5-flash 대화 및 Function Calling, Embedding
│       ├── google_workspace.py # Google Calendar, Gmail, Sheets, Drive 연동 (to_thread 비동기화)
│       ├── voice.py            # 볼륨 정규화, 무음 제거, 40차원 MFCC 추출, DTW 인증, 음성 스트레스 분석
│       ├── iot.py              # SwitchBot & 스마트 플러그 전력 제어 및 과부하 판별
│       └── orchestrator.py     # Tier 2 권한 승인 상태 머신 및 Gemini 2.0 상담 요약
├── tests/
│   └── test_voice.py           # DSP 모듈 단위 테스트 스크립트
├── requirements.txt            # 의존성 목록
└── README.md                   # 본 가이드
```

---

## 2. 필수 패키지 설치 및 환경 설정

### 2.1. 패키지 설치
```bash
pip install -r requirements.txt
```

### 2.2. 환경 변수 설정 (`.env`)
루트 디렉토리에 `.env` 파일을 생성하고 아래의 정보들을 기입합니다:

```env
DATABASE_URL=postgresql+asyncpg://<username>:<password>@<host>:<port>/<dbname>
GEMINI_API_KEY=AIzaSy... (구글 제미나이 API 키)
ENCRYPTION_KEY=... (32바이트 urlsafe base64 키 - 생략 시 메모리 임시 키로 작동)
GOOGLE_CLIENT_ID=... (선택 사항 - 구글 워크스페이스 OAuth 연동 테스트용)
GOOGLE_CLIENT_SECRET=... (선택 사항)
```

---

## 3. 핵심 API 엔드포인트 목록

모든 API 요청은 인증된 사용자 데이터의 격리(Multi-Tenancy)를 보장하기 위해 헤더에 `X-User-Id: <UUID>`를 필수로 요구합니다.

| 분류 | HTTP 메서드 | 엔드포인트 | 설명 |
| :--- | :--- | :--- | :--- |
| **사용자** | `POST` | `/api/v1/users` | 신규 사용자 테넌트 등록 |
| | `PUT` | `/api/v1/users/profile` | 사용자의 System Instruction용 프로필 업데이트 |
| **AI 비서** | `POST` | `/api/v1/ai/chat` | AI 대화 실행 (Function Calling 및 시맨틱 메모리 연동) |
| | `POST` | `/api/v1/ai/tts-reformat` | 300자 이상 응답에 대한 구어체 자연어 요약 가공 |
| **Google 연동** | `GET` | `/api/v1/google/calendar` | 오늘 하루 일정 조회 (00:00:00 ~ 23:59:59) |
| | `POST` | `/api/v1/google/calendar/create` | 신규 일정 동적 생성 |
| | `GET` | `/api/v1/google/gmail/unread` | 최신 미확인 Gmail 5개 리스트 요약 반환 |
| | `POST` | `/api/v1/google/sheets/append` | 구글 스프레드시트 빈 최하단 행 데이터 추가 |
| | `GET` | `/api/v1/google/drive/search` | 드라이브 파일 검색 |
| | `GET` | `/api/v1/google/drive/read/{file_id}` | 드라이브 문서 본문 텍스트 추출 |
| **바이오메트릭** | `POST` | `/api/v1/voice/register` | 사용자 성문 등록 (WAV 파일 수신) |
| | `POST` | `/api/v1/voice/verify` | DTW 알고리즘 성문 일치 판별 및 임계값 자동 조정 |
| | `POST` | `/api/v1/voice/stress-analysis` | F0, Jitter, Shimmer 진단 기반 사용자 스트레스 판정 |
| **오케스트레이션**| `POST` | `/api/v1/orchestration/run` | 고위험 시나리오 승인 제어 상태 머신 실행 (Tier 2) |
| | `POST` | `/api/v1/orchestration/consultation`| 상담일지 JSON 정형화 및 구글 드라이브 문서 기록 |
| **IoT 제어** | `POST` | `/api/v1/iot/toggle` | 스위치봇 및 스마트 플러그 ON/OFF 토글 제어 |
| | `GET` | `/api/v1/iot/power-check/{device_id}`| 스마트 플러그 전력량 검사 (2000W 제한 판단) |
| **모니터링** | `GET` | `/api/v1/notifications` | 60초 주기 진단 루프가 발행한 경고 알림 조회 |

---

## 4. 백엔드 기동 방법

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
기동이 성공적으로 완료되면 브라우저에서 `http://localhost:8000/docs` 로 접속하여 Swagger UI를 통해 모든 비동기 API 엔드포인트를 편리하게 직접 테스트해볼 수 있습니다.
