"""
إدارة شهادات عملاء OpenVPN وتوليد ملفات .ovpn.

مهم جدًا: لا نمرر أي مدخل مستخدم مباشرة إلى subprocess/shell.
الـcommon_name يُبنى داخليًا من user_id فقط (وليس من نص يكتبه المستخدم)،
لذلك لا يوجد مجال لـCommand Injection من هذا المسار.
"""
import re
import subprocess
from pathlib import Path

from config import settings

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
CLIENT_OVPN_TEMPLATE = Path(__file__).resolve().parent.parent / "openvpn_templates" / "client.ovpn.template"

SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def build_common_name(user_id: int) -> str:
    return f"user{user_id}"


def next_vpn_ip(existing_count: int) -> str:
    # .1 هو السيرفر نفسه، لذلك نبدأ العملاء من .2
    host = existing_count + 2
    if host > 254:
        raise RuntimeError("انتهت عناوين شبكة الـVPN المتاحة (10.8.0.0/24)")
    return f"{settings.VPN_SUBNET_BASE}.{host}"


def write_ccd_file(common_name: str, vpn_ip: str) -> None:
    """كتابة قاعدة ifconfig-push لتثبيت IP العميل عند اتصاله بنفق OpenVPN"""
    if settings.DEV_MODE:
        return
    ccd_path = Path(settings.CCD_DIR)
    ccd_path.mkdir(parents=True, exist_ok=True)
    client_file = ccd_path / common_name
    client_file.write_text(f"ifconfig-push {vpn_ip} 255.255.255.0\n")


def delete_ccd_file(common_name: str) -> None:
    if settings.DEV_MODE:
        return
    client_file = Path(settings.CCD_DIR) / common_name
    if client_file.exists():
        client_file.unlink()


def create_client_certificate(common_name: str) -> None:
    if not SAFE_NAME_RE.match(common_name):
        raise ValueError("اسم غير صالح للـcommon_name")

    if settings.DEV_MODE:
        return

    script = SCRIPTS_DIR / "create_client.sh"
    result = subprocess.run(
        ["sudo", str(script), common_name],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"فشل إنشاء الشهادة: {result.stderr.strip()}")


def _read_pki_file(relative_path: str) -> str:
    path = Path(settings.PKI_DIR) / relative_path
    return path.read_text()


def build_ovpn_file(common_name: str) -> str:
    if settings.DEV_MODE:
        return f"# [DEV_MODE MOCK OVPN PROFILE FOR {common_name}]\nclient\ndev tun\nproto udp\nremote 127.0.0.1 1194\n"

    template = CLIENT_OVPN_TEMPLATE.read_text()

    ca = _read_pki_file("ca.crt")
    cert_full = _read_pki_file(f"issued/{common_name}.crt")
    key = _read_pki_file(f"private/{common_name}.key")
    ta = (Path(settings.OPENVPN_SERVER_DIR) / "ta.key").read_text()

    # استخراج جزء الشهادة فقط بين BEGIN/END CERTIFICATE (easy-rsa يضيف نصًا قبلها)
    cert = _extract_block(cert_full, "CERTIFICATE")

    ovpn = (
        template.replace("__VPN_PUBLIC_IP__", settings.VPN_PUBLIC_IP)
        .replace("__VPN_PORT__", str(settings.VPN_PORT))
        .replace("__VPN_PROTO__", settings.VPN_PROTO)
        .replace("__CA__", ca.strip())
        .replace("__CERT__", cert.strip())
        .replace("__KEY__", key.strip())
        .replace("__TA__", ta.strip())
    )
    return ovpn


def _extract_block(text: str, tag: str) -> str:
    begin = f"-----BEGIN {tag}-----"
    end = f"-----END {tag}-----"
    start_idx = text.index(begin)
    end_idx = text.index(end) + len(end)
    return text[start_idx:end_idx]
