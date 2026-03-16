# ERP Suite 배포 가이드

## 1. Docker Compose 배포

### 1.1 사전 요구사항

- Docker 20.10 이상
- Docker Compose v2 이상
- 최소 2GB RAM, 10GB 디스크

### 1.2 디렉토리 구조

```
/opt/erp-suite/
├── docker-compose.yml
├── .env                  # 환경변수 파일
├── nginx/
│   └── default.conf      # Nginx 설정
└── ssl/
    ├── fullchain.pem     # SSL 인증서
    └── privkey.pem       # SSL 개인키
```

### 1.3 환경변수 설정

`.env` 파일을 생성합니다:

```env
# Django 설정
SECRET_KEY=your-very-long-random-secret-key-here
DJANGO_SETTINGS_MODULE=config.settings.production
ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# 데이터베이스
DB_PASSWORD=your-secure-database-password

# 네이버 스마트스토어 API (선택)
NAVER_CLIENT_ID=your-naver-client-id
NAVER_CLIENT_SECRET=your-naver-client-secret

# Claude AI API (선택, 문의관리 AI 답변용)
ANTHROPIC_API_KEY=your-anthropic-api-key
```

> **주의:** `SECRET_KEY`는 50자 이상의 무작위 문자열을 사용하세요. 아래 명령으로 생성할 수 있습니다:
> ```bash
> python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
> ```

### 1.4 docker-compose.yml

프로젝트에 포함된 `docker-compose.yml` 기본 구성:

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

### 1.5 실행

```bash
# 컨테이너 빌드 및 백그라운드 실행
docker-compose up -d --build

# 데이터베이스 마이그레이션
docker-compose exec web python manage.py migrate

# 정적 파일 수집
docker-compose exec web python manage.py collectstatic --noinput

# 관리자 계정 생성
docker-compose exec web python manage.py createsuperuser

# 로그 확인
docker-compose logs -f web
```

### 1.6 업데이트

```bash
# 최신 코드 가져오기
git pull origin main

# 컨테이너 재빌드 및 재시작
docker-compose up -d --build

# 마이그레이션 적용
docker-compose exec web python manage.py migrate

# 정적 파일 재수집
docker-compose exec web python manage.py collectstatic --noinput
```

## 2. PostgreSQL 설정

### 2.1 Docker 사용 시 (권장)

`docker-compose.yml`에 포함된 PostgreSQL 16 Alpine 이미지를 사용합니다. 별도 설정이 필요 없습니다.

### 2.2 외부 PostgreSQL 사용 시

```bash
# PostgreSQL에 데이터베이스 및 사용자 생성
sudo -u postgres psql

CREATE DATABASE erp_suite ENCODING 'UTF8' LC_COLLATE 'ko_KR.UTF-8' LC_CTYPE 'ko_KR.UTF-8' TEMPLATE template0;
CREATE USER erp WITH PASSWORD 'your-password';
ALTER ROLE erp SET client_encoding TO 'utf8';
ALTER ROLE erp SET default_transaction_isolation TO 'read committed';
ALTER ROLE erp SET timezone TO 'Asia/Seoul';
GRANT ALL PRIVILEGES ON DATABASE erp_suite TO erp;
\q
```

환경변수에서 `DATABASE_URL`을 외부 서버 주소로 변경합니다:
```env
DATABASE_URL=postgres://erp:your-password@db-server-ip:5432/erp_suite
```

### 2.3 백업

```bash
# 데이터베이스 백업
docker-compose exec db pg_dump -U erp erp_suite > backup_$(date +%Y%m%d_%H%M%S).sql

# 복원
docker-compose exec -T db psql -U erp erp_suite < backup_20260316_120000.sql
```

## 3. 환경변수 설명

| 변수명 | 필수 | 기본값 | 설명 |
|--------|------|--------|------|
| `SECRET_KEY` | O | - | Django 시크릿 키 (50자 이상 권장) |
| `DJANGO_SETTINGS_MODULE` | O | `config.settings.production` | 사용할 설정 모듈 |
| `ALLOWED_HOSTS` | O | `localhost,127.0.0.1` | 허용 호스트 (쉼표 구분) |
| `DATABASE_URL` | O | - | PostgreSQL 연결 URL |
| `DB_PASSWORD` | O | `changeme` | PostgreSQL 비밀번호 |
| `NAVER_CLIENT_ID` | X | - | 네이버 API 클라이언트 ID |
| `NAVER_CLIENT_SECRET` | X | - | 네이버 API 클라이언트 시크릿 |
| `ANTHROPIC_API_KEY` | X | - | Claude AI API 키 |

## 4. Nginx 설정

### 4.1 Nginx 설정 파일

`nginx/default.conf`:

```nginx
upstream erp_backend {
    server web:8000;
}

server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    # HTTP를 HTTPS로 리다이렉트
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;

    # SSL 인증서
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    # SSL 보안 설정
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;

    # 보안 헤더
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

    # 업로드 최대 크기
    client_max_body_size 20M;

    # 정적 파일
    location /static/ {
        alias /app/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # 미디어 파일
    location /media/ {
        alias /app/media/;
        expires 7d;
    }

    # Django 애플리케이션
    location / {
        proxy_pass http://erp_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;

        # WebSocket 지원 (필요 시)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 4.2 docker-compose.yml에 Nginx 추가

```yaml
services:
  # ... 기존 db, web 서비스 ...

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

> Nginx를 사용하는 경우 `web` 서비스의 `ports: "8000:8000"`은 제거하거나 `expose: - "8000"`으로 변경하여 외부에서 직접 접근하지 못하도록 합니다.

## 5. SSL 인증서 설정

### 5.1 Let's Encrypt (무료, 권장)

```bash
# certbot 설치
sudo apt-get install certbot

# 인증서 발급 (Nginx 중지 후)
sudo certbot certonly --standalone -d your-domain.com -d www.your-domain.com

# 인증서 복사
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ./ssl/
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ./ssl/
```

### 5.2 자동 갱신

Let's Encrypt 인증서는 90일마다 갱신이 필요합니다. crontab에 자동 갱신을 등록합니다:

```bash
# crontab 편집
crontab -e

# 매월 1일 새벽 3시에 갱신 시도
0 3 1 * * certbot renew --quiet && cp /etc/letsencrypt/live/your-domain.com/fullchain.pem /opt/erp-suite/ssl/ && cp /etc/letsencrypt/live/your-domain.com/privkey.pem /opt/erp-suite/ssl/ && cd /opt/erp-suite && docker-compose restart nginx
```

## 6. 운영 체크리스트

배포 전 아래 항목을 확인하세요:

- [ ] `SECRET_KEY`를 무작위 문자열로 변경
- [ ] `DB_PASSWORD`를 안전한 비밀번호로 변경
- [ ] `ALLOWED_HOSTS`에 실제 도메인 설정
- [ ] `DEBUG = False` 확인 (production 설정 기본값)
- [ ] SSL 인증서 설정 완료
- [ ] 정적 파일 수집 (`collectstatic`) 완료
- [ ] 데이터베이스 마이그레이션 완료
- [ ] 관리자 계정 생성 완료
- [ ] 방화벽에서 80, 443 포트만 개방
- [ ] PostgreSQL 5432 포트는 외부 접근 차단
- [ ] 정기 백업 스케줄 설정
- [ ] 로그 모니터링 설정

## 7. 문제 해결

### 컨테이너 상태 확인
```bash
docker-compose ps
docker-compose logs web
docker-compose logs db
```

### 데이터베이스 연결 오류
```bash
# PostgreSQL 컨테이너가 정상 실행 중인지 확인
docker-compose exec db pg_isready -U erp

# 연결 테스트
docker-compose exec web python manage.py dbshell
```

### 정적 파일 404 오류
```bash
# 정적 파일 재수집
docker-compose exec web python manage.py collectstatic --noinput

# Nginx 재시작
docker-compose restart nginx
```

### 마이그레이션 오류
```bash
# 마이그레이션 상태 확인
docker-compose exec web python manage.py showmigrations

# 특정 앱 마이그레이션
docker-compose exec web python manage.py migrate inventory
```
