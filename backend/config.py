import os
import platform
import urllib.request
from pathlib import Path
from pydantic_settings import BaseSettings


def _get_default_public_ip() -> str:
    env_ip = os.getenv("VPN_PUBLIC_IP")
    if env_ip:
        return env_ip
    # محاولة كشف الـ IP العام تلقائيًا من الخارج
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                ip = resp.read().decode("utf-8").strip()
                if ip and len(ip) <= 45:
                    return ip
        except Exception:
            continue
    return "127.0.0.1"


class Settings(BaseSettings):
    DEV_MODE: bool = (
        platform.system() == "Windows"
        or os.getenv("CODESPACES") == "true"
        or not Path("/etc/openvpn/easy-rsa").exists()
    )
    SECRET_KEY: str = "dev-only-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    DATABASE_URL: str = "sqlite:///./myportmap.db"

    VPN_PUBLIC_IP: str = _get_default_public_ip()
    VPN_PORT: int = 1194
    VPN_PROTO: str = "udp"

    EASYRSA_DIR: str = "/etc/openvpn/easy-rsa"
    PKI_DIR: str = "/etc/openvpn/easy-rsa/pki"
    OPENVPN_SERVER_DIR: str = "/etc/openvpn/server"
    CCD_DIR: str = "/etc/openvpn/ccd"

    VPN_SUBNET_BASE: str = "10.8.0"

    PORT_RANGE_START: int = 40000
    PORT_RANGE_END: int = 50000

    NFT_TABLE: str = "myportmap"

    class Config:
        env_file = ".env"


settings = Settings()

