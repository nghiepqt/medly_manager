from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey, DateTime, Text, UniqueConstraint, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Hospital(Base):
    __tablename__ = "hospitals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=False, nullable=False)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    departments: Mapped[list["Department"]] = relationship(back_populates="hospital", cascade="all, delete-orphan")

class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    hospital: Mapped[Hospital] = relationship(back_populates="departments")
    doctors: Mapped[list["Doctor"]] = relationship(back_populates="department", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("hospital_id", "name", name="uq_department_hospital_name"),)

class Doctor(Base):
    __tablename__ = "doctors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), nullable=False)
    department: Mapped[Department] = relationship(back_populates="doctors")
    phone: Mapped[str] = mapped_column(String(10))
    roles: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    cccd: Mapped[str] = mapped_column(String(12), unique=True)
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="user")

class Appointment(Base):
    __tablename__ = "appointments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False)
    when: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    stt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    need: Mapped[str] = mapped_column(Text, nullable=True)
    symptoms: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    user: Mapped[User] = relationship(back_populates="appointments")
    doctor: Mapped[Doctor] = relationship()

    # Slot relationship removed; busy is derived from Appointment

class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    summary: Mapped[str] = mapped_column(Text)
    symptoms: Mapped[str] = mapped_column(Text, nullable=True)


class ScheduleWindow(Base):
    """Doctor schedule windows for availability management.
    kind: 'available' (green) or 'ooo' (gray)
    """
    __tablename__ = "schedule_windows"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False)
    start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    __table_args__ = (UniqueConstraint("doctor_id", "start", "end", "kind", name="uq_window_unique"),)


class Room(Base):
    __tablename__ = "rooms"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), nullable=False)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    __table_args__ = (UniqueConstraint("hospital_id", "code", name="uq_room_hospital_code"),)
