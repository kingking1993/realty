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

## 설치

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

## 실행

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
2. **GitHub**에 이 저장소를 **Private**으로 push
3. **Render** (render.com) → New → **Blueprint** → GitHub 저장소 연결
   (`render.yaml`이 자동 인식됨) → 환경변수 입력:
   - `DATABASE_URL`: Neon 연결 주소
   - `MOLIT_API_KEY`, `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`: `.env`와 동일
   - `APP_PASSWORD`: 접속 비밀번호 (둘만 아는 값)
4. **cron-job.org** 가입 → 아래 URL로 크론 잡 등록 (시간대 Asia/Seoul):
   | URL | 시각 |
   |---|---|
   | `https://<앱>.onrender.com/collect/listings?key=<비밀번호>` | 10:00, 18:00 |
   | `https://<앱>.onrender.com/collect/transactions?key=<비밀번호>` | 11:00 |
   | `https://<앱>.onrender.com/collect/articles?key=<비밀번호>` | 08:00, 12:00, 17:00, 21:00 |

접속: `https://<앱>.onrender.com` — 브라우저가 아이디/비밀번호를 물으면
아이디는 아무거나, 비밀번호는 `APP_PASSWORD` 값.

무료 티어 특성:
- 15분 무접속 시 잠들었다가 접속하면 ~1분 걸려 깨어남 (첫 화면만 느림)
- 무료 인스턴스 시간은 계정당 월 750시간 — 다른 무료 서비스와 공유되므로
  항상 깨워두는 keepalive는 권장하지 않음
- 네이버 부동산이 클라우드 IP를 차단하면 매물 수집만 실패할 수 있음
  (실거래·뉴스는 영향 없음) — 이 경우 매물 수집만 집 PC에서 돌리는 방법이 있음
