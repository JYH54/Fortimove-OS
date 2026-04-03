# Fortimove PM Agent - Production Deployment Guide

**Version**: 1.0
**Last Updated**: 2026-03-30
**Target**: Production-ready deployment with HTTPS and secure token authentication

---

## ⚠️ CRITICAL SECURITY REQUIREMENTS

### 1. HTTPS is MANDATORY

**Why**: The Approval UI API uses `X-API-TOKEN` header authentication. If deployed over HTTP, tokens are transmitted in **plaintext** and can be intercepted by attackers (Man-in-the-Middle attacks).

**Requirements**:
- ✅ HTTPS with valid TLS certificate (Let's Encrypt recommended)
- ✅ Reverse proxy (Nginx, Caddy, or Traefik)
- ❌ DO NOT expose FastAPI directly to the internet over HTTP
- ❌ DO NOT use self-signed certificates in production

**Risk if ignored**: Attackers can intercept `ADMIN_TOKEN` and gain full access to approval queue, exports, and handoff operations.

---

## Environment Modes

### Local Development Mode
```bash
export ALLOW_LOCAL_NOAUTH="true"
# ADMIN_TOKEN not required
# All endpoints accessible without authentication
# ⚠️ NEVER use this in staging or production
```

**Use case**: Local testing, fast iteration
**Security**: None (all endpoints open)

### Staging/Test Mode
```bash
export ADMIN_TOKEN="test_token_12345"
export ALLOW_LOCAL_NOAUTH="false"  # or unset
# Use test credentials for Slack/SMTP
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/TEST/..."
export SMTP_HOST="smtp.example.test"
```

**Use case**: Pre-production verification
**Security**: Token required, but weaker token acceptable

### Production Mode
```bash
export ADMIN_TOKEN="$(openssl rand -base64 32)"  # Strong random token
export ALLOW_LOCAL_NOAUTH="false"  # or unset (default)
# Use real production credentials
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/PROD/..."
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="ops@fortimove.com"
export SMTP_PASS="app_specific_password_here"
export EMAIL_FROM="ops@fortimove.com"
export EMAIL_TO="team@fortimove.com"
```

**Use case**: Real operations
**Security**: Strong random token (≥32 chars), HTTPS mandatory

---

## Required Environment Variables

### Authentication (Required)
```bash
# Production: Strong random token
ADMIN_TOKEN="your_strong_random_token_here_32_chars_minimum"

# Local dev only: Disable auth (DO NOT use in production)
ALLOW_LOCAL_NOAUTH="true"  # default: false
```

### Handoff - Slack (Optional)
```bash
SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```
If not set: Handoff runs in `log_only` mode (no real Slack messages sent)

### Handoff - Email (Optional)
```bash
SMTP_HOST="smtp.gmail.com"
SMTP_PORT="587"  # default: 587
SMTP_USER="your_email@example.com"
SMTP_PASS="your_app_specific_password"
EMAIL_FROM="admin@fortimove.com"  # default: admin@fortimove.com
EMAIL_TO="ops@fortimove.com"  # default: ops@fortimove.com
```
If not set: Handoff runs in `log_only` mode (no real emails sent)

### Database (Optional)
```bash
APPROVAL_QUEUE_DB_PATH="./approval_queue.db"  # default: ./approval_queue.db
```

---

## Recommended Deployment: Nginx + Let's Encrypt

### 1. Install dependencies
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx

# Install Python dependencies
pip install -r pm-agent/requirements.txt
```

### 2. Generate strong ADMIN_TOKEN
```bash
# Generate a 32-character random token
openssl rand -base64 32

# Example output: "8fK2jD+9xZ/pQ3vL1mN0oR4sT7uW6yA=="
# Save this token securely
```

### 3. Create systemd service
Create `/etc/systemd/system/fortimove-pm-agent.service`:

```ini
[Unit]
Description=Fortimove PM Agent Approval UI
After=network.target

[Service]
Type=simple
User=fortimove
WorkingDirectory=/home/fortimove/Fortimove-OS/pm-agent
Environment="ADMIN_TOKEN=YOUR_STRONG_TOKEN_HERE"
Environment="SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK"
Environment="SMTP_HOST=smtp.gmail.com"
Environment="SMTP_PORT=587"
Environment="SMTP_USER=ops@fortimove.com"
Environment="SMTP_PASS=your_app_password"
Environment="EMAIL_FROM=ops@fortimove.com"
Environment="EMAIL_TO=team@fortimove.com"
ExecStart=/usr/bin/uvicorn approval_ui_app:app --host 127.0.0.1 --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Note**: FastAPI listens on `127.0.0.1:8080` (localhost only), not exposed to internet directly.

### 4. Configure Nginx reverse proxy

Create `/etc/nginx/sites-available/fortimove-pm-agent`:

```nginx
server {
    listen 80;
    server_name pm-agent.fortimove.com;  # Your domain

    # Redirect all HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name pm-agent.fortimove.com;

    # SSL certificates (managed by certbot)
    ssl_certificate /etc/letsencrypt/live/pm-agent.fortimove.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/pm-agent.fortimove.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Proxy to FastAPI
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Access logs
    access_log /var/log/nginx/pm-agent-access.log;
    error_log /var/log/nginx/pm-agent-error.log;
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/fortimove-pm-agent /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 5. Obtain Let's Encrypt certificate
```bash
sudo certbot --nginx -d pm-agent.fortimove.com
```

Follow prompts. Certbot will automatically:
- Obtain SSL certificate
- Configure Nginx
- Set up auto-renewal

### 6. Start service
```bash
sudo systemctl daemon-reload
sudo systemctl enable fortimove-pm-agent
sudo systemctl start fortimove-pm-agent
sudo systemctl status fortimove-pm-agent
```

### 7. Verify deployment
```bash
# Check service is running
sudo systemctl status fortimove-pm-agent

# Check Nginx
sudo systemctl status nginx

# Test HTTPS endpoint
curl https://pm-agent.fortimove.com/health

# Test with auth (should fail without token)
curl https://pm-agent.fortimove.com/api/queue
# Expected: 401 Unauthorized

# Test with valid token
curl -H "X-API-TOKEN: YOUR_ADMIN_TOKEN" https://pm-agent.fortimove.com/api/queue
# Expected: 200 OK with queue items
```

---

## Alternative: Docker + Traefik

If using Docker with Traefik reverse proxy:

### docker-compose.yml
```yaml
version: '3.8'

services:
  pm-agent:
    build: ./pm-agent
    environment:
      - ADMIN_TOKEN=${ADMIN_TOKEN}
      - SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL}
      - SMTP_HOST=${SMTP_HOST}
      - SMTP_PORT=${SMTP_PORT}
      - SMTP_USER=${SMTP_USER}
      - SMTP_PASS=${SMTP_PASS}
      - EMAIL_FROM=${EMAIL_FROM}
      - EMAIL_TO=${EMAIL_TO}
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.pm-agent.rule=Host(`pm-agent.fortimove.com`)"
      - "traefik.http.routers.pm-agent.entrypoints=websecure"
      - "traefik.http.routers.pm-agent.tls.certresolver=letsencrypt"
      - "traefik.http.services.pm-agent.loadbalancer.server.port=8080"
    networks:
      - traefik-public
    volumes:
      - ./data:/app/data

networks:
  traefik-public:
    external: true
```

Traefik handles HTTPS automatically with Let's Encrypt.

---

## Smoke Test Checklist

After deployment, verify the following:

### ✅ HTTPS and Security
- [ ] Site is accessible via HTTPS
- [ ] HTTP automatically redirects to HTTPS
- [ ] Browser shows valid SSL certificate (no warnings)
- [ ] `curl http://...` redirects to `https://...`

### ✅ Authentication
- [ ] `/health` endpoint works without auth
- [ ] `/api/queue` returns 401 without token
- [ ] `/api/queue` with `X-API-TOKEN` header returns 200
- [ ] Wrong token returns 401
- [ ] UI can save token to localStorage

### ✅ Handoff Configuration
- [ ] Run `GET /api/handoff/verify` to check Slack/Email status
- [ ] Verify Slack shows `verified` or `not_verified` (not fake success)
- [ ] Verify Email shows `verified` or `not_verified` (not fake success)
- [ ] Check mode is `real_send` or `log_only` as expected

### ✅ Handoff Execution
- [ ] Run handoff with no approved items → returns `no_op`
- [ ] Run handoff with approved items → executes successfully
- [ ] Run handoff twice quickly → second returns 409 Conflict
- [ ] Check `/api/handoff/runs` shows current and recent runs
- [ ] Verify Slack message received (if configured)
- [ ] Verify Email received (if configured)

### ✅ Operational
- [ ] Systemd service auto-restarts on failure
- [ ] Nginx logs requests to `/var/log/nginx/pm-agent-*.log`
- [ ] No sensitive data (tokens, passwords) in logs
- [ ] Database persists across restarts

---

## Security Best Practices

### 1. Token Management
- ✅ Generate strong random tokens (≥32 chars)
- ✅ Use different tokens for staging and production
- ✅ Rotate tokens periodically (every 90 days recommended)
- ✅ Store tokens in systemd environment or secure secrets manager
- ❌ Never commit tokens to git
- ❌ Never share tokens in plain text (Slack, email)

### 2. HTTPS Configuration
- ✅ Use Let's Encrypt for free TLS certificates
- ✅ Enable HSTS (Strict-Transport-Security header)
- ✅ Set certificate auto-renewal
- ❌ Never use self-signed certs in production
- ❌ Never allow HTTP for authenticated endpoints

### 3. Reverse Proxy Hardening
- ✅ Set proper timeouts (60s recommended)
- ✅ Add security headers (X-Frame-Options, X-Content-Type-Options)
- ✅ Log all access for audit trail
- ✅ Use rate limiting if exposing to public

### 4. Operational
- ✅ Monitor systemd service status
- ✅ Set up log rotation for Nginx and app logs
- ✅ Backup SQLite database regularly
- ✅ Test disaster recovery procedure

---

## Troubleshooting

### Issue: 401 Unauthorized even with correct token
**Check**:
1. Token has no extra spaces or newlines
2. Token matches exactly (case-sensitive)
3. `ADMIN_TOKEN` env var is set in systemd service
4. Service restarted after env var change

### Issue: Handoff shows "log_only" but credentials are configured
**Check**:
1. `SLACK_WEBHOOK_URL` or `SMTP_HOST` is actually set
2. Run `GET /api/handoff/verify` to see real status
3. Check systemd service environment variables
4. Restart service after changing env vars

### Issue: Handoff fails with 409 Conflict
**Cause**: Another handoff is already running
**Solution**:
1. Wait for current run to complete (usually < 30 seconds)
2. Check `/api/handoff/runs` to see current run status
3. If stuck (>10 minutes), automatic stale lock recovery will trigger
4. Or manually reset by deleting running row from `handoff_runs` table

### Issue: Slack/Email verification fails
**Slack**:
- Check webhook URL is correct and active
- Test manually: `curl -X POST -H 'Content-Type: application/json' -d '{"text":"test"}' YOUR_WEBHOOK_URL`
- Check Slack app is not revoked

**Email**:
- Check SMTP host/port are correct
- Verify SMTP_USER and SMTP_PASS are correct
- For Gmail: Use App Password, not regular password
- Check firewall allows outbound port 587

---

## Monitoring and Maintenance

### Logs
```bash
# Application logs (stdout/stderr from uvicorn)
sudo journalctl -u fortimove-pm-agent -f

# Nginx access logs
sudo tail -f /var/log/nginx/pm-agent-access.log

# Nginx error logs
sudo tail -f /var/log/nginx/pm-agent-error.log
```

### Database Backup
```bash
# Backup SQLite database
cp /home/fortimove/Fortimove-OS/pm-agent/approval_queue.db \
   /home/fortimove/backups/approval_queue_$(date +%Y%m%d_%H%M%S).db

# Automated daily backup (cron)
0 2 * * * cp /home/fortimove/Fortimove-OS/pm-agent/approval_queue.db /home/fortimove/backups/approval_queue_$(date +\%Y\%m\%d).db
```

### Certificate Renewal
Certbot auto-renews certificates. Verify:
```bash
sudo certbot renew --dry-run
```

### Health Check
```bash
# Simple uptime monitoring
*/5 * * * * curl -f https://pm-agent.fortimove.com/health || echo "PM Agent is down!" | mail -s "Alert" ops@fortimove.com
```

---

## Next Steps After Deployment

1. **JWT Token Implementation** (recommended for production)
   - Add token expiration (24 hours)
   - Add refresh token flow
   - Add per-user tokens (instead of single admin token)

2. **Audit Logging**
   - Log all API calls with token ID
   - Track who did what and when
   - Export audit logs for compliance

3. **Advanced Monitoring**
   - Prometheus metrics export
   - Grafana dashboard
   - Alert on handoff failures

4. **Database Migration**
   - Move from SQLite to PostgreSQL for better concurrency
   - Required if multiple users access simultaneously

---

**Document maintained by**: Fortimove Engineering
**Support**: File issues at [GitHub repo]
**Security concerns**: Email security@fortimove.com
