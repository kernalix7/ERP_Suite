# ERP Suite 기여 가이드

[English](../CONTRIBUTING.md) | **한국어**

ERP Suite에 기여해 주셔서 감사합니다.

## 개발 환경 준비

### 사전 요구사항
- Python 3.13+
- pip

### 빌드
```bash
git clone https://github.com/kernalix7/ERP_Suite.git
cd ERP_Suite
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements/base.txt
bash scripts/download_vendor.sh
mkdir -p local && cp .env.example local/.env
python manage.py migrate
```

### 테스트
```bash
python manage.py test apps/ -v 0 --parallel
python manage.py test tests.verification -v 0
ruff check apps/ config/ --select E,F,W --ignore E501,F401,E402
```

## 작업 흐름

1. 저장소를 Fork 합니다
2. 기능 브랜치를 생성합니다: `git checkout -b feature/my-change`
3. Conventional Commits 스타일로 커밋합니다
4. Push 후 Pull Request를 생성합니다

## Pull Request 체크리스트

- [ ] 변경 범위와 목적이 명확한가?
- [ ] 필요한 테스트를 추가/갱신했는가?
- [ ] `python manage.py test apps/ -v 0 --parallel` 통과하는가?
- [ ] `ruff check` 통과하는가?
- [ ] 누락된 마이그레이션이 없는가? (`python manage.py makemigrations --check --dry-run`)
- [ ] 동작 변경 시 README/문서를 갱신했는가?

## 커밋 메시지 규칙

[Conventional Commits](https://www.conventionalcommits.org/)를 사용합니다:
- `feat:` 새 기능
- `fix:` 버그 수정
- `docs:` 문서 변경
- `refactor:` 동작 변경 없는 구조 개선
- `test:` 테스트 변경
- `chore:` 유지보수 작업

## 보안

보안 이슈는 [SECURITY.ko.md](SECURITY.ko.md)의 제보 절차를 따라 주세요.
