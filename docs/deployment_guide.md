# ERP Suite Deployment Guide

## 1. Docker Compose Deployment

### 1.1 Prerequisites

- Docker 20.10 or higher
- Docker Compose v2 or higher
- Minimum 2GB RAM, 10GB disk

### 1.2 Directory Structure

```
/opt/erp-suite/
├── docker-compose.yml
├── .env                  # Environment variables file
├── nginx/
│   └── default.conf      # Nginx configuration
└── ssl/
    ├── fullchain.pem     # SSL certificate
    └── privkey.pem       # SSL private key
```

### 1.3 Environment Variables Setup

Create a `.env` file:

```env
# Django settings
SECRET_KEY=your-very-long-random-secret-key-here
DJANGO_SETTINGS_MODULE=config.settings.production
ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# Database
DB_PASSWORD=your-secure-database-password

# Naver Smart Store API (optional)
NAVER_CLIENT_ID=your-naver-client-id
NAVER_CLIENT_SECRET=your-naver-client-secret

# Claude AI API (optional, for inquiry management AI responses)
ANTHROPIC_API_KEY=your-anthropic-api-key
```

> **Warning:** Use a random string of 50 characters or more for `SECRET_KEY`. You can generate one with the following command:
> ```bash
> python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
> ```

### 1.4 docker-compose.yml

Default configuration included in the project's `docker-compose.yml`:

```yaml
services:
  db:
    image: postgres:16-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: erp_suite
      POSTGRES_USER: erp
      POSTGRES_PASSWORD: ${DB_PASSWORD:-changeme}
    ports:
      - "5432:5432"
    restart: unless-stopped

  web:
    build: .
    command: gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
    volumes:
      - static_files:/app/staticfiles
      - media_files:/app/media
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgres://erp:${DB_PASSWORD:-changeme}@db:5432/erp_suite
      - SECRET_KEY=${SECRET_KEY:-change-this-in-production}
      - ALLOWED_HOSTS=${ALLOWED_HOSTS:-localhost,127.0.0.1}
      - DJANGO_SETTINGS_MODULE=config.settings.production
    depends_on:
      - db
    restart: unless-stopped

volumes:
  postgres_data:
  static_files:
  media_files:
```

### 1.5 Running

```bash
# Build containers and run in background
docker-compose up -d --build

# Run database migrations
docker-compose exec web python manage.py migrate

# Collect static files
docker-compose exec web python manage.py collectstatic --noinput

# Create admin account
docker-compose exec web python manage.py createsuperuser

# View logs
docker-compose logs -f web
```

### 1.6 Updating

```bash
# Pull latest code
git pull origin main

# Rebuild and restart containers
docker-compose up -d --build

# Apply migrations
docker-compose exec web python manage.py migrate

# Re-collect static files
docker-compose exec web python manage.py collectstatic --noinput
```

## 2. PostgreSQL Configuration

### 2.1 Using Docker (Recommended)

Uses the PostgreSQL 16 Alpine image included in `docker-compose.yml`. No additional configuration is required.

### 2.2 Using an External PostgreSQL

```bash
# Create database and user in PostgreSQL
sudo -u postgres psql

CREATE DATABASE erp_suite ENCODING 'UTF8' LC_COLLATE 'ko_KR.UTF-8' LC_CTYPE 'ko_KR.UTF-8' TEMPLATE template0;
CREATE USER erp WITH PASSWORD 'your-password';
ALTER ROLE erp SET client_encoding TO 'utf8';
ALTER ROLE erp SET default_transaction_isolation TO 'read committed';
ALTER ROLE erp SET timezone TO 'Asia/Seoul';
GRANT ALL PRIVILEGES ON DATABASE erp_suite TO erp;
\q
```

Change the `DATABASE_URL` in environment variables to your external server address:
```env
DATABASE_URL=postgres://erp:your-password@db-server-ip:5432/erp_suite
```

### 2.3 Backup

```bash
# Database backup
docker-compose exec db pg_dump -U erp erp_suite > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore
docker-compose exec -T db psql -U erp erp_suite < backup_20260316_120000.sql
```

## 3. Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes | - | Django secret key (50+ characters recommended) |
| `DJANGO_SETTINGS_MODULE` | Yes | `config.settings.production` | Settings module to use |
| `ALLOWED_HOSTS` | Yes | `localhost,127.0.0.1` | Allowed hosts (comma-separated) |
| `DATABASE_URL` | Yes | - | PostgreSQL connection URL |
| `DB_PASSWORD` | Yes | `changeme` | PostgreSQL password |
| `NAVER_CLIENT_ID` | No | - | Naver API client ID |
| `NAVER_CLIENT_SECRET` | No | - | Naver API client secret |
| `ANTHROPIC_API_KEY` | No | - | Claude AI API key |

## 4. Nginx Configuration

### 4.1 Nginx Configuration File

`nginx/default.conf`:

```nginx
upstream erp_backend {
    server web:8000;
}

server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;

    # SSL certificate
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    # SSL security settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;

    # Security headers
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

    # Maximum upload size
    client_max_body_size 20M;

    # Static files
    location /static/ {
        alias /app/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias /app/media/;
        expires 7d;
    }

    # Django application
    location / {
        proxy_pass http://erp_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;

        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 4.2 Adding Nginx to docker-compose.yml

```yaml
services:
  # ... existing db, web services ...

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf
      - ./ssl:/etc/nginx/ssl:ro
      - static_files:/app/staticfiles:ro
      - media_files:/app/media:ro
    depends_on:
      - web
    restart: unless-stopped
```

> When using Nginx, remove `ports: "8000:8000"` from the `web` service or change it to `expose: - "8000"` to prevent direct external access.

## 5. SSL Certificate Setup

### 5.1 Let's Encrypt (Free, Recommended)

```bash
# Install certbot
sudo apt-get install certbot

# Issue certificate (after stopping Nginx)
sudo certbot certonly --standalone -d your-domain.com -d www.your-domain.com

# Copy certificates
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ./ssl/
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ./ssl/
```

### 5.2 Automatic Renewal

Let's Encrypt certificates need to be renewed every 90 days. Register automatic renewal in crontab:

```bash
# Edit crontab
crontab -e

# Attempt renewal at 3 AM on the 1st of every month
0 3 1 * * certbot renew --quiet && cp /etc/letsencrypt/live/your-domain.com/fullchain.pem /opt/erp-suite/ssl/ && cp /etc/letsencrypt/live/your-domain.com/privkey.pem /opt/erp-suite/ssl/ && cd /opt/erp-suite && docker-compose restart nginx
```

## 6. Production Checklist

Verify the following items before deployment:

- [ ] Changed `SECRET_KEY` to a random string
- [ ] Changed `DB_PASSWORD` to a secure password
- [ ] Set `ALLOWED_HOSTS` to the actual domain
- [ ] Confirmed `DEBUG = False` (default in production settings)
- [ ] SSL certificate setup completed
- [ ] Static file collection (`collectstatic`) completed
- [ ] Database migrations completed
- [ ] Admin account created
- [ ] Firewall allows only ports 80 and 443
- [ ] PostgreSQL port 5432 is blocked from external access
- [ ] Scheduled backup configured
- [ ] Log monitoring configured

## 7. Troubleshooting

### Checking Container Status
```bash
docker-compose ps
docker-compose logs web
docker-compose logs db
```

### Database Connection Errors
```bash
# Check if the PostgreSQL container is running properly
docker-compose exec db pg_isready -U erp

# Test connection
docker-compose exec web python manage.py dbshell
```

### Static File 404 Errors
```bash
# Re-collect static files
docker-compose exec web python manage.py collectstatic --noinput

# Restart Nginx
docker-compose restart nginx
```

### Migration Errors
```bash
# Check migration status
docker-compose exec web python manage.py showmigrations

# Migrate a specific app
docker-compose exec web python manage.py migrate inventory
```
