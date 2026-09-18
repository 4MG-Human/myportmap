"""
اختبار شامل لجميع وظائف MyPortMap:
1. التسجيل والدخول (Auth)
2. إنشاء عميل VPN (Vpn Client)
3. فحص ملف .ovpn والتأكد من احتوائه على الشهادات والمفاتيح والـ IP
4. إنشاء Mapping للمنفذ 4444
5. فحص قائمة الـ Mappings والتأكد من المنفذ الخارجي والداخلي
6. حذف الـ Mapping
"""
import sys
from pathlib import Path

# ضبط الترميز ليدعم UTF-8 على ويندوز
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# إضافة مجلد backend للمسار
backend_dir = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_dir))


from fastapi.testclient import TestClient
from main import app
from config import settings
from database import engine
import models

models.Base.metadata.create_all(bind=engine)
client = TestClient(app)


def run_tests():
    print("=" * 60)
    print("بدء الاختبار الشامل لنظام MyPortMap...")
    print(f"بيئة التشغيل: DEV_MODE = {settings.DEV_MODE}")
    print(f"الـ Public IP المكتشف: {settings.VPN_PUBLIC_IP}")
    print("=" * 60)

    # 1. فحص الصحة (Health check)
    res = client.get("/api/health")
    assert res.status_code == 200, f"فشل Health check: {res.text}"
    print("✅ 1. Health check ناجح: status = ok")

    # 2. تسجيل مستخدم جديد
    import time
    test_email = f"test_{int(time.time())}@example.com"
    res = client.post("/api/auth/register", json={"email": test_email, "password": "Password123!"})
    assert res.status_code == 201, f"فشل التسجيل: {res.text}"
    print(f"✅ 2. التسجيل ناجح للمستخدم: {test_email}")

    # 3. تسجيل الدخول
    res = client.post("/api/auth/login", data={"username": test_email, "password": "Password123!"})
    assert res.status_code == 200, f"فشل تسجيل الدخول: {res.text}"
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ 3. تسجيل الدخول والحصول على JWT Token ناجح")


    # 4. إنشاء عميل VPN
    res = client.post("/api/vpn/client", headers=headers)
    assert res.status_code == 201, f"فشل إنشاء عميل VPN: {res.text}"
    vpn_data = res.json()
    print(f"✅ 4. تم إنشاء عميل VPN بنجاح: Common Name = {vpn_data['common_name']}, VPN IP = {vpn_data['vpn_ip']}")

    # 5. تحميل وفحص ملف .ovpn
    res = client.get("/api/vpn/config", headers=headers)
    assert res.status_code == 200, f"فشل تحميل .ovpn: {res.text}"
    ovpn_content = res.text
    assert "client" in ovpn_content, "ملف .ovpn لا يحتوي على client"
    assert "dev tun" in ovpn_content, "ملف .ovpn لا يحتوي على dev tun"
    assert f"remote {settings.VPN_PUBLIC_IP}" in ovpn_content, f"ملف .ovpn لا يحتوي على IP السيرفر {settings.VPN_PUBLIC_IP}"
    assert "<ca>" in ovpn_content and "</ca>" in ovpn_content, "ملف .ovpn ينقصه <ca>"
    assert "<cert>" in ovpn_content and "</cert>" in ovpn_content, "ملف .ovpn ينقصه <cert>"
    assert "<key>" in ovpn_content and "</key>" in ovpn_content, "ملف .ovpn ينقصه <key>"
    assert "<tls-crypt>" in ovpn_content and "</tls-crypt>" in ovpn_content, "ملف .ovpn ينقصه <tls-crypt>"
    print("✅ 5. فحص ملف .ovpn ناجح: يحتوي على السيرفر، الشهادات، والمفاتيح كاملة!")

    # 6. إنشاء Mapping للمنفذ 4444
    res = client.post("/api/mappings", headers=headers, json={"protocol": "tcp", "local_port": 4444})
    assert res.status_code == 201, f"فشل إنشاء Mapping: {res.text}"
    map_data = res.json()
    mapping_id = map_data["id"]
    external_port = map_data["external_port"]
    local_port = map_data["local_port"]
    public_host = map_data["public_host"]
    print(f"✅ 6. تم إنشاء توجيه المنفذ (Mapping) بنجاح:")
    print(f"   TCP {public_host}:{external_port} ──(DNAT)──> local:{local_port}")
    assert local_port == 4444, "المنفذ الداخلي ليس 4444"
    assert 40000 <= external_port <= 50000, f"المنفذ الخارجي {external_port} خارج النطاق المخصص"

    # 7. جلب قائمة الـ Mappings
    res = client.get("/api/mappings", headers=headers)
    assert res.status_code == 200, f"فشل جلب الـ Mappings: {res.text}"
    mappings_list = res.json()
    assert len(mappings_list) >= 1, "قائمة الـ Mappings فارغة"
    assert any(m["id"] == mapping_id for m in mappings_list), "الـ Mapping الجديد غير موجود في القائمة"
    print(f"✅ 7. جلب قائمة الـ Mappings ناجح وتتضمن المنفذ {external_port} -> 4444")

    # 8. فحص حالة الـ VPN
    res = client.get("/api/vpn/status", headers=headers)
    assert res.status_code == 200, f"فشل فحص حالة الـ VPN: {res.text}"
    status_data = res.json()
    print(f"✅ 8. حالة الـ VPN: Connected = {status_data['connected']}, IP = {status_data['vpn_ip']}")

    # 9. حذف الـ Mapping للتأكد من سلامة عملية الحذف
    res = client.delete(f"/api/mappings/{mapping_id}", headers=headers)
    assert res.status_code in (200, 204), f"فشل حذف الـ Mapping: {res.text}"
    res = client.get("/api/mappings", headers=headers)
    assert not any(m["id"] == mapping_id for m in res.json()), "فشل إزالة الـ Mapping بعد الحذف"
    print("✅ 9. حذف الـ Mapping تم بنجاح وتحديث الجدول")


    print("=" * 60)
    print("🎉 جميع الاختبارات اجتازت بنجاح 100%! كل الوظائف تعمل بشكل مثالي.")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
