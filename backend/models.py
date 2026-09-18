from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    vpn_clients = relationship("VpnClient", back_populates="owner", cascade="all, delete-orphan")
    mappings = relationship("Mapping", back_populates="owner", cascade="all, delete-orphan")


class VpnClient(Base):
    __tablename__ = "vpn_clients"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    common_name = Column(String, unique=True, index=True, nullable=False)
    vpn_ip = Column(String, unique=True, nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="vpn_clients")
    mappings = relationship("Mapping", back_populates="vpn_client", cascade="all, delete-orphan")


class Mapping(Base):
    __tablename__ = "mappings"
    __table_args__ = (UniqueConstraint("protocol", "external_port", name="uq_proto_extport"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vpn_client_id = Column(Integer, ForeignKey("vpn_clients.id"), nullable=False)
    protocol = Column(String, nullable=False)  # tcp | udp
    external_port = Column(Integer, nullable=False)
    local_port = Column(Integer, nullable=False)
    status = Column(String, default="active")  # active | deleted
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="mappings")
    vpn_client = relationship("VpnClient", back_populates="mappings")
