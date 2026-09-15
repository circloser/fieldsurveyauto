# 오토다타 웹 시작 페이지

인터넷 주소로 여는 **시작 페이지**입니다. 조사 파일 처리는 하지 않습니다.

- 이 컴퓨터에서 **오토다타 도우미**(`FieldSurveyDB.exe`)가 켜져 있는지 찾고
- 한글(HWP) 변환 · 스캔 글자 인식 · AI 키 준비 상태를 보여 주고
- **작업 화면 열기**로 도우미 화면(`http://127.0.0.1:포트/`)을 엽니다.

파일 · AI 키 · 결과 엑셀은 모두 그 컴퓨터에만 저장됩니다. 이 페이지는 정적 파일(HTML·CSS·JS·글꼴)뿐이라 서버 연산이 없습니다.

## 클라우드플레어 Pages 배포

1. Cloudflare 대시보드 → **Workers & Pages** → **Create** → **Pages** → **Connect to Git** → 저장소 `circloser/fieldsurveyauto` 선택
2. 빌드 설정
   - Framework preset: **None**
   - Build command: *(비워 둠)*
   - Build output directory: **`field-survey-db/web`**
   - Production branch: `main`
3. 배포되면 주소가 `https://<프로젝트 이름>.pages.dev` 로 생깁니다.

도우미는 기본으로 `https://fieldsurveyauto.pages.dev` 와 그 미리보기 주소(`https://*.fieldsurveyauto.pages.dev`)의 요청만 받습니다.
프로젝트 이름을 다르게 만들었거나 기관 도메인을 연결했다면, 도우미 폴더(`FieldSurveyDB.exe` 옆)에 `web_origins.txt` 를 만들고 한 줄에 하나씩 적으세요.

```
https://autodata.example.org
https://*.autodata.example.org
```

## 도우미 새 버전 배포

1. `app/config.py` 의 `APP_VERSION` 과 이 폴더의 `version.json` 의 `helper` 를 같은 번호로 올립니다.
2. `scripts/make_portable.py` 로 만든 zip 을 GitHub **Releases** 에 올립니다(파일 하나당 2 GiB 미만 — GPU판 전체 zip은 이 한도를 넘습니다).
3. `main` 에 푸시하면 Pages 가 다시 배포되고, 시작 페이지가 예전 도우미를 쓰는 사람에게 새 버전 안내를 띄웁니다.

## 로컬에서 확인

```
python -m http.server 8788 --directory web
```

도우미 개발 서버가 다른 포트(예: 8791)에서 돌면 `http://localhost:8788/?port=8791` 로 엽니다.

## 브라우저 허용

크롬 등은 인터넷 주소의 페이지가 이 컴퓨터(127.0.0.1)에 연결할 때 **로컬 네트워크 접근** 허용을 한 번 묻습니다. 허용해야 도우미를 찾을 수 있습니다.
