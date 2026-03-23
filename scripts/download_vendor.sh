#!/usr/bin/env bash
# =============================================================================
# download_vendor.sh — CDN 라이브러리를 로컬 static/vendor/ 로 다운로드
# 인터넷 접속이 가능한 환경에서 한 번 실행하면 오프라인 배포 준비 완료.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENDOR_JS="$PROJECT_ROOT/static/vendor/js"
VENDOR_CSS="$PROJECT_ROOT/static/vendor/css"
STATIC_SRC="$PROJECT_ROOT/static/src"

mkdir -p "$VENDOR_JS" "$VENDOR_CSS" "$STATIC_SRC"

echo "=== Downloading JS vendor libraries ==="

echo "[1/5] HTMX v2.0.4 ..."
curl -sL "https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js" \
  -o "$VENDOR_JS/htmx.min.js"

echo "[2/5] Alpine.js v3.14.9 ..."
curl -sL "https://unpkg.com/alpinejs@3.14.9/dist/cdn.min.js" \
  -o "$VENDOR_JS/alpine.min.js"

echo "[3/5] Chart.js v4.4.7 ..."
curl -sL "https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js" \
  -o "$VENDOR_JS/chart.umd.min.js"

echo "[4/5] FullCalendar v6.1.15 ..."
curl -sL "https://cdn.jsdelivr.net/npm/fullcalendar@6.1.15/index.global.min.js" \
  -o "$VENDOR_JS/fullcalendar.global.min.js"

echo "[5/5] html5-qrcode v2.3.8 ..."
curl -sL "https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js" \
  -o "$VENDOR_JS/html5-qrcode.min.js"

echo ""
echo "=== Building Tailwind CSS ==="

# Detect OS and architecture for Tailwind standalone CLI
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"
case "$ARCH" in
  x86_64)  ARCH_SUFFIX="x64" ;;
  aarch64|arm64) ARCH_SUFFIX="arm64" ;;
  armv7l)  ARCH_SUFFIX="armv7" ;;
  *)       echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

case "$OS" in
  linux)  PLATFORM="linux" ;;
  darwin) PLATFORM="macos" ;;
  *)      echo "Unsupported OS: $OS"; exit 1 ;;
esac

TAILWIND_CLI="tailwindcss-${PLATFORM}-${ARCH_SUFFIX}"
TAILWIND_VERSION="v3.4.17"
TAILWIND_URL="https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/${TAILWIND_CLI}"

echo "Downloading Tailwind CLI (${TAILWIND_CLI}) ..."
curl -sL "$TAILWIND_URL" -o "$PROJECT_ROOT/$TAILWIND_CLI"
chmod +x "$PROJECT_ROOT/$TAILWIND_CLI"

echo "Building tailwind.min.css (scanning templates/**/*.html) ..."
"$PROJECT_ROOT/$TAILWIND_CLI" \
  -i "$STATIC_SRC/input.css" \
  -o "$VENDOR_CSS/tailwind.min.css" \
  --minify \
  --content "$PROJECT_ROOT/templates/**/*.html"

echo "Cleaning up Tailwind CLI binary ..."
rm -f "$PROJECT_ROOT/$TAILWIND_CLI"

echo ""
echo "=== Verification ==="
echo "JS files:"
for f in "$VENDOR_JS"/*.js; do
  SIZE=$(wc -c < "$f")
  NAME=$(basename "$f")
  if [ "$SIZE" -lt 100 ]; then
    echo "  WARNING: $NAME is only ${SIZE} bytes (likely a placeholder)"
  else
    echo "  OK: $NAME (${SIZE} bytes)"
  fi
done

echo "CSS files:"
for f in "$VENDOR_CSS"/*.css; do
  SIZE=$(wc -c < "$f")
  NAME=$(basename "$f")
  if [ "$SIZE" -lt 100 ]; then
    echo "  WARNING: $NAME is only ${SIZE} bytes (likely a placeholder)"
  else
    echo "  OK: $NAME (${SIZE} bytes)"
  fi
done

echo ""
echo "Done! All vendor files are in static/vendor/."
echo "The project can now run fully offline."
