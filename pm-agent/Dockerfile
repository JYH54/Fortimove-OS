FROM python:3.11-slim

WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# PM 에이전트 코드 복사
COPY pm_agent.py .
COPY test_pm.py .

# 환경 변수 (docker-compose에서 주입)
ENV ANTHROPIC_API_KEY=""

CMD ["python", "pm_agent.py"]
