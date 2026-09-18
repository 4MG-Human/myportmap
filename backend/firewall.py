"""
إدارة قواعد nftables لتمرير المنافذ (DNAT) من الـVPS العام إلى عناوين الـVPN الداخلية.

قواعد أمان:
- protocol يجب أن يكون "tcp" أو "udp" فقط (يفرضها pydantic قبل الوصول هنا).
- external_port و local_port أعداد صحيحة 1-65535 (تفرضها pydantic).
- vpn_ip يُقرأ من قاعدة البيانات (من سجل vpn_clients الخاص بالمستخدم نفسه)
  وليس نصًا حرًا من المستخدم، ويجب أن يبدأ بـ VPN_SUBNET_BASE فقط.
- كل قيمة تُمرَّر إلى nft كعنصر منفصل في القائمة (لا نبني نصًا واحدًا ونمرره لـshell=True)،
  لذلك لا يوجد Shell/Command Injection من هذا المسار.
"""
import re
import subprocess

from config import settings

IP_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")


def _run(args: list[str]) -> str:
    if settings.DEV_MODE:
        return ""
    result = subprocess.run(["sudo", "nft", *args], capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        raise RuntimeError(f"nft error: {result.stderr.strip()}")
    return result.stdout


def _validate(protocol: str, port: int, vpn_ip: str) -> None:
    if protocol not in ("tcp", "udp"):
        raise ValueError("protocol غير صالح")
    if not (1 <= port <= 65535):
        raise ValueError("port غير صالح")
    if not IP_RE.match(vpn_ip) or not vpn_ip.startswith(settings.VPN_SUBNET_BASE + "."):
        raise ValueError("vpn_ip غير صالح أو خارج شبكة الـVPN")


def add_dnat_rule(mapping_id: int, protocol: str, external_port: int, vpn_ip: str, local_port: int) -> None:
    _validate(protocol, external_port, vpn_ip)
    _validate(protocol, local_port, vpn_ip)

    comment = f"myportmap_{mapping_id}"
    table = settings.NFT_TABLE

    # قاعدة الـDNAT في prerouting
    _run([
        "add", "rule", "ip", table, "prerouting",
        "meta", "l4proto", protocol,
        "th", "dport", str(external_port),
        "dnat", "to", f"{vpn_ip}:{local_port}",
        "comment", comment,
    ])

    # السماح بمرور الترافيك المُحوَّل في forward
    _run([
        "add", "rule", "ip", table, "forward",
        "ip", "daddr", vpn_ip,
        "meta", "l4proto", protocol,
        "th", "dport", str(local_port),
        "accept",
        "comment", comment,
    ])


def remove_dnat_rule(mapping_id: int) -> None:
    comment = f"myportmap_{mapping_id}"
    table = settings.NFT_TABLE

    for chain in ("prerouting", "forward"):
        listing = _run(["-a", "list", "chain", "ip", table, chain])
        for line in listing.splitlines():
            if comment in line and "handle" in line:
                handle = line.strip().split("handle")[-1].strip()
                _run(["delete", "rule", "ip", table, chain, "handle", handle])
