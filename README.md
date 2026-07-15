# Realty — 아파트 모니터링 대시보드

관심 아파트 단지의 **매물 수량 추이**, **동/층별 매물 소멸 감지 + 실거래가 매칭 추정**,
**뉴스·네이버 카페 글 모아보기**를 한 화면에서 보는 개인용 웹 앱.

## 동작 방식

- **매물**: 네이버 부동산을 하루 2회(10시, 18시) 스냅샷 수집 → 이전 스냅샷과 비교(diff)해
  신규/가격변동/소멸 이벤트를 기록. 매물 수는 날짜별로 집계되어 추이 차트로 표시.
- **실거래가**: 국토교통부 공공 API로 매일 11시 최근 3개월치를 재조회(신고 지연·계약 해제 반영).
- **매칭**: 소멸된 매매 매물과 실거래를 면적·층·동·시기·가격으로 비교해
  "이 매물이 얼마에 팔린 듯"을 신뢰도(HIGH/MEDIUM/LOW)와 함께 로그로 남김. **어디까지나 추정임.**
- **뉴스·카페**: 네이버 검색 API(공식)로 하루 4회 키워드 검색, 중복 제거 후 피드에 표시.

> ⚠ 실거래 신고 기한이 계약 후 30일이라, 매물이 사라지고 실제 거래가 확인되기까지
> 최대 한 달 걸릴 수 있습니다. 그동안은 "매칭 대기"로 표시됩니다.

## 구성

- **백엔드**: FastAPI (JSON API + React 빌드 결과물 서빙) — `app/`
- **프론트엔드**: React + Vite — `frontend/` (빌드하면 `frontend/dist` 생성, FastAPI가 이를 서빙)
- **DB**: 로컬은 SQLite(`data/realty.db`), 배포는 Postgres(`DATABASE_URL`)

## 로컬 실행 (macOS)

### 사전 준비 (최초 1회)

[Homebrew](https://brew.sh)로 `uv`(파이썬 관리)와 `node`(프론트엔드 빌드)를 설치합니다.
> macOS 기본 파이썬(3.9)은 SQLAlchemy 2.0의 타입 어노테이션을 런타임에 해석하지 못하므로,
> `uv`로 배포 타깃과 동일한 **Python 3.12** 환경을 만들어 씁니다.

```bash
brew install uv node
```

### 1. 백엔드 의존성 설치

```bash
cd ~/Downloads/realty
uv venv --python 3.12 .venv
VIRTUAL_ENV=.venv uv pip install -r requirements.txt
```

### 2. 프론트엔드 빌드

```bash
cd frontend
npm install
npm run build          # frontend/dist 생성 (FastAPI가 서빙)
cd ..
```

### 3. 서버 실행

```bash
DISABLE_SCHEDULER=1 DATABASE_URL="" APP_PASSWORD="" TZ=Asia/Seoul \
  .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010
```

브라우저에서 http://127.0.0.1:8010 접속.

| 환경변수 | 의미 |
|---|---|
| `DISABLE_SCHEDULER=1` | 자동 수집 스케줄러 끔 (로컬에선 화면 버튼/스크립트로 수동 수집) |
| `DATABASE_URL=""` | 비우면 로컬 SQLite(`data/realty.db`) 사용 |
| `APP_PASSWORD=""` | 비우면 비밀번호 없이 접속 |

화면 우상단의 **매물/실거래/뉴스 수집** 버튼으로 즉시 수집하거나, 앱 실행 없이:

```bash
DATABASE_URL="" .venv/bin/python scripts/collect_now.py --job all   # listings/transactions/articles
```

> 매물 수집(네이버 부동산)은 키 없이 동작하지만, 실거래·뉴스 수집은 아래 API 키가 필요합니다.

### 개발 모드 (UI 수정 시 핫리로드)

프론트를 매번 빌드하지 않고 Vite 개발 서버(5173)를 씁니다. `/api`는 8010으로 프록시됩니다.

```bash
# 터미널 1 — 백엔드
DISABLE_SCHEDULER=1 .venv/bin/uvicorn app.main:app --port 8010

# 터미널 2 — 프론트엔드
cd frontend && npm run dev
```

→ http://localhost:5173 접속

### 테스트

```bash
DATABASE_URL="" .venv/bin/python -m pytest
```

## 설치 (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

## API 키 발급 (최초 1회)

1. **실거래가** — [공공데이터포털](https://www.data.go.kr) 회원가입 →
   ["아파트 매매 실거래가 자료"](https://www.data.go.kr/data/15126469/openapi.do) 활용신청 →
   마이페이지에서 **일반 인증키(Decoding)** 복사
2. **뉴스/카페** — [네이버 개발자센터](https://developers.naver.com/apps) 애플리케이션 등록
   (사용 API: 검색) → Client ID / Client Secret 복사
3. `.env.example`을 `.env`로 복사하고 키 입력

## 단지 등록

`complexes.yaml`에 단지를 추가:

```yaml
complexes:
  - name: 헬리오시티
    naver_complex_no: "111515"   # 아래 방법으로 확인
    lawd_cd: "11710"             # 법정동코드 앞 5자리 (https://www.code.go.kr)
    apt_name_molit: 헬리오시티    # 실거래가 API상 단지명 (비워두면 이름 부분일치)
    keywords: [헬리오시티, 송파 헬리오시티]
```

- **naver_complex_no**: `python scripts/find_complex.py "단지명"` 또는
  브라우저에서 new.land.naver.com 검색 후 주소창의 `/complexes/{번호}`
- **apt_name_molit**: 처음엔 비워두고 실거래 수집을 한 번 실행하면,
  이름이 안 맞을 때 로그에 그 지역 단지명 목록이 표시되므로 그걸 보고 채우면 됨

## 실행 (Windows)

> 프론트엔드 빌드가 선행되어야 합니다: `cd frontend && npm install && npm run build`

```powershell
.\.venv\Scripts\uvicorn app.main:app --port 8000
```

브라우저에서 http://localhost:8000 접속. 앱이 켜져 있는 동안 스케줄러가 자동 수집합니다
(매물 10/18시, 실거래 11시, 뉴스·카페 8/12/17/21시). 화면 상단 버튼으로 즉시 수집도 가능.

수동 수집 (앱 실행 없이):

```powershell
.\.venv\Scripts\python scripts\collect_now.py --job all   # 또는 listings/transactions/articles
```

## 주의사항

- 네이버 부동산 수집은 비공식 API를 사용하는 **개인 이용 목적의 저빈도 수집**입니다.
  수집 주기를 과도하게 늘리지 마세요 (차단될 수 있음).
- PC가 꺼져 있는 동안은 수집이 쉽니다. 그날의 diff는 다음 수집 때 한꺼번에 반영됩니다.
- 데이터는 `data/realty.db` (SQLite) 한 파일에 저장됩니다. 백업은 이 파일만 복사하면 됩니다.

## 테스트

```powershell
.\.venv\Scripts\python -m pytest
```

## 무료 클라우드 배포 (Render + Neon)

PC를 꺼도 항상 접속되게 하려면 (모두 무료):

1. **Neon** (neon.tech) 가입 → 프로젝트 생성 (리전: Singapore) → **Connection string** 복사
   (예: `postgresql://user:pw@ep-xxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`)
2. **GitHub**에 이 저장소를 push (Private 권장)
3. **Render** (render.com) → New → **Blueprint** → GitHub 저장소 연결
   (`render.yaml`이 자동 인식됨) → 환경변수 입력:
   - `DATABASE_URL`: Neon 연결 주소
   - `MOLIT_API_KEY`, `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`: `.env`와 동일
   - `APP_PASSWORD`: `/collect/*` 수집 트리거 보호용 키 (화면 접속과는 무관)
4. **cron-job.org** 가입 → 아래 URL로 크론 잡 등록 (시간대 Asia/Seoul):
   | URL | 시각 |
   |---|---|
   | `https://<앱>.onrender.com/collect/listings?key=<비밀번호>` | 10:00, 18:00 |
   | `https://<앱>.onrender.com/collect/transactions?key=<비밀번호>` | 11:00 |
   | `https://<앱>.onrender.com/collect/articles?key=<비밀번호>` | 08:00, 12:00, 17:00, 21:00 |
   | `https://<앱>.onrender.com/` (keep-alive, 로그인 없음) | 10분마다 |

접속: `https://<앱>.onrender.com` — 화면은 비밀번호 없이 바로 열림.
`APP_PASSWORD`는 `/collect/*` 엔드포인트(크론 트리거)만 보호한다.

> **빌드 과정**: `render.yaml`의 `buildCommand`가 파이썬 의존성 설치에 이어
> `cd frontend && npm ci && npm run build`로 React 앱을 빌드합니다.
> Render의 Python 런타임에는 Node.js가 포함되어 있어 별도 설정 없이 동작합니다.
> `main`(또는 연결한 브랜치)에 push할 때마다 자동 재배포됩니다.

무료 티어 특성:
- 15분 무접속 시 잠들었다가 접속하면 ~1분 걸려 깨어남 (첫 화면만 느림)
- 무료 인스턴스 시간은 계정당 월 750시간 — 다른 무료 서비스와 공유되므로
  항상 깨워두는 keepalive는 권장하지 않음

### 매물 수집은 집 PC에서 (하이브리드)

**네이버 부동산은 클라우드(데이터센터) IP를 차단**하므로 매물 수집만 집 PC가 담당한다
(실거래·뉴스는 클라우드에서 정상). 로컬 `.env`에 클라우드와 **같은 `DATABASE_URL`**(Neon)을
넣으면 PC 수집 결과가 곧바로 클라우드 화면에 반영된다.

#### macOS (launchd)

`~/Library/LaunchAgents/com.realty.listings.plist` 생성 (매일 10:00·18:00 실행,
경로는 본인 저장소 위치로 수정):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.realty.listings</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/이름/Downloads/realty/.venv/bin/python</string>
    <string>scripts/collect_now.py</string>
    <string>--job</string><string>listings</string>
  </array>
  <key>WorkingDirectory</key><string>/Users/이름/Downloads/realty</string>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Hour</key><integer>10</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>18</integer><key>Minute</key><integer>0</integer></dict>
  </array>
  <key>StandardOutPath</key><string>/tmp/realty-listings.log</string>
  <key>StandardErrorPath</key><string>/tmp/realty-listings.err</string>
</dict>
</plist>
```

등록:

```bash
launchctl load ~/Library/LaunchAgents/com.realty.listings.plist
launchctl start com.realty.listings   # 즉시 한 번 실행해 확인
```

> launchd는 예약 시각에 Mac이 꺼져 있었으면 **다음 켜졌을 때 한 번** 실행합니다.
> 잠자기 중에도 실행되게 하려면 `sudo pmset repeat wakeorpoweron MTWRFSU 09:58:00`처럼
> 깨우기 일정을 걸어두면 됩니다.

#### Windows (작업 스케줄러)

"Realty-listings" 작업 등록 (매일 10:00/18:00, 절전 깨우기):

```powershell
$action = New-ScheduledTaskAction -Execute "$PWD\.venv\Scripts\python.exe" `
  -Argument "scripts\collect_now.py --job listings" -WorkingDirectory "$PWD"
$t1 = New-ScheduledTaskTrigger -Daily -At 10:00
$t2 = New-ScheduledTaskTrigger -Daily -At 18:00
$settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable `
  -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName "Realty-listings" -Action $action -Trigger $t1,$t2 -Settings $settings
```

PC는 "시스템 종료" 대신 "절전"으로 두면 수집 시각에 스스로 깨어난다.
