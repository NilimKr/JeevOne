"""
storage/models.py
=================
SQLAlchemy ORM models for the local SQLite database.
Two tables:
  - sensor_readings  : raw (validated) sensor samples
  - risk_states      : processed risk assessments
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SensorReadingRecord(Base):
    """One validated sensor sample from the ESP32."""

    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp_epoch: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    timestamp_iso: Mapped[str] = mapped_column(String(32), nullable=False)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    heart_rate: Mapped[float] = mapped_column(Float, nullable=False)
    spo2: Mapped[float] = mapped_column(Float, nullable=False)
    body_temperature: Mapped[float] = mapped_column(Float, nullable=False)
    room_temperature: Mapped[float] = mapped_column(Float, nullable=False)
    humidity: Mapped[float] = mapped_column(Float, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<SensorReading id={self.id} ts={self.timestamp_iso} "
            f"device={self.device_id} hr={self.heart_rate} spo2={self.spo2}>"
        )


class RiskStateRecord(Base):
    """Processed risk state snapshot after each reading."""

    __tablename__ = "risk_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp_epoch: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    timestamp_iso: Mapped[str] = mapped_column(String(32), nullable=False)
    heat_risk: Mapped[str] = mapped_column(String(16), nullable=False)
    vital_risk: Mapped[str] = mapped_column(String(16), nullable=False)
    respiratory_risk: Mapped[str] = mapped_column(String(16), nullable=False)
    overall_status: Mapped[str] = mapped_column(String(16), nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    reasons: Mapped[str] = mapped_column(Text, nullable=False)   # JSON list

    def __repr__(self) -> str:
        return (
            f"<RiskState id={self.id} ts={self.timestamp_iso} "
            f"overall={self.overall_status}>"
        )
