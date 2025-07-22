# Railway용 Dockerfile - 보컬 분리 앱
FROM python:3.9-slim

# 메모리 효율성을 위한 환경변수 설정
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# 시스템 패키지 설치 (ffmpeg 등)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 작업 디렉토리 설정
WORKDIR /app

# Python 의존성 먼저 복사 및 설치 (캐싱 최적화)
COPY requirements.txt .

# 메모리 사용량을 줄이기 위해 단계별 설치
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir tensorflow==2.8.4 keras==2.8.0 numpy==1.21.6
RUN pip install --no-cache-dir librosa==0.8.1
RUN pip install --no-cache-dir spleeter==2.3.0
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# Railway가 자동으로 감지할 디렉토리 생성
RUN mkdir -p uploads outputs logs

# 포트 설정 (Railway가 자동으로 $PORT 환경변수 제공)
EXPOSE $PORT

# 애플리케이션 실행
CMD ["python", "main.py"]