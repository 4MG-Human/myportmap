# MyPortMap — دليل التنفيذ الكامل من الصفر حتى التشغيل

هذا الدليل يفترض أنك بدأت من **لا شيء**: لا حساب سحابي، لا سيرفر، لا كود. اتبع الأرقام بالترتيب. كل خطوة فيها إما "افتح موقعًا ونفّذ كذا بالماوس" أو أوامر تُنسخ وتُلصق كما هي.

---

## 0) على أي جهاز أعمل هذا؟ (الجواب المباشر على سؤالك)

يوجد **جهازان مختلفان تمامًا** في هذا المشروع، ولا تخلط بينهما:

| الجهاز | ما هو | نظام التشغيل المطلوب |
|---|---|---|
| **الـVPS (السيرفر)** | جهاز افتراضي في Oracle Cloud، هو "MyPortMap" نفسه | **Ubuntu Server 22.04 أو 24.04** — إلزامي، لأن كل أوامر هذا الدليل (`apt`, `systemctl`, `nft`...) مكتوبة لأوبنتو |
| **جهازك الشخصي (العميل خلف NAT)** | اللابتوب الذي تشغّل عليه الخدمة المحلية وتتصل عبره بالـVPN | **أي نظام تريده**: Windows, macOS, Ubuntu, Linux Mint، أو **نعم، Kali Linux تمامًا مثله** |

Kali Linux توزيعة مبنية على Debian، ونفس أمر `sudo apt install openvpn` يعمل عليها بلا أي فرق. لا تحتاج Kali تحديدًا (هي موجّهة لاختبار الاختراق، وليست ضرورية هنا)، لكن إذا كانت هي نظامك الحالي فاستخدمها بلا قلق — لن تواجه أي مشكلة في هذا المشروع.

**الخلاصة: الـVPS = Ubuntu حصرًا. جهازك = أي شيء، بما فيه Kali.**

---

## 1) إنشاء حساب Oracle Cloud (مجاني)

1. افتح: **https://www.oracle.com/cloud/free/**
2. اضغط **Start for free**
3. سجّل بريدك الإلكتروني، ثم أكمل البيانات (الاسم، الدولة، رقم الهاتف للتحقق عبر SMS)
4. سيطلب منك **بطاقة بنكية للتحقق فقط** (لن يُخصم منها شيء طالما بقيت ضمن Always Free)
5. بعد التفعيل تدخل إلى **OCI Console** (لوحة التحكم)

> إذا رفض حسابك أو لم تتوفر سعة Always Free في منطقتك، البديل: Google Cloud Free Tier (`https://cloud.google.com/free`) أو AWS Free Tier (`https://aws.amazon.com/free/`) — نفس الخطوات لاحقًا تُطبَّق بعد اختيار Ubuntu كنظام.

---

## 2) إنشاء الـVPS

داخل OCI Console:

```
Menu (☰) → Compute → Instances → Create Instance
```

اضبط:

| الحقل | القيمة |
|---|---|
| Name | `myportmap-vps` |
| Image | **Canonical Ubuntu** → اختر **24.04** (أو 22.04) |
| Shape | `VM.Standard.A1.Flex` (ضمن Always Free) — اضبط OCPU=1, RAM=6GB |
| Add SSH keys | اختر **Generate a key pair for me** ثم اضغط **Save private key** (سيُحمَّل ملف مثل `ssh-key-...key`) |
| Networking | اترك الإعداد الافتراضي، وتأكد أن **Assign a public IPv4 address = Yes** |

اضغط **Create**. انتظر حتى تصبح الحالة **RUNNING**.

انسخ **Public IP Address** الظاهر في صفحة الـInstance — ستحتاجه في كل خطوة لاحقة. سمِّه من الآن:

```
VPS_IP = <ضع هنا العنوان الذي ظهر لك>
```

---

## 3) فتح المنافذ من شبكة Oracle (Security List)

Oracle تحجب المنافذ من طبقة الشبكة قبل حتى وصولها لجدار حماية أوبنتو، فيجب فتحها هنا أولًا:

```
Instance page → Virtual Cloud Network (اضغط اسم الـVCN)
→ Security Lists → Default Security List
→ Add Ingress Rules
```

أضف القواعد التالية (كل واحدة Ingress Rule منفصلة، Source CIDR = `0.0.0.0/0`):

| Protocol | Port Range |
|---|---|
| TCP | 22 |
| UDP | 1194 |
| TCP | 80 |
| TCP | 443 |
| TCP | 40000-50000 |
| UDP | 40000-50000 |

> نطاق `40000-50000` هو نطاق المنافذ العامة التي سيوزّعها MyPortMap تلقائيًا لكل Mapping يُنشئه المستخدمون.

---

## 4) الاتصال بالسيرفر عبر SSH

على جهازك، انقل مفتاح SSH الذي حمّلته إلى مكان آمن واضبط صلاحياته:

```bash
chmod 600 ~/Downloads/ssh-key-*.key
ssh -i ~/Downloads/ssh-key-*.key ubuntu@VPS_IP
```

(استبدل `VPS_IP` بالعنوان الحقيقي). عند أول اتصال اكتب `yes` لقبول البصمة.

تحقق من النظام:

```bash
uname -a
lsb_release -a
```

---

## 5) رفع المشروع إلى السيرفر

من جهازك (وليس من داخل SSH)، انسخ مجلد المشروع كاملًا إلى السيرفر عبر `scp`:

```bash
scp -i ~/Downloads/ssh-key-*.key -r ./myportmap ubuntu@VPS_IP:/home/ubuntu/
```

ثم عد إلى جلسة SSH داخل السيرفر:

```bash
sudo mv /home/ubuntu/myportmap /opt/myportmap
cd /opt/myportmap
cp .env.example .env
```

افتح `.env` وعدّل القيم الأهم:

```bash
sudo nano .env
```

غيّر على الأقل:

```
SECRET_KEY=              ← ضع نصًا عشوائيًا طويلًا
VPN_PUBLIC_IP=VPS_IP      ← ضع IP السيرفر الحقيقي
```

احفظ (`Ctrl+O` ثم `Enter`) واخرج (`Ctrl+X`).

---

## 6) تشغيل سكربت التجهيز الكامل (خطوة واحدة تُنفّذ كل شيء)

هذا السكربت يُثبّت OpenVPN وEasy-RSA وnftables وNginx وPython، وينشئ الشهادات، ويفعّل كل الخدمات:

```bash
sudo bash scripts/00_setup_server.sh
```

سيطبع في النهاية رسالة تأكيد. تحقق يدويًا:

```bash
sudo systemctl status openvpn-server@server
sudo systemctl status myportmap
sudo systemctl status nginx
```

الثلاثة يجب أن تظهر **active (running)**.

افتح في المتصفح:

```
http://VPS_IP/
```

يجب أن تظهر صفحة MyPortMap الرئيسية. **هذا يعني أن الملفات التالية أُنشئت تلقائيًا على السيرفر:**

```
/etc/openvpn/easy-rsa/pki/...        ← الشهادات (CA, server, dh, ta.key)
/etc/openvpn/server/server.conf      ← إعداد سيرفر الـVPN
/etc/nftables.conf                   ← قواعد الجدار الناري وNAT
/etc/systemd/system/myportmap.service← خدمة تشغيل الـBackend
/etc/nginx/sites-available/myportmap ← إعداد الـreverse proxy
/opt/myportmap/venv/                 ← بيئة بايثون المعزولة مع كل المكتبات
/opt/myportmap/data/myportmap.db     ← قاعدة بيانات SQLite (تُنشأ عند أول تشغيل)
```

---

## 7) إنشاء حساب واختبار الموقع

من المتصفح على `http://VPS_IP/`:

1. اضغط **إنشاء حساب** → أدخل بريدًا وكلمة مرور (8 أحرف فأكثر) → Create Account
2. سيرجعك إلى صفحة **تسجيل الدخول** → سجّل بنفس البيانات
3. ستدخل إلى **Dashboard**

اضغط **"إنشاء / عرض عميل VPN"**. هذا الزر ينفّذ خلف الكواليس:

```
POST /api/vpn/client
   → يُنشئ شهادة العميل عبر scripts/create_client.sh
   → يُخصص لك IP داخل شبكة الـVPN (مثال: 10.8.0.2)
   → يحفظ السجل في قاعدة البيانات
```

اضغط **"Download .OVPN"** — سيُحمَّل ملف `myportmap-client.ovpn` على جهازك.

---

## 8) توصيل جهازك بالـVPN (Phase العميل — على جهازك أنت، Kali أو غيره)

على **جهازك** (Windows / macOS / Ubuntu / Kali — لا فرق):

### Linux / Kali:
```bash
sudo apt install -y openvpn
sudo openvpn --config ~/Downloads/myportmap-client.ovpn
```
اترك هذا الطرفية مفتوحة (الاتصال يبقى قائمًا طالما هي شغّالة).

### Windows:
حمّل **OpenVPN Connect** من `https://openvpn.net/client/`، ثم استورد ملف `myportmap-client.ovpn` واضغط Connect.

### تحقق من الاتصال (على جهازك، في نافذة ثانية):
```bash
ip addr     # Linux/Kali — ابحث عن واجهة tun0 وعنوان مثل 10.8.0.2
```
على Windows: `ipconfig` وابحث عن TAP-Windows Adapter.

ارجع إلى صفحة الـDashboard في المتصفح — يجب أن تتحول حالة VPN CLIENT إلى **CONNECTED** خلال ثوانٍ (يفحص الموقع ملف `/var/log/openvpn-status.log` على السيرفر).

---

## 9) تشغيل خدمة تجريبية محلية على جهازك

على نفس جهازك (العميل)، افتح طرفية جديدة وشغّل خادمًا بسيطًا:

```bash
python3 -m http.server 8080 --bind 0.0.0.0
```

هذه الخدمة تستمع الآن على المنفذ `8080` على عنوان الـVPN الخاص بك (`10.8.0.2` مثلًا).

---

## 10) إنشاء أول Port Mapping من الـDashboard

في المتصفح، داخل قسم **PORT MAPPINGS**:

```
Protocol: TCP
Local Port: 8080
→ اضغط "+ CREATE MAPPING"
```

خلف الكواليس ينفّذ الـBackend:

```
اختيار منفذ عام غير مستخدم من نطاق 40000-50000
        ↓
إضافة قاعدة nftables (DNAT):
  VPS_IP:<external_port>  →  10.8.0.2:8080
        ↓
حفظ السجل في قاعدة البيانات
        ↓
عرض النتيجة في الواجهة
```

ستظهر لك النتيجة مباشرة، مثلًا:

```
TCP   VPS_IP:45213 → local:8080
```

---

## 11) الاختبار النهائي من جهاز خارجي (الإثبات الحقيقي للمشروع)

من **أي جهاز آخر متصل بالإنترنت** (ليس جهازك، وليس السيرفر) — مثلًا جوالك عبر بيانات الجوال، أو جهاز صديق:

```
افتح في المتصفح أو نفّذ:
curl http://VPS_IP:45213
```

(استبدل الرقم بالمنفذ الذي ظهر لك فعليًا في الخطوة السابقة)

إذا ظهرت لك صفحة الملفات التي يعرضها `python3 -m http.server` — **نجح المشروع بالكامل**:

```
Internet (جهاز خارجي)
   → VPS_IP:45213
   → nftables DNAT
   → 10.8.0.2:8080 (عبر نفق الـVPN)
   → جهازك خلف الـNAT
   → الخدمة المحلية
```

---

## 12) التحقق عند حدوث مشكلة

| العرض | أمر التشخيص |
|---|---|
| OpenVPN لا يعمل | `sudo systemctl status openvpn-server@server` ثم `sudo journalctl -u openvpn-server@server -n 50` |
| العميل متصل لكن VPN IP لا يظهر | تأكد أن الـVCN فتحت UDP 1194 فعليًا (خطوة 3) |
| الـMapping أُنشئ لكن لا يستجيب من الخارج | `sudo nft list ruleset` تحقق من وجود قاعدة DNAT، و`sudo ss -lntup` على جهازك تحقق أن `python3 -m http.server` يستمع على `0.0.0.0` وليس `127.0.0.1` |
| خطأ 500 عند إنشاء Mapping | `sudo journalctl -u myportmap -n 50` لعرض خطأ الـBackend |
| الموقع لا يفتح إطلاقًا | `sudo systemctl status nginx` و`curl http://127.0.0.1:8000/api/health` من داخل السيرفر |

---

## 13) ملاحظات أمان قبل أي استخدام جدي

- عطّل تسجيل الدخول بكلمة مرور عبر SSH واعتمد المفاتيح فقط:
  ```bash
  sudo nano /etc/ssh/sshd_config
  # PasswordAuthentication no
  sudo systemctl restart ssh
  ```
- غيّر `SECRET_KEY` في `.env` إلى قيمة عشوائية طويلة فعليًا قبل أي استخدام حقيقي.
- عند إضافة Domain لاحقًا، فعّل HTTPS عبر:
  ```bash
  sudo certbot --nginx -d yourdomain.com
  ```
- هذا الكود MVP تعليمي/تجريبي: قبل فتحه لعموم الناس راجع Rate Limiting وQuotas وRevoke للشهادات (مذكورة كخطوات تالية في نهاية هذا الملف).

---

## 14) هيكل المشروع الكامل (كل ملف وماذا يفعل)

```
myportmap/
├── README.md                          ← هذا الدليل
├── .env.example                       ← نموذج الإعدادات (يُنسخ إلى .env على السيرفر)
│
├── backend/
│   ├── requirements.txt               ← مكتبات بايثون المطلوبة
│   ├── config.py                      ← قراءة الإعدادات من .env
│   ├── database.py                    ← اتصال SQLAlchemy + SQLite
│   ├── models.py                      ← جداول: users, vpn_clients, mappings
│   ├── schemas.py                     ← Pydantic schemas للـAPI
│   ├── security.py                    ← تشفير كلمات المرور + JWT
│   ├── vpn_certs.py                   ← توليد شهادات وملفات .ovpn
│   ├── firewall.py                    ← إضافة/حذف قواعد nftables (DNAT)
│   ├── main.py                        ← نقطة تشغيل FastAPI
│   └── routers/
│       ├── auth.py                    ← /api/auth/register /login
│       ├── vpn.py                     ← /api/vpn/client /config /status
│       └── mappings.py                ← /api/mappings (POST/GET/DELETE)
│
├── frontend/
│   ├── index.html                     ← الصفحة الرئيسية
│   ├── register.html                  ← التسجيل
│   ├── login.html                     ← تسجيل الدخول
│   ├── dashboard.html                 ← لوحة التحكم (VPN + Mappings)
│   ├── css/style.css
│   └── js/app.js                      ← تعامل مع الـAPI وتخزين التوكن
│
├── openvpn_templates/
│   └── client.ovpn.template           ← قالب بناء ملف .ovpn لكل مستخدم
│
└── scripts/
    ├── 00_setup_server.sh             ← يُشغَّل مرة واحدة على السيرفر (يُجهّز كل شيء)
    └── create_client.sh               ← يستدعيه الـBackend لتوليد شهادة عميل جديد
```

---

## 15) ما بعد النسخة الأولى (اختياري، بعد نجاح كل ما سبق)

```
UDP Mapping كامل    → نفس منطق TCP، مطبّق أصلًا في الكود (اختر Protocol=UDP من الواجهة)
Domain + HTTPS       → أضف DNS A record يشير إلى VPS_IP ثم شغّل certbot
Admin Dashboard      → صفحة /admin لعرض كل المستخدمين والـMappings وإدارتها
Rate Limiting        → أضف slowapi أو nginx limit_req
Quotas               → أضف حقل max_mappings في جدول users وتحقق منه قبل الإنشاء
Multiple VPS         → لاحقًا فقط، ليس مطلوبًا للنسخة الأولى
```

---

**بهذا يكون لديك Portmap خاص بك بالكامل: موقع، تسجيل حسابات، توليد `.ovpn` تلقائي، Dashboard، Port Mapping تلقائي عبر nftables، كل ذلك يعمل على VPS مجاني ضمن Oracle Always Free.**
