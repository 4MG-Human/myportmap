#!/usr/bin/env bash
# ==========================================================================
# MyPortMap - سكربت تجهيز الـVPS من الصفر (Ubuntu 22.04 / 24.04)
# نفّذه مرة واحدة بعد رفع المشروع إلى السيرفر:
#   sudo bash scripts/00_setup_server.sh
# ==========================================================================
set -euo pipefail

PROJECT_DIR="/opt/myportmap"
APP_USER="myportmap"
VPN_SUBNET="10.8.0.0"
VPN_MASK="255.255.255.0"
VPN_PORT="1194"
NFT_TABLE="myportmap"

echo "==> [1/10] تحديث النظام وتثبيت الحزم"
apt update
apt upgrade -y
apt install -y openvpn easy-rsa nftables nginx python3-venv python3-pip \
               git curl certbot python3-certbot-nginx

echo "==> [2/10] إنشاء مستخدم النظام لتشغيل الخدمة"
if ! id "$APP_USER" &>/dev/null; then
  useradd --system --no-create-home --shell /usr/sbin/nologin "$APP_USER"
fi

echo "==> [3/10] تجهيز PKI عبر easy-rsa"
mkdir -p /etc/openvpn/easy-rsa
cp -r /usr/share/easy-rsa/* /etc/openvpn/easy-rsa/
cd /etc/openvpn/easy-rsa

export EASYRSA_BATCH=1
if [ ! -d pki ]; then
  ./easyrsa init-pki
  ./easyrsa build-ca nopass
  ./easyrsa gen-req server nopass
  ./easyrsa sign-req server server
  ./easyrsa gen-dh
  openvpn --genkey secret /etc/openvpn/easy-rsa/pki/ta.key
fi

echo "==> [4/10] نسخ شهادات السيرفر إلى /etc/openvpn/server"
mkdir -p /etc/openvpn/server
cp pki/ca.crt /etc/openvpn/server/
cp pki/issued/server.crt /etc/openvpn/server/
cp pki/private/server.key /etc/openvpn/server/
cp pki/dh.pem /etc/openvpn/server/
cp pki/ta.key /etc/openvpn/server/
chmod 600 /etc/openvpn/server/server.key /etc/openvpn/server/ta.key

echo "==> [5/10] كتابة server.conf وتجهيز مجلد CCD لتثبيت عناوين الـIP"
mkdir -p /etc/openvpn/ccd
chown -R "${APP_USER}:${APP_USER}" /etc/openvpn/ccd
chmod 775 /etc/openvpn/ccd

cat > /etc/openvpn/server/server.conf <<EOF
port ${VPN_PORT}
proto udp
dev tun

topology subnet
server ${VPN_SUBNET} ${VPN_MASK}
client-config-dir /etc/openvpn/ccd

ca /etc/openvpn/server/ca.crt
cert /etc/openvpn/server/server.crt
key /etc/openvpn/server/server.key
dh /etc/openvpn/server/dh.pem
tls-crypt /etc/openvpn/server/ta.key

cipher AES-256-GCM
auth SHA256

keepalive 10 120
persist-key
persist-tun

user nobody
group nogroup

status /var/log/openvpn-status.log
verb 3
EOF

# ضبط صلاحيات القراءة للتطبيق
touch /var/log/openvpn-status.log
chmod 644 /var/log/openvpn-status.log
chmod 644 /etc/openvpn/server/ta.key
chmod 755 /etc/openvpn/easy-rsa/pki
chmod 755 /etc/openvpn/easy-rsa/pki/issued
chmod 750 /etc/openvpn/easy-rsa/pki/private
chgrp "${APP_USER}" /etc/openvpn/easy-rsa/pki/private 2>/dev/null || true

systemctl enable openvpn-server@server
systemctl restart openvpn-server@server

echo "==> [6/10] تفعيل IP forwarding بشكل دائم"
if ! grep -q "net.ipv4.ip_forward=1" /etc/sysctl.conf; then
  echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
fi
sysctl -p

echo "==> [7/10] تجهيز جدول nftables الأساسي"
mkdir -p /etc/nftables.d
cat > /etc/nftables.conf <<EOF
#!/usr/sbin/nft -f

flush ruleset

table ip ${NFT_TABLE} {
    chain prerouting {
        type nat hook prerouting priority -100;
    }
    chain postrouting {
        type nat hook postrouting priority 100;
        oifname != "tun0" ip saddr ${VPN_SUBNET%.*}.0/24 masquerade
    }
    chain forward {
        type filter hook forward priority 0; policy drop;
        ct state established,related accept
        ip saddr ${VPN_SUBNET%.*}.0/24 accept
    }
}

table inet filter {
    chain input {
        type filter hook input priority 0; policy drop;
        ct state established,related accept
        iif "lo" accept
        icmp type echo-request accept
        tcp dport 22 accept
        udp dport ${VPN_PORT} accept
        tcp dport { 80, 443 } accept
    }
}
EOF

systemctl enable nftables
nft -f /etc/nftables.conf

echo "==> [8/10] السماح للتطبيق بتشغيل nft وسكربت إنشاء العملاء بدون كلمة مرور"
cat > /etc/sudoers.d/myportmap <<EOF
${APP_USER} ALL=(root) NOPASSWD: /usr/sbin/nft
${APP_USER} ALL=(root) NOPASSWD: ${PROJECT_DIR}/scripts/create_client.sh
EOF
chmod 440 /etc/sudoers.d/myportmap
chmod +x "${PROJECT_DIR}/scripts/create_client.sh"

echo "==> [9/10] تجهيز بيئة بايثون والتطبيق"
mkdir -p "${PROJECT_DIR}/data"
python3 -m venv "${PROJECT_DIR}/venv"
"${PROJECT_DIR}/venv/bin/pip" install --upgrade pip
"${PROJECT_DIR}/venv/bin/pip" install -r "${PROJECT_DIR}/backend/requirements.txt"
chown -R "${APP_USER}:${APP_USER}" "${PROJECT_DIR}"

cat > /etc/systemd/system/myportmap.service <<EOF
[Unit]
Description=MyPortMap FastAPI backend
After=network.target

[Service]
User=${APP_USER}
WorkingDirectory=${PROJECT_DIR}/backend
EnvironmentFile=${PROJECT_DIR}/.env
ExecStart=${PROJECT_DIR}/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable myportmap
systemctl restart myportmap

echo "==> [10/10] إعداد Nginx كـreverse proxy"
cat > /etc/nginx/sites-available/myportmap <<EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF
ln -sf /etc/nginx/sites-available/myportmap /etc/nginx/sites-enabled/myportmap
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

echo ""
echo "=========================================================="
echo " تم الإعداد. تحقق من الحالة:"
echo "   sudo systemctl status openvpn-server@server"
echo "   sudo systemctl status myportmap"
echo "   sudo systemctl status nginx"
echo " الموقع متاح الآن على: http://<VPS_PUBLIC_IP>/"
echo "=========================================================="
