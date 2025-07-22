# Railway용 Dockerfile - 보컬 분리 앱
FROM python:3.9-slim

# 시스템 패키지 설치 (ffmpeg 등)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# Python 의존성 먼저 복사 및 설치 (캐싱 최적화)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# Railway가 자동으로 감지할 디렉토리 생성
RUN mkdir -p uploads outputs logs

# 포트 설정 (Railway가 자동으로 $PORT 환경변수 제공)
EXPOSE $PORT

# 애플리케이션 실행
CMD ["python", "main.py"]