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
  sudo apt update && sudo apt install -y python3.12-venv
  echo "==> [2/3] إنشاء البيئة وتثبيت المكتبات..."
  python3.12 -m venv .venv
  source .venv/bin/activate
  pip install -r backend/requirements.txt
else
  echo "==> تفعيل البيئة الافتراضية..."
  source .venv/bin/activate
fi

# تشغيل السيرفر
echo "==> [3/3] تشغيل سيرفر MyPortMap..."
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
