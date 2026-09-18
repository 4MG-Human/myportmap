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


MOCK_CA = """-----BEGIN CERTIFICATE-----
MIIDSDCCAjCgAwIBAgIUStIHC8goPcXPzdKkO2ovj9DyTagwDQYJKoZIhvcNAQEL
BQAwFTETMBEGA1UEAwwKUG9ydG1hcCBDQTAeFw0yNTEwMzAwMTE3NDFaFw0zNTEw
MjgwMTE3NDFaMBUxEzARBgNVBAMMClBvcnRtYXAgQ0EwggEiMA0GCSqGSIb3DQEB
AQUAA4IBDwAwggEKAoIBAQCnSBLhf3eDHOc2a6dl4YcdcIsFLNmLYdZo2J1qBp/N
MoZrpFWY1qf0VpphArqkaD4UY+8uOPyfZ+3yxhPOVZzGsYSYykpkIWWGi7HwBe6x
PpjLTT3XvBRSz6KHGUcXldeQxJKSmS9blq1+JcI3QRgVUL+Q3/HrvrAyUVTmzMip
aKe1m2L6h78dfLs8BOjxHk29sJiQHstNrMmBJehy4VdltzNGGAraFQLYaqIUWxyx
2AZcJcgHOYzzf+T8KR8ig69PbXgFC50dZH6uiPv0f2PEcXSQ4o5bY2e4kurFEuAN
KJTa/Y3crJ897CxpHdplgJcEomML1y3bxE/QtNNF2eMNAgMBAAGjgY8wgYwwHQYD
VR0OBBYEFF7F7x9Sl3KG6QtZuCKS/KtrfwCfMFAGA1UdIwRJMEeAFF7F7x9Sl3KG
6QtZuCKS/KtrfwCfoRmkFzAVMRMwEQYDVQQDDApQb3J0bWFwIENBghRK0gcLyCg9
xc/N0qQ7ai+P0PJNqDAMBgNVHRMEBTADAQH/MAsGA1UdDwQEAwIBBjANBgkqhkiG
9w0BAQsFAAOCAQEAHRHTX724CjGcfVcE/AscysAYXlVXmc48vKx9kqJiqyG7+mBt
gW5aIIqHIDGCyIJD47GRH6E0Rb19opGru53KsHUhiMXeSCmH+N/zew35l3R3cyLZ
fAHFlqeeLve5g7ozPWgpRoCISVoP8Us2jggwheOYNtTU4C9lVr2ojejmIz2rq03p
p6rHY0AfwzZRfN5CQkXAUauVvwo5QupmUQ1z8aBnW9WZLCLu114wpqSqMaTzkD89
aenMJoWMRnJhW1yt0aL3c/0b+EzfaRePE+i0SpjIYdXPrcRXLayJZygzBgl2nUaa
Yn4yh0mVdscdM7FLTCq8PWQDCmr6dgsRzdMLPA==
-----END CERTIFICATE-----"""

MOCK_CERT = """-----BEGIN CERTIFICATE-----
MIIDWzCCAkOgAwIBAgIRAKCq+cGP2dLzuomoq0JId1owDQYJKoZIhvcNAQELBQAw
FTETMBEGA1UEAwwKUG9ydG1hcCBDQTAeFw0yNjA4MTQxMzU1MjlaFw0zNjA4MTEx
MzU1MjlaMBkxFzAVBgNVBAMMDm1vbnFpdGguQU1HTU9OMIIBIjANBgkqhkiG9w0B
AQEFAAOCAQ8AMIIBCgKCAQEA06uSdHsJnoRSQWapaO8BWyM1bkJZHF1/tMJAAi9s
72/HjTjLpP/sIQTETEKhcgpGx4O3T3oTw27nneDx4Sw/PxucM/QPKY7YJCJnUdJz
tYkPdFTvqFAVpMYbiSDj2QE5F+zu2Iq5UqH6QcpkvIPHn+tNhsn8tHwODHGzBlLT
6aByHg6jx9vxO3Pca8L47QuzMk0kt6xkRCeWlh/fBhYfTDawvJDj4aXLKix+5Ixd
bbUhsUeFo1/lgKOxIMOE5zSh6EGSw1VCN6yNbYbr1FkPWDsf1VZ92HcgVpYQXOdy
IPMQ7c4WpeUhDSg6HzLbXTF2Ow8c0J/TN1xHkUNI37m5gQIDAQABo4GhMIGeMAkG
A1UdEwQCMAAwHQYDVR0OBBYEFEAb/ipfgH04MYaY/8gZmeNYHXfyMFAGA1UdIwRJ
MEeAFF7F7x9Sl3KG6QtZuCKS/KtrfwCfoRmkFzAVMRMwEQYDVQQDDApQb3J0bWFw
IENBghRK0gcLyCg9xc/N0qQ7ai+P0PJNqDATBgNVHSUEDDAKBggrBgEFBQcDAjAL
BgNVHQ8EBAMCB4AwDQYJKoZIhvcNAQELBQADggEBAHEbKw6reK9syIsJouRBqrZF
EWcRmEf/gSAFn/muJpr029fCabCfvsg/BLftePFnlJspgVqThrUvXBF+OxKsbaxg
osHGjkmEiu9hO7BaPj9JfVcJ23G4bqzwoQorWELfo+NtrGMf7JKY5m8pjUUKTtL4
dlZUJN8TCltYtcJC8OqpEvLJoXVUuGcZNdpfM3P9Ktq4QPCn7WVSB9fULA9Jwh/s
IAYuXX2B0lQW5LZUWX+rYvkEqb8IV0U5i+D0mIohgzxdssTptd6zcD3+28HlkZJa
JCkzE7MUqadf6nLCAG9iXSHwvxUBJQKg5FpxkaDI5GhJ4/vKcA1JX7uRrxHNX0U=
-----END CERTIFICATE-----"""

MOCK_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDTq5J0ewmehFJB
Zqlo7wFbIzVuQlkcXX+0wkACL2zvb8eNOMuk/+whBMRMQqFyCkbHg7dPehPDbued
4PHhLD8/G5wz9A8pjtgkImdR0nO1iQ90VO+oUBWkxhuJIOPZATkX7O7YirlSofpB
ymS8g8ef602Gyfy0fA4McbMGUtPpoHIeDqPH2/E7c9xrwvjtC7MyTSS3rGREJ5aW
H98GFh9MNrC8kOPhpcsqLH7kjF1ttSGxR4WjX+WAo7Egw4TnNKHoQZLDVUI3rI1t
huvUWQ9YOx/VVn3YdyBWlhBc53Ig8xDtzhal5SENKDofMttdMXY7DxzQn9M3XEeR
Q0jfubmBAgMBAAECggEAAaoA/5uOmlLTh6OONXFgv8nnl/wgwa0PlZuml6HORosI
3QX3Q2RWmQCbJ2HpeCPyACGWO7NTw72WfRvdQ5zRVePHyHMyGedPUOg96tNc9k5r
WxSLx7Vn+HzNJKiymTSApveQKI7deROQYVX9O7Zsl7KIpa9G4QzIipMLrNMSlYz0
wsfUp4r2zVSraXiLiujmAUHK2a6yUAnSrA0zVliwDKa9Vo2B+DuIaBEjpk01fdk0
DUsJx6GRvuOkObDrt+/QiuPDnneXEfPXd/UdWZWIv3VLy+XlvkWHny0SNQWaMJ3E
XWdZP8sdlBRxUU5Dj7HfORNulL8aahHdsyCmEllecQKBgQDbjzjiaMXHUWB8Ta6T
K5IrO3l16A+eTzzfk+AqtzzkW6nJPEgJxA+/MfbRJZZAdjgvq1OIiLYZzmPjWM/e
gxRMr+iK8lsATFuZ6s8y4+flU6jQQMfgUtacCmeqt5gD0iOgGF7wADbIsb3nMYOJ
bFJeMoNK8TwYMTEQN75UgpraUQKBgQD2zSVuX/LuprEiVTDoqTrisxhSQEjbaYpk
7C5On64wbh/Tou9P0MxfyXCqyKXo7tH9dpqResH0db1HMVlwSGOLWXb5BeyrFrjT
OzXbROegQU/yIpXP0XMl3PlCZP0C8DBkDDiy/jtabGbdo0UJO4xlakeGtzpT88ew
NzJwGErwMQKBgQCvyG0sp+GhAMAVBUS9w2aVglpuUcsfXiVIg2Y4DNiNo+29lau/
Vd+dne0T6dnv5jZ5w9tvNrVE1/8VKCfU6HE6LKQrinndNUUpZ9tXzSv+aQqBITxl
ly0HZTU2cyMb/ARVyu1HjYRPDi8SiIvdXIJdtGd1eso4PDoh199kXeSI4QKBgQC9
6ikWoVDwYmdGUyX6s1bz4fsiOAOYi8OKW9BagjfpXqSxF91tnu/V+c3wLcy1zSjc
EWtp7XvY4M1RPmFjrOCk96g8glmXYjnBmfucio5u3DNn0UNVEwi3py5L8CheHXQv
WNQ8sLP9phMWFLBoJWGpHLqDqPWCasJMEH2Ikrj/0QKBgALPHmcvNpjWbUOMO9g6
B3DgV+fPlv76/+M3FoU+jH9E+c/ApcK0OIQ5rITP/74KSIY6CdPTPYGnGyNY7KEo
QF6V2P19eT9gHvishESVkFqm/qHgS+pxJ0GQFHKAhCaGB0KU2POhV7lgDs2zqiom
IRRFZzhXsADXLFtBArl26e+w
-----END PRIVATE KEY-----"""

MOCK_TA = """#
# 2048 bit OpenVPN static key
#
-----BEGIN OpenVPN Static key V1-----
42bb453ee0df769b134e57435c88a745
927d7fd254987077bdf822567410ed73
f816335742f5737b0ad1e290ebe4e669
1a8edad3f23aff0c4872172f1e3c30d2
025cddbfd2dfdcecb3ef2f1f4e531c60
1e9c48e1abe96c46c80eaa5f121a72b5
e7b194a6a0abc06fbc736abc41122f5d
aa0c7ddcfc80455983ac7e6cb005d0c7
7ef5ed9c20cebe4481a733a5b4e63ba8
74a0710bcd0b732d5b79ef6e2032c0c2
6e1cbe01873367524a28d582901ceed1
241fe087a8e84467c9c790c7af719622
413fcc77b130629258db8a8e6678f53c
7cd213dc82e5b613ca310642cfbb6cb5
63111511e467f45417d9950035827d30
43b13e9e01f0c42481edb1fe1808806b
-----END OpenVPN Static key V1-----"""


def build_ovpn_file(common_name: str) -> str:
    template = CLIENT_OVPN_TEMPLATE.read_text()

    if settings.DEV_MODE:
        ca = MOCK_CA
        cert = MOCK_CERT
        key = MOCK_KEY
        ta = MOCK_TA
    else:
        ca = _read_pki_file("ca.crt")
        cert_full = _read_pki_file(f"issued/{common_name}.crt")
        key = _read_pki_file(f"private/{common_name}.key")
        ta = (Path(settings.OPENVPN_SERVER_DIR) / "ta.key").read_text()
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

