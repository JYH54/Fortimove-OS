FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl fonts-nanum \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/fonts /app/data && \
    cp /usr/share/fonts/truetype/nanum/Nanum* /app/fonts/ 2>/dev/null || true

EXPOSE 8051

CMD ["uvicorn", "approval_ui_app:app", "--host", "0.0.0.0", "--port", "8051"]
