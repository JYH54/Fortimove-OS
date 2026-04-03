#!/bin/bash
set -e

echo "🚀 Fortimove PM Agent Production 배포 시작"
echo "=========================================="

# 변수 설정 (수정 필요)
DOMAIN="your-domain.com"  # 실제 도메인으로 변경
ANTHROPIC_KEY="sk-ant-your-key"  # 실제 API 키로 변경

# 1. 시스템 업데이트
echo "📦 시스템 패키지 업데이트..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y nginx certbot python3-certbot-nginx python3 python3-pip python3-venv git ufw curl

# 2. 방화벽 설정
echo "🔒 방화벽 설정..."
sudo ufw --force enable
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# 3. 코드 배포
echo "📥 코드 배포..."
cd ~
if [ ! -d "Fortimove-OS" ]; then
    git clone https://github.com/your-org/Fortimove-OS.git
else
    cd Fortimove-OS && git pull && cd ..
fi
cd Fortimove-OS/pm-agent

# 4. Python 가상환경
echo "🐍 Python 환경 구성..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. 환경변수 생성
echo "⚙️  환경변수 생성..."
ADMIN_TOKEN=$(openssl rand -hex 32)
cat > .env << EOF
ANTHROPIC_API_KEY=$ANTHROPIC_KEY
ADMIN_TOKEN=$ADMIN_TOKEN
DATABASE_PATH=/home/ubuntu/pm-agent-data/approval_queue.db
EOF

echo "✅ ADMIN_TOKEN: $ADMIN_TOKEN"
echo "⚠️  이 토큰을 안전한 곳에 저장하세요!"

# 6. 데이터 디렉토리
echo "📁 데이터 디렉토리 생성..."
mkdir -p ~/pm-agent-data
chmod 700 ~/pm-agent-data

# 7. systemd 서비스
echo "🔧 systemd 서비스 등록..."
sudo tee /etc/systemd/system/pm-agent.service > /dev/null << EOF
[Unit]
Description=Fortimove PM Agent Approval API
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/Fortimove-OS/pm-agent
Environment="PATH=/home/ubuntu/Fortimove-OS/pm-agent/venv/bin"
EnvironmentFile=/home/ubuntu/Fortimove-OS/pm-agent/.env
ExecStart=/home/ubuntu/Fortimove-OS/pm-agent/venv/bin/uvicorn approval_ui_app:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable pm-agent
sudo systemctl start pm-agent

# 8. Nginx 설정
echo "🌐 Nginx 리버스 프록시 설정..."
sudo tee /etc/nginx/sites-available/pm-agent > /dev/null << EOF
server {
    listen 80;
    server_name $DOMAIN;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/pm-agent /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# 9. SSL 인증서
echo "🔐 SSL 인증서 발급..."
echo "⚠️  DNS가 $DOMAIN → 1.201.124.96 로 설정되어 있어야 합니다!"
read -p "DNS 설정이 완료되었습니까? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN --redirect
    echo "✅ SSL 인증서 발급 완료"
else
    echo "⏭️  SSL 단계 건너뜀. 나중에 실행: sudo certbot --nginx -d $DOMAIN"
fi

# 10. 최종 확인
echo ""
echo "=========================================="
echo "✅ 배포 완료!"
echo "=========================================="
echo "🌐 서비스 URL: https://$DOMAIN"
echo "🔑 Admin Token: $ADMIN_TOKEN"
echo ""
echo "📋 Health Check:"
curl -s http://127.0.0.1:8000/health | python3 -m json.tool || echo "서비스 시작 대기 중..."
echo ""
echo "📊 서비스 상태 확인:"
sudo systemctl status pm-agent --no-pager
