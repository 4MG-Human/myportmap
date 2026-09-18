#!/usr/bin/env bash
# الاستخدام: create_client.sh <common_name>
# ينشئ طلب شهادة عميل جديد ويوقّعه تلقائيًا (بدون كلمة مرور على المفتاح).
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "usage: create_client.sh <common_name>" >&2
  exit 1
fi

CN="$1"

# تحقق صارم من الاسم لمنع أي حقن أوامر حتى لو استُدعي هذا السكربت يدويًا
if ! [[ "$CN" =~ ^[a-zA-Z0-9_-]{1,64}$ ]]; then
  echo "invalid common name" >&2
  exit 1
fi

EASYRSA_DIR="/etc/openvpn/easy-rsa"
cd "$EASYRSA_DIR"

# إن كانت الشهادة موجودة مسبقًا لا تُنشئها من جديد
if [ -f "pki/issued/${CN}.crt" ]; then
  echo "certificate for $CN already exists"
  exit 0
fi

export EASYRSA_BATCH=1
./easyrsa gen-req "$CN" nopass
./easyrsa sign-req client "$CN"

# إعطاء صلاحية القراءة لمجموعة myportmap
chmod 640 "pki/private/${CN}.key"
chgrp myportmap "pki/private/${CN}.key" 2>/dev/null || true

echo "client certificate created for $CN"
