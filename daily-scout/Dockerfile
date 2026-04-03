# Daily Wellness Scout - 백그라운드 자동 실행 에이전트
FROM python:3.11-slim

# 작업 디렉토리
WORKDIR /app

# 시스템 패키지 설치 (타임존 + 크롤링 의존성)
RUN apt-get update && apt-get install -y \
    tzdata \
    curl \
    wget \
    ca-certificates \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# 타임존 설정 (한국 시간)
ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Python 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright 시스템 의존성 먼저 설치 (Debian Trixie 호환)
RUN apt-get update && apt-get install -y \
    # Playwright 의존성
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    fonts-liberation \
    fonts-unifont \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Playwright 브라우저 엔진 설치 (시스템 의존성 없이 브라우저만)
RUN playwright install chromium

# 애플리케이션 코드 복사
COPY ./app /app/app

# 데이터 및 로그 디렉토리 생성
RUN mkdir -p /app/data /app/logs

# 환경 변수
ENV PYTHONUNBUFFERED=1

# 에이전트 실행
CMD ["python", "-u", "app/daily_scout.py"]
