#!/bin/bash
set -e

# الانتقال لمجلد المشروع
if [ -d "/workspaces/myportmap" ]; then
  cd /workspaces/myportmap
else
  cd "$(dirname "$0")"
fi

# فحص وتجهيز البيئة
if [ ! -f ".venv/bin/activate" ]; then
  echo "==> [1/3] تثبيت حزم النظام..."
  sudo apt update && sudo apt install -y python3.12-venv curl
  echo "==> [2/3] إنشاء البيئة وتثبيت المكتبات..."
  python3.12 -m venv .venv
  source .venv/bin/activate
  pip install -r backend/requirements.txt
else
  echo "==> تفعيل البيئة الافتراضية..."
  source .venv/bin/activate
fi

# كشف الـ IP العام تلقائياً إذا لم يكن معرّفاً
if [ -z "${VPN_PUBLIC_IP:-}" ]; then
  DETECTED_IP=$(curl -s --connect-timeout 2 https://api.ipify.org 2>/dev/null || curl -s --connect-timeout 2 https://ifconfig.me/ip 2>/dev/null || echo "127.0.0.1")
  if [ -n "$DETECTED_IP" ] && [ "$DETECTED_IP" != "127.0.0.1" ]; then
    export VPN_PUBLIC_IP="$DETECTED_IP"
  fi
fi

echo "=========================================================="
echo " ==> Public IP المعتمد للسيرفر: ${VPN_PUBLIC_IP:-127.0.0.1}"
echo " ==> تشغيل سيرفر MyPortMap على 0.0.0.0:8000..."
echo "=========================================================="

# حلقة Keep-Alive في الخلفية لمنع إيقاف Codespace أثناء تشغيل السيرفر
(while true; do sleep 60; touch /tmp/.codespaces_keepalive 2>/dev/null || true; done) &
KEEPALIVE_PID=$!
trap "kill $KEEPALIVE_PID 2>/dev/null || true" EXIT

# تشغيل السيرفر
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000

