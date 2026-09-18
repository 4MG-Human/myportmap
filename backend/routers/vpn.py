from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

import models
import schemas
import vpn_certs
from config import settings
from database import get_db
from security import get_current_user

router = APIRouter(prefix="/api/vpn", tags=["vpn"])


@router.post("/client", response_model=schemas.VpnClientOut, status_code=201)
def create_vpn_client(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    existing = db.query(models.VpnClient).filter(models.VpnClient.user_id == user.id).first()
    if existing:
        return existing

    common_name = vpn_certs.build_common_name(user.id)
    used_ips = {row[0] for row in db.query(models.VpnClient.vpn_ip).all()}
    vpn_ip = None
    for host in range(2, 255):
        candidate = f"{settings.VPN_SUBNET_BASE}.{host}"
        if candidate not in used_ips:
            vpn_ip = candidate
            break
    if not vpn_ip:
        raise HTTPException(status_code=507, detail="انتهت عناوين شبكة الـVPN المتاحة (10.8.0.0/24)")

    vpn_certs.create_client_certificate(common_name)
    vpn_certs.write_ccd_file(common_name, vpn_ip)

    client = models.VpnClient(user_id=user.id, common_name=common_name, vpn_ip=vpn_ip)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("/config", response_class=PlainTextResponse)
def download_ovpn(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    client = db.query(models.VpnClient).filter(models.VpnClient.user_id == user.id).first()
    if not client:
        raise HTTPException(status_code=404, detail="لا يوجد عميل VPN بعد، أنشئه أولًا عبر /api/vpn/client")

    ovpn_text = vpn_certs.build_ovpn_file(client.common_name)
    return PlainTextResponse(content=ovpn_text, media_type="application/x-openvpn-profile")


@router.get("/status")
def vpn_status(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    client = db.query(models.VpnClient).filter(models.VpnClient.user_id == user.id).first()
    if not client:
        return {"connected": False, "vpn_ip": None}

    connected = False
    if settings.DEV_MODE:
        connected = True
    else:
        status_file = "/var/log/openvpn-status.log"
        try:
            with open(status_file) as f:
                content = f.read()
                connected = client.common_name in content
        except FileNotFoundError:
            connected = False

    return {"connected": connected, "vpn_ip": client.vpn_ip}
