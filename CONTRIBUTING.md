# Contributing to ERP Suite

**English** | [한국어](docs/CONTRIBUTING.ko.md)

Thanks for your interest in contributing to ERP Suite.

## Development Setup

### Prerequisites
- Python 3.13+
- pip

### Build
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

### Test
```bash
python manage.py test apps/ -v 0 --parallel
python manage.py test tests.verification -v 0
ruff check apps/ config/ --select E,F,W --ignore E501,F401,E402
```

## Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-change`
3. Commit with Conventional Commits style
4. Push and open a Pull Request

## Pull Request Checklist

- [ ] The change has a clear scope and rationale
- [ ] Tests are added/updated where applicable
- [ ] `python manage.py test apps/ -v 0 --parallel` passes
- [ ] `ruff check` passes
- [ ] No missing migrations (`python manage.py makemigrations --check --dry-run`)
- [ ] README / docs are updated when behavior changes

## Commit Message Convention

Use [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation changes
- `refactor:` for internal improvements without behavior changes
- `test:` for test updates
- `chore:` for maintenance tasks

## Security

For security issues, follow the process in [SECURITY.md](SECURITY.md).
