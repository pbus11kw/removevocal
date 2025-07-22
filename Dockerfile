# Railway용 Dockerfile - 보컬 분리 앱 (경량화)
FROM python:3.9-slim

# 환경변수 설정
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 필수 시스템 패키지만 설치
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# 웹 프레임워크 먼저 설치 (로컬과 동일한 버전)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Spleeter 설치 (최신 typing_extensions와 강제 호환)
RUN pip install --no-cache-dir spleeter==2.3.0 --no-deps
RUN pip install --no-cache-dir librosa==0.8.0 tensorflow==2.5.0 numpy==1.19.5

# 최종적으로 로컬과 동일한 typing_extensions 유지
RUN pip install --no-cache-dir --force-reinstall typing_extensions==4.14.1

# 애플리케이션 코드 복사
COPY . .

# Railway가 자동으로 감지할 디렉토리 생성
RUN mkdir -p uploads outputs logs

# 포트 설정 (Railway가 자동으로 $PORT 환경변수 제공)
EXPOSE $PORT

# 애플리케이션 실행
CMD ["python", "main.py"]