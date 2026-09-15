# 오토다타 웹 시작 페이지

주소: **https://autodata.singlena.workers.dev**

인터넷 주소로 여는 **시작 페이지**입니다. 조사 파일 처리는 하지 않습니다.

- 이 컴퓨터에서 **오토다타 도우미**(`FieldSurveyDB.exe`)가 켜져 있는지 찾고
- 한글(HWP) 변환 · 스캔 글자 인식 · AI 키 준비 상태를 보여 주고
- **작업 화면 열기**로 도우미 화면(`http://127.0.0.1:포트/`)을 엽니다.

파일 · AI 키 · 결과 엑셀은 모두 그 컴퓨터에만 저장됩니다. 이 페이지는 정적 파일(HTML·CSS·JS·글꼴)뿐이라 서버 연산이 없습니다.

## 클라우드플레어 Workers 배포(한 번만 연결)

저장소 맨 위의 `wrangler.jsonc` 가 배포 설정입니다(Worker 이름 `autodata`, 올릴 폴더 `field-survey-db/web`).

1. Cloudflare 대시보드 → **Workers & Pages** → **autodata** → **Settings** → **Build** → **Connect**
2. GitHub 저장소 `circloser/fieldsurveyauto` 선택
3. 설정
   - Branch: `main`
   - Build command: *(비워 둠)*
   - Deploy command: `npx wrangler deploy` *(기본값)*
   - Root directory: `/` *(기본값)*
4. 저장하면 첫 배포가 돌고, 이후 `main` 에 푸시할 때마다 다시 배포됩니다.

도우미는 기본으로 `https://autodata.singlena.workers.dev` 의 요청만 받습니다(상태 읽기만, 파일·설정 변경은 불가).
기관 도메인을 따로 연결했다면 도우미 폴더(`FieldSurveyDB.exe` 옆)에 `web_origins.txt` 를 만들고 한 줄에 하나씩 적으세요.

```
https://autodata.example.org
https://*.autodata.example.org
```

## 도우미 새 버전 배포

1. `app/config.py` 의 `APP_VERSION` 과 이 폴더 `version.json` 의 `helper` 를 같은 번호로 올리고 커밋·푸시합니다.
2. 같은 번호로 태그를 푸시합니다.

   ```
   git tag v0.5.1
   git push origin v0.5.1
   ```

3. GitHub Actions(`.github/workflows/release.yml`)가 Windows에서 테스트 → 포터블 빌드 → 기동 확인을 거쳐
   Releases 에 두 파일을 올립니다.
   - `AutoData_Windows.zip` — 경량판(약 130MB). 시작 페이지의 내려받기 주소는 항상 최신 릴리스의 이 파일입니다.
     스캔 문서 글자 인식은 처음 쓸 때 공개 저장소에서 받습니다(`core/ocr_runtime.py`).
   - `AutoData_Windows_offline.zip` — 오프라인판(약 430MB, 글자 인식 엔진·모델 포함).
   빌드가 실패하면 실패한 단계의 마지막 출력이 그 실행의 주석(annotation)으로 남습니다.
4. 예전 도우미를 켠 사람에게는 시작 페이지가 새 버전 안내를 띄웁니다.

GitHub Releases 는 파일 하나당 2 GiB 미만이라 GPU판 전체 zip(약 2.1 GiB)은 올리지 않습니다 —
경량판에서 'GPU 가속판'을 받으면 같은 속도가 납니다. torch·EasyOCR 버전을 올리면
`scripts/make_ocr_manifest.py` 로 내려받기 목록을 다시 만드세요(테스트가 버전 불일치를 잡습니다).

## 로컬에서 확인

```
python -m http.server 8788 --directory web
```

도우미 개발 서버가 다른 포트(예: 8791)에서 돌면 `http://localhost:8788/?port=8791` 로 엽니다.

## 브라우저 허용

크롬 등은 인터넷 주소의 페이지가 이 컴퓨터(127.0.0.1)에 연결할 때 **로컬 네트워크 접근** 허용을 한 번 묻습니다. 허용해야 도우미를 찾을 수 있습니다.
