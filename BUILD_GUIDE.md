# 서초 채널 테니스 클럽 앱 - 빌드 가이드

## 데스크톱에서 실행 (Windows/Mac/Linux)

```bash
cd c:\Users\user\Downloads
python seocho_tennis_club.py
```

## 웹 앱으로 실행

```bash
flet run --web seocho_tennis_club.py
```

브라우저에서 `http://localhost:8550` 으로 접속

---

## Android APK 빌드

### 1. 사전 요구 사항
- Python 3.8 이상
- Flet 최신 버전 설치

```bash
pip install flet --upgrade
```

### 2. Android APK 빌드 명령어

```bash
cd c:\Users\user\Downloads
flet build apk seocho_tennis_club.py
```

빌드 완료 후 `build/apk/` 폴더에 APK 파일이 생성됩니다.

### 3. APK 설치
- 생성된 APK 파일을 Android 기기로 전송
- 기기에서 APK 파일을 열어 설치
- (설정에서 "알 수 없는 앱 설치" 허용 필요)

---

## iOS 앱 빌드

### 1. 사전 요구 사항
- macOS 필요
- Xcode 설치
- Apple Developer 계정

### 2. iOS 빌드 명령어

```bash
cd /path/to/project
flet build ipa seocho_tennis_club.py
```

### 3. iOS 앱 배포
- 생성된 IPA 파일을 Xcode 또는 Transporter로 App Store Connect에 업로드
- TestFlight로 테스트 배포 가능

---

## 클라우드 빌드 (권장)

Flet은 클라우드 빌드 서비스를 제공합니다:

```bash
# Flet 계정 로그인
flet login

# Android APK 클라우드 빌드
flet build apk --cloud seocho_tennis_club.py

# iOS IPA 클라우드 빌드 (macOS 없이도 가능)
flet build ipa --cloud seocho_tennis_club.py
```

---

## 앱 설정 커스터마이징

### 앱 아이콘 추가

1. `assets` 폴더 생성
2. 512x512 크기의 `icon.png` 파일 추가
3. `pyproject.toml`에서 아이콘 경로 설정:

```toml
[tool.flet]
icon = "assets/icon.png"
```

### 스플래시 화면 색상 변경

```toml
[tool.flet]
splash_color = "#4CAF50"  # 초록색
```

---

## 데이터 동기화 방법

1. 기기 A에서 **설정 > 내보내기** 클릭
2. 생성된 JSON 파일을 카카오톡, 이메일 등으로 공유
3. 기기 B에서 JSON 파일 다운로드
4. **설정 > 불러오기**로 데이터 가져오기

---

## 문제 해결

### 빌드 실패 시

```bash
# Flet 업데이트
pip install flet --upgrade

# 캐시 정리 후 재빌드
flet build apk --clean seocho_tennis_club.py
```

### 앱이 실행되지 않을 때

- Python 버전 확인 (3.8 이상)
- Flet 버전 확인 (`pip show flet`)
- 데이터 폴더 권한 확인
