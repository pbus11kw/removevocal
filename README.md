# 🎤 MP3 보컬 분리기

AI 기반 음성 분리 서비스로, MP3 파일이나 YouTube 링크에서 보컬과 반주를 분리할 수 있습니다.

## ✨ 주요 기능

- 📁 **MP3 파일 업로드**: 로컬 MP3 파일에서 보컬/반주 분리
- 🎬 **YouTube 다운로드**: YouTube URL에서 직접 오디오 추출 및 분리
- 🚀 **실시간 진행률**: 작업 진행 상황을 실시간으로 확인
- ⚡ **동시 처리**: 최대 3명의 사용자가 동시에 서비스 이용 가능
- 📱 **반응형 디자인**: 모바일/데스크톱 모두 지원

## 🛠️ 기술 스택

- **Backend**: FastAPI, Python
- **AI Model**: Spleeter (Deezer)
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Audio Processing**: librosa, yt-dlp

## 📋 요구 사항

- Python 3.8+
- FFmpeg (오디오 처리용)
- 약 1GB의 저장 공간 (사전 훈련된 모델용)

## 🚀 설치 및 실행

### 1. 저장소 클론
```bash
git clone https://github.com/yourusername/removevocal.git
cd removevocal
```

### 2. 가상환경 생성 및 활성화
```bash
python -m venv venv

# Windows
venv\\Scripts\\activate

# macOS/Linux
source venv/bin/activate
```

### 3. 종속성 설치
```bash
pip install -r requirements.txt
```

### 4. FFmpeg 설치

**Windows:**
```bash
# Chocolatey 사용 시
choco install ffmpeg

# 또는 https://ffmpeg.org/download.html 에서 직접 다운로드
```

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

### 5. 환경 설정
```bash
# .env.example을 .env로 복사
cp .env.example .env

# 필요시 .env 파일 편집
```

### 6. 서버 실행
```bash
python main.py
```

또는 Windows에서:
```bash
run.bat
```

웹 브라우저에서 `http://localhost:8000`으로 접속하세요.

## ⚙️ 설정

`config.ini` 파일에서 다음 설정을 조정할 수 있습니다:

```ini
[LIMITS]
MAX_FILE_SIZE_MB = 50
MAX_DURATION_SECONDS = 420

[CONCURRENCY]
MAX_CONCURRENT_TASKS = 3
TASK_TIMEOUT_SECONDS = 600
```

## 📁 프로젝트 구조

```
removevocal/
├── main.py                 # FastAPI 메인 애플리케이션
├── task_manager.py         # 백그라운드 작업 관리
├── config_manager.py       # 설정 관리
├── audio_utils.py          # 오디오 처리 유틸리티
├── file_handlers.py        # 파일 처리 로직
├── logger.py              # 로깅 설정
├── config.ini             # 기본 설정 파일
├── requirements.txt       # Python 종속성
├── templates/
│   └── index.html         # 메인 웹 페이지
├── static/
│   └── style.css          # 스타일시트
├── uploads/               # 업로드된 파일 (임시)
├── outputs/               # 분리된 오디오 파일 (임시)
└── logs/                  # 로그 파일
```

## 🎯 사용법

1. **파일 업로드**: "MP3 업로드" 탭에서 오디오 파일 선택
2. **YouTube URL**: "YouTube URL" 탭에서 링크 입력
3. **분리 시작**: "분리하기" 버튼 클릭
4. **진행률 확인**: 실시간으로 작업 진행 상황 모니터링
5. **결과 다운로드**: 완료 후 보컬, 반주, 원본 파일 다운로드

## 🔧 배포

### Render.com 배포

1. `render.yaml` 파일이 포함되어 있어 Render.com에서 쉽게 배포 가능
2. GitHub 저장소를 Render.com에 연결
3. 환경 변수 설정 필요

### Docker 배포

```bash
# Dockerfile 생성 후
docker build -t removevocal .
docker run -p 8000:8000 removevocal
```

## ⚠️ 주의사항

- 사전 훈련된 AI 모델은 첫 실행 시 자동으로 다운로드됩니다 (~588MB)
- 업로드된 파일과 결과 파일은 일정 시간 후 자동으로 삭제됩니다
- YouTube 다운로드는 저작권 정책을 준수해주세요

## 🤝 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 있습니다. 자세한 내용은 `LICENSE` 파일을 참조하세요.

## 🙏 감사의 말

- [Spleeter](https://github.com/deezer/spleeter) - Deezer의 오픈 소스 음성 분리 라이브러리
- [FastAPI](https://fastapi.tiangolo.com/) - 현대적이고 빠른 Python 웹 프레임워크
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - YouTube 다운로드 도구

## 🐛 버그 신고

버그를 발견하셨나요? [Issues 페이지](https://github.com/yourusername/removevocal/issues)에서 신고해주세요.

---

⭐ 이 프로젝트가 도움이 되었다면 스타를 눌러주세요!