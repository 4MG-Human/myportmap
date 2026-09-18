import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import firewall
import models
import schemas
from config import settings
from database import get_db
from security import get_current_user

router = APIRouter(prefix="/api/mappings", tags=["mappings"])


def _to_out(m: models.Mapping) -> schemas.MappingOut:
    return schemas.MappingOut(
        id=m.id,
        protocol=m.protocol,
        external_port=m.external_port,
        local_port=m.local_port,
        status=m.status,
        public_host=f"{settings.VPN_PUBLIC_IP}",
        created_at=m.created_at,
    )


def _allocate_external_port(db: Session, protocol: str) -> int:
    used = {
        row.external_port
        for row in db.query(models.Mapping.external_port)
        .filter(models.Mapping.protocol == protocol, models.Mapping.status == "active")
        .all()
    }
    candidates = list(range(settings.PORT_RANGE_START, settings.PORT_RANGE_END + 1))
    random.shuffle(candidates)
    for port in candidates:
        if port not in used:
            return port
    raise HTTPException(status_code=507, detail="لا توجد منافذ متاحة حاليًا")


@router.post("", response_model=schemas.MappingOut, status_code=201)
def create_mapping(
    payload: schemas.MappingCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    client = db.query(models.VpnClient).filter(models.VpnClient.user_id == user.id).first()
    if not client:
        raise HTTPException(status_code=400, detail="أنشئ عميل VPN أولًا قبل إنشاء Mapping")

    external_port = _allocate_external_port(db, payload.protocol)

    mapping = models.Mapping(
        user_id=user.id,
        vpn_client_id=client.id,
        protocol=payload.protocol,
        external_port=external_port,
        local_port=payload.local_port,
        status="active",
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)

    try:
        firewall.add_dnat_rule(mapping.id, mapping.protocol, mapping.external_port, client.vpn_ip, mapping.local_port)
    except Exception as exc:
        db.delete(mapping)
        db.commit()
        raise HTTPException(status_code=500, detail=f"فشل إنشاء قاعدة الجدار الناري: {exc}")

    return _to_out(mapping)


@router.get("", response_model=list[schemas.MappingOut])
def list_mappings(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    rows = (
        db.query(models.Mapping)
        .filter(models.Mapping.user_id == user.id, models.Mapping.status == "active")
        .all()
    )
    return [_to_out(m) for m in rows]


@router.delete("/{mapping_id}", status_code=204)
def delete_mapping(mapping_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    mapping = (
        db.query(models.Mapping)
        .filter(models.Mapping.id == mapping_id, models.Mapping.user_id == user.id)
        .first()
    )
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping غير موجود")

    firewall.remove_dnat_rule(mapping.id)
    db.delete(mapping)
    db.commit()
    return None
