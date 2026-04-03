FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 전체 PM Agent 코드 복사
COPY *.py ./
COPY static/ ./static/
COPY templates/ ./templates/
COPY migrations/ ./migrations/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# 데이터 디렉토리
RUN mkdir -p /app/data /app/logs

# 환경 변수 (docker-compose에서 주입)
ENV ANTHROPIC_API_KEY=""
ENV CLAUDE_MODEL="claude-sonnet-4-5-20250929"
ENV ALLOW_LOCAL_NOAUTH="false"
ENV HOST="0.0.0.0"
ENV PORT="8001"

EXPOSE 8001

# 헬스체크
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')" || exit 1

CMD ["uvicorn", "approval_ui_app:app", "--host", "0.0.0.0", "--port", "8001"]
