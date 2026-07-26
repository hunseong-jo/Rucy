"""
메일·캘린더 — 지메일을 읽고, 구글 캘린더를 보고, 일정을 넣습니다.

권한은 **일부러 좁게** 잡았습니다.
  · 메일 = 읽기 + **초안 만들기**(세션54). 루시는 메일을 **보내지 않습니다** — 사용자
    이름으로 나간 메일은 되돌릴 수 없으므로, 루시가 초안함까지만 쓰고 발송 버튼은
    사람이 누릅니다. ⚠️구글에 '초안만' 스코프는 없어서 gmail.compose(초안+발송)를
    받되, **이 코드에는 send를 부르는 줄이 존재하지 않습니다** — 안전장치는 스코프가
    아니라 코드에 있습니다. send를 추가하려는 사람은 이 줄부터 지우게 되길.
  · 캘린더 = 읽기 + 쓰기. 일정은 잘못 넣어도 지우면 그만이라 위험이 훨씬 작습니다.
    단, 넣기 전에 사용자 확인을 받습니다(tools의 _confirm). 참석자 초대(attendees)를
    넣으면 초대 메일이 밖으로 나가므로 같은 게이트 뒤에 있습니다.

첫 실행 때 브라우저가 열려 사용자가 '허용'을 눌러야 합니다. 그다음부터는 token이 저장돼
조용히 갱신됩니다(토큰 만료도 알아서 갱신). 이건 사람 손이 꼭 필요한 유일한 단계입니다.
"""
import base64
import datetime
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CRED_PATH = os.path.join(BASE_DIR, "keys", "google_credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "keys", "google_token.json")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",   # 초안 전용으로 씀 — send는 부르지 않음
    "https://www.googleapis.com/auth/calendar",
]

SETUP_GUIDE = f"""구글 연동이 아직 안 됐습니다. 한 번만 하면 됩니다 (5분):

  1. https://console.cloud.google.com/ 접속 → 프로젝트 만들기 (이름 아무거나)
  2. 'API 및 서비스' → '라이브러리' → Gmail API 와 Google Calendar API 를 각각 '사용'
  3. 'API 및 서비스' → 'OAuth 동의 화면' → 외부 → 앱 이름·이메일만 채우고 저장
     → '대상' 에서 본인 이메일을 '테스트 사용자'로 추가 (이걸 빼면 로그인이 거부됩니다)
  4. '사용자 인증 정보' → '사용자 인증 정보 만들기' → 'OAuth 클라이언트 ID'
     → 유형은 반드시 **데스크톱 앱**
  5. 만들어진 JSON을 내려받아 이 경로에 두세요:
     {CRED_PATH}

그다음 루시에게 '메일 확인해줘' 라고 하면 브라우저가 열립니다. '허용'을 누르면 끝입니다."""


def ready():
    return os.path.exists(CRED_PATH)


def _service(which):
    """구글에 로그인하고 서비스 객체를 돌려줍니다. 처음이면 브라우저가 열립니다."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    if not ready():
        raise RuntimeError(SETUP_GUIDE)

    creds = None
    if os.path.exists(TOKEN_PATH):
        # 스코프가 늘었는데 옛 토큰을 그대로 쓰면(예: 초안 권한 없는 토큰) 갱신은
        # 조용히 성공하고 **호출에서야 403**이 납니다. 여기서 미리 재승인으로 보냅니다.
        # ⚠️creds.scopes로 검사하면 안 됩니다 — from_authorized_user_file이 그 속성을
        #   '요청한' 스코프로 덮어써서 검사가 항상 통과합니다(실측). **파일에 적힌
        #   '부여된' 스코프**를 직접 읽어야 합니다.
        try:
            with open(TOKEN_PATH, "r", encoding="utf-8-sig") as f:
                granted = set(json.load(f).get("scopes") or [])
        except (OSError, ValueError):
            granted = set()
        if set(SCOPES) <= granted:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())            # 토큰 만료 — 조용히 갱신합니다
            except Exception:
                creds = None
                if os.path.exists(TOKEN_PATH):
                    try:
                        os.remove(TOKEN_PATH)
                    except OSError:
                        pass

        if not creds:
            print("\n  [구글] 브라우저가 열립니다. 계정을 고르고 '허용'을 눌러 주세요...")
            flow = InstalledAppFlow.from_client_secrets_file(CRED_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return build(which, "v3" if which == "calendar" else "v1", credentials=creds,
                 cache_discovery=False)


# ── 메일 ─────────────────────────────────────────────────────────
def _header(payload, name):
    for h in payload.get("headers", []):
        if h.get("name", "").lower() == name:
            return h.get("value", "")
    return ""


def _body_text(payload, limit=600):
    """본문에서 글자만 뽑습니다. 메일은 여러 부분(text/html)이 겹쳐 있어 재귀로 훑습니다."""
    if payload.get("body", {}).get("data"):
        raw = base64.urlsafe_b64decode(payload["body"]["data"] + "==")
        text = raw.decode("utf-8", errors="replace")
        if payload.get("mimeType") == "text/html":
            text = re.sub(r"<[^>]+>", " ", text)     # 태그를 걷어냅니다
        return re.sub(r"\s+", " ", text).strip()[:limit]

    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain":
            got = _body_text(part, limit)
            if got:
                return got
    for part in payload.get("parts", []):
        got = _body_text(part, limit)
        if got:
            return got
    return ""


def mail(query="is:unread", limit=10):
    """메일을 봅니다. query는 지메일 검색 문법 그대로 (is:unread, from:..., newer_than:2d)."""
    try:
        svc = _service("gmail")
        listing = svc.users().messages().list(
            userId="me", q=query, maxResults=int(limit)).execute()
        ids = [m["id"] for m in listing.get("messages", [])]
        if not ids:
            return []

        out = []
        for mid in ids:
            msg = svc.users().messages().get(
                userId="me", id=mid, format="full").execute()
            payload = msg.get("payload", {})
            out.append({
                "from": _header(payload, "from"),
                "subject": _header(payload, "subject") or "(제목 없음)",
                "date": _header(payload, "date"),
                "snippet": msg.get("snippet", "") or _body_text(payload, 300),
                "unread": "UNREAD" in msg.get("labelIds", []),
            })
        return out
    except Exception as e:
        raise RuntimeError(f"지메일 연동 에러/토큰 만료 (메모 확인 필요): {e}") from e


def create_draft(to, subject, body_text):
    """
    메일 초안을 지메일 **초안함에만** 만듭니다 — 보내지 않습니다.
    루시가 검토·작성까지 하고, 발송 버튼은 사람이 지메일에서 누릅니다(그게 안전장치).
    이 파일 어디에도 send를 부르는 줄이 없어야 합니다.
    """
    from email.mime.text import MIMEText

    svc = _service("gmail")
    msg = MIMEText(body_text or "", _charset="utf-8")   # 한글은 utf-8로 못박아야 안 깨집니다
    if to:
        msg["To"] = to
    msg["Subject"] = subject or "(제목 없음)"
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    made = svc.users().drafts().create(
        userId="me", body={"message": {"raw": raw}}).execute()
    return made.get("id", "")


def delete_draft(draft_id):
    """초안을 지웁니다(시험 뒷정리용 — 초안함은 사용자 공간이라 시험 흔적을 남기지 않습니다)."""
    _service("gmail").users().drafts().delete(userId="me", id=draft_id).execute()


# ── 캘린더 ───────────────────────────────────────────────────────
def _kst(dt):
    return dt.astimezone().isoformat()


def events(days=7, limit=20):
    """앞으로 며칠간의 일정."""
    try:
        svc = _service("calendar")
        now = datetime.datetime.now().astimezone()
        end = now + datetime.timedelta(days=int(days))
        got = svc.events().list(
            calendarId="primary", timeMin=_kst(now), timeMax=_kst(end),
            singleEvents=True, orderBy="startTime", maxResults=int(limit),
        ).execute()

        out = []
        for e in got.get("items", []):
            start = e.get("start", {})
            when = start.get("dateTime") or start.get("date", "")
            out.append({
                "id": e.get("id", ""),      # 선알림이 '이미 알렸는지'를 기억하는 열쇠
                "title": e.get("summary", "(제목 없음)"),
                "when": when,
                "allday": "date" in start and "dateTime" not in start,
                "where": e.get("location", ""),
            })
        return out
    except Exception as e:
        raise RuntimeError(f"캘린더 연동 에러/토큰 만료 (메모 확인 필요): {e}") from e


def add_event(title, start, end=None, description="", attendees=None):
    """
    일정을 넣습니다. start/end는 '2026-07-15 14:00' 또는 '2026-07-15'(종일).
    attendees(이메일 목록)를 주면 구글이 초대 메일을 보냅니다(sendUpdates="all") —
    초대장이 밖으로 나가는 일이므로, 실제 등록은 tools 쪽에서 사용자 확인을 받은 뒤에만 부릅니다.
    """
    svc = _service("calendar")
    allday = len(start.strip()) <= 10        # 시각이 없으면 종일 일정

    if allday:
        s = datetime.datetime.strptime(start.strip()[:10], "%Y-%m-%d").date()
        e = (datetime.datetime.strptime(end.strip()[:10], "%Y-%m-%d").date()
             if end else s) + datetime.timedelta(days=1)   # 구글은 종료일을 하루 뒤로 적습니다
        body = {"summary": title, "description": description,
                "start": {"date": s.isoformat()}, "end": {"date": e.isoformat()}}
    else:
        s = datetime.datetime.fromisoformat(start.strip()).astimezone()
        e = (datetime.datetime.fromisoformat(end.strip()).astimezone()
             if end else s + datetime.timedelta(hours=1))  # 끝 시각을 안 주면 1시간짜리로
        body = {"summary": title, "description": description,
                "start": {"dateTime": s.isoformat()}, "end": {"dateTime": e.isoformat()}}

    guests = [a.strip() for a in (attendees or []) if a and "@" in a]
    if guests:
        body["attendees"] = [{"email": a} for a in guests]

    made = svc.events().insert(calendarId="primary", body=body,
                               sendUpdates="all" if guests else "none").execute()
    return made.get("htmlLink", "등록됨")
