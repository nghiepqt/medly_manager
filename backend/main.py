from fastapi import FastAPI, Query, HTTPException
import logging
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, timedelta, date, time as dtime
from sqlalchemy import select, and_, func, or_, delete, update, inspect
from backend.db import get_session, engine
from backend.timing_instrumentation import TimingMiddleware, attach_sqlalchemy_instrumentation
from backend.models import Base, Hospital, Department, Doctor, User, Appointment, Conversation, ScheduleWindow, Room
from backend import seed_loader
import os
import json
from pathlib import Path
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text as sa_text
from sqlalchemy.exc import ProgrammingError
from collections import defaultdict

app = FastAPI(title="Medly API")
app.add_middleware(TimingMiddleware)
_HAS_HOSPITAL_ADDRESS: Optional[bool] = None

def has_hospital_address() -> bool:
    global _HAS_HOSPITAL_ADDRESS
    if _HAS_HOSPITAL_ADDRESS is None:
        try:
            cols = sa_inspect(engine).get_columns("hospitals")
            _HAS_HOSPITAL_ADDRESS = any(c.get("name") == "address" for c in cols)
        except Exception:
            _HAS_HOSPITAL_ADDRESS = False
    return bool(_HAS_HOSPITAL_ADDRESS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)


# --------- Utilities ---------
def ensure_seed():
    """Seed data from exactly two JSON files once tables exist."""
    try:
        insp = inspect(engine)
        required = ["hospitals", "departments", "doctors", "rooms"]
        missing = [t for t in required if not insp.has_table(t)]
        if missing:
            print("Skipping seed: missing tables -> " + ", ".join(missing))
            return
        # Load only the two seed files the user requested
        from backend.seed_loader import seed_two_files_only
        summary = seed_two_files_only()
        print("[seed]", summary)
    except Exception as e:
        print(f"Seed load failed: {e}")
    # Startup now only ensures seed from the two JSON files; demo data seeding removed.


@app.on_event("startup")
def startup():
    # Attach SQLAlchemy query timing & slow query logging
    try:
        attach_sqlalchemy_instrumentation(engine)
    except Exception as e:
        print(f"[timing] attach_sqlalchemy_instrumentation failed: {e}")
    # Best-effort unique index to prevent exact duplicate windows
    try:
        with engine.begin() as conn:
            conn.execute(sa_text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ux_windows_doc_start_end_kind
                ON schedule_windows (doctor_id, start, "end", kind)
                """
            ))
            # Ensure appointments.stt exists (best-effort) and backfill if missing
            conn.execute(sa_text(
                """
                ALTER TABLE appointments ADD COLUMN IF NOT EXISTS stt integer
                """
            ))
            # Backfill stt for existing rows where null: daily sequence per doctor by appointment time
            try:
                conn.execute(sa_text(
                    """
                    WITH ranked AS (
                        SELECT id, ROW_NUMBER() OVER (PARTITION BY doctor_id, DATE("when") ORDER BY "when" ASC, id ASC) AS rn
                        FROM appointments
                    )
                    UPDATE appointments a
                    SET stt = r.rn
                    FROM ranked r
                    WHERE a.id = r.id AND a.stt IS NULL
                    """
                ))
            except Exception:
                pass
    except Exception as e:
        print(f"[startup] unique index create skipped: {e}")
    ensure_seed()

# Basic logging config for timing loggers
logging.basicConfig(level=logging.INFO)


# --------- Schemas ---------
class UserPayload(BaseModel):
    phone: str
    name: str
    cccd: Optional[str] = None


@app.post("/api/users")
def create_or_fetch_user(payload: UserPayload):
    """
    Login or create:
    - First try exact match on lower(name) + phone (fast via functional index).
    - If not found, try by phone only; if exists, update the name/cccd if provided.
    - Else create a new user.
    """
    name = (payload.name or "").strip()
    phone = "".join(ch for ch in (payload.phone or "") if ch.isdigit()) or (payload.phone or "").strip()
    with get_session() as db:
        # 1) exact match by lower(name) + phone
        lowered = name.lower()
        u = db.execute(
            select(User).where(func.lower(User.name) == lowered, User.phone == phone)
        ).scalar_one_or_none()
        if u:
            return {"id": str(u.id), "phone": u.phone, "name": u.name}

        # 2) fallback: by phone only, then update name/cccd if changed
        u = db.execute(select(User).where(User.phone == phone)).scalar_one_or_none()
        if u:
            changed = False
            if name and u.name != name:
                u.name = name
                changed = True
            if payload.cccd and getattr(u, "cccd", None) != payload.cccd:
                u.cccd = payload.cccd
                changed = True
            if changed:
                db.flush()
            return {"id": str(u.id), "phone": u.phone, "name": u.name}

        # 3) create new
        new_u = User(name=name or "Người dùng", phone=phone, cccd=payload.cccd)
        db.add(new_u)
        db.flush()
        return {"id": str(new_u.id), "phone": new_u.phone, "name": new_u.name}




def base_day_slots(day: date) -> list[tuple[datetime, datetime]]:
    # 30-min slots from 08:00 to 18:00
    start_hour = 8
    end_hour = 18
    slots = []
    cur = datetime.combine(day, dtime(hour=start_hour))
    end = datetime.combine(day, dtime(hour=end_hour))
    while cur < end:
        slots.append((cur, cur + timedelta(minutes=30)))
        cur += timedelta(minutes=30)
    return slots


class BookingSummary(BaseModel):
    userId: str
    name: str
    phone: str
    need: str
    symptoms: Optional[str] = None
    hospitalId: str
    hospitalName: str
    hospitalAddress: Optional[str] = None
    department: str
    doctorId: str
    doctorName: str
    time: str


@app.post("/api/book")
def book(summary: BookingSummary):
    """Create booking with validation.
    Duration is 15 minutes. Must be within an available window, not overlap OOO, and not overlap existing busy.
    """
    start_dt = datetime.fromisoformat(summary.time)
    end_dt = start_dt + timedelta(minutes=15)
    doctor_id = int(summary.doctorId)
    with get_session() as db:
        # Validate constraints
        err = _check_slot_constraints(db, doctor_id, start_dt, end_dt)
        if err:
            raise HTTPException(status_code=409, detail=err)

        # Upsert or create user
        u = db.get(User, int(summary.userId))
        if not u:
            # fallback create
            u = User(id=int(summary.userId), name=summary.name, phone=summary.phone)
            db.add(u)
            db.flush()
        # Compute STT for the day per doctor
        day_start = datetime.combine(start_dt.date(), dtime.min)
        day_end = datetime.combine(start_dt.date(), dtime.max)
        cur_stt = db.scalar(
            select(func.coalesce(func.max(Appointment.stt), 0))
            .where(Appointment.doctor_id == doctor_id, Appointment.when >= day_start, Appointment.when <= day_end)
        ) or 0
        # Create appointment with stt = max + 1
        appt = Appointment(user=u, doctor_id=doctor_id, when=start_dt, stt=int(cur_stt) + 1, need=summary.need, symptoms=summary.symptoms or None)
        db.add(appt)
        db.flush()
        summary.time = start_dt.isoformat()
        return summary



# --------- External booking ingest ---------
class ExternalBookingPayload(BaseModel):
    hospital: str
    patient_name: str
    phone_number: str
    doctor_name: str
    department_name: str
    room_code: Optional[str] = None
    time_slot: str
    symptoms: Optional[List[str]] = None


def _ensure_entities(db, hospital_name: str, department_name: str, doctor_name: str):
    hosp = db.execute(select(Hospital).where(func.lower(Hospital.name) == hospital_name.lower())).scalar_one_or_none()
    if not hosp:
        hosp = Hospital(name=hospital_name)
        db.add(hosp)
        db.flush()
    dep = db.execute(select(Department).where(Department.hospital_id == hosp.id, func.lower(Department.name) == department_name.lower())).scalar_one_or_none()
    if not dep:
        dep = Department(name=department_name, hospital_id=hosp.id)
        db.add(dep)
        db.flush()
    doc = db.execute(select(Doctor).where(Doctor.department_id == dep.id, func.lower(Doctor.name) == doctor_name.lower())).scalar_one_or_none()
    if not doc:
        doc = Doctor(name=doctor_name, department_id=dep.id)
        db.add(doc)
        db.flush()
    return hosp, dep, doc


@app.post("/api/bookings")
def ingest_booking(payload: ExternalBookingPayload):
    # Map external JSON into our internal BookingSummary, create entities as needed
    with get_session() as db:
        hosp, dep, doc = _ensure_entities(db, payload.hospital.strip(), payload.department_name.strip(), payload.doctor_name.strip())
        # user
        u = db.execute(select(User).where(User.phone == payload.phone_number)).scalar_one_or_none()
        if not u:
            u = User(name=payload.patient_name, phone=payload.phone_number)
            db.add(u)
            db.flush()
        when_iso = payload.time_slot
        bs = BookingSummary(
            userId=str(u.id),
            name=u.name,
            phone=u.phone,
            need=f"Khám tại phòng {payload.room_code}" if payload.room_code else "Đặt lịch khám",
            symptoms=", ".join(payload.symptoms) if payload.symptoms else None,
            hospitalId=str(hosp.id),
            hospitalName=hosp.name,
            department=dep.name,
            doctorId=str(doc.id),
            doctorName=doc.name,
            time=when_iso,
        )
        # create appointment and mark busy
        when_dt = datetime.fromisoformat(when_iso)
        end_dt = when_dt + timedelta(minutes=15)
        err = _check_slot_constraints(db, doc.id, when_dt, end_dt)
        if err:
            raise HTTPException(status_code=409, detail=err)
        # Compute STT for the day per doctor
        day_start = datetime.combine(when_dt.date(), dtime.min)
        day_end = datetime.combine(when_dt.date(), dtime.max)
        cur_stt = db.scalar(
            select(func.coalesce(func.max(Appointment.stt), 0))
            .where(Appointment.doctor_id == doc.id, Appointment.when >= day_start, Appointment.when <= day_end)
        ) or 0
        appt = Appointment(user=u, doctor_id=doc.id, when=when_dt, stt=int(cur_stt) + 1, need=bs.need, symptoms=bs.symptoms or None, content={
            "hospital": payload.hospital,
            "patient_name": payload.patient_name,
            "phone_number": payload.phone_number,
            "doctor_name": payload.doctor_name,
            "department_name": payload.department_name,
            "room_code": payload.room_code,
            "time_slot": payload.time_slot,
            "symptoms": payload.symptoms or [],
        })
    db.add(appt)
    # no linking column; we store the snapshot in appointment.content
    db.flush()
    return bs


@app.get("/api/bookings")
def list_bookings(userId: Optional[str] = Query(None)):
    try:
        with get_session() as db:
            q = select(Appointment).order_by(Appointment.created_at.desc(), Appointment.id.desc())
            if userId:
                try:
                    q = q.where(Appointment.user_id == int(userId))
                except ValueError:
                    pass
            rows = db.execute(q).scalars().all()
            out = []
            for ap in rows:
                out.append({
                    "id": ap.id,
                    "created_at": (ap.created_at or ap.when).isoformat(),
                    "stt": ap.stt,
                    "content": ap.content or {},
                })
            return out
    except ProgrammingError as e:
        # Handle case where migrations haven't created the table yet
        if "UndefinedTable" in str(e) or "relation \"appointments\" does not exist" in str(e):
            return []
        raise


@app.get("/api/bookings/{booking_id}")
def get_booking(booking_id: int):
    with get_session() as db:
        ap = db.get(Appointment, booking_id)
        if not ap:
            raise HTTPException(status_code=404, detail="Booking not found")
        return {
            "id": ap.id,
            "created_at": (ap.created_at or ap.when).isoformat(),
            "stt": ap.stt,
            "content": ap.content or {},
        }


@app.get("/api/appointments/lookup")
def lookup_appointment(doctor_id: int, start: str):
    """Lookup an appointment by doctor and start time (15-minute window).
    Returns enriched details for UI popovers.
    """
    try:
        s = datetime.fromisoformat(start)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid start time")
    e = s + timedelta(minutes=15)
    with get_session() as db:
        ap = db.execute(
            select(Appointment)
            .where(
                Appointment.doctor_id == int(doctor_id),
                Appointment.when >= s,
                Appointment.when < e,
            )
            .order_by(Appointment.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if not ap:
            return {"appointment": None}
        # Enrich with relations
        doc = db.get(Doctor, ap.doctor_id)
        dep = db.get(Department, doc.department_id) if doc else None
        hosp = db.get(Hospital, dep.hospital_id) if dep else None
        user = db.get(User, ap.user_id) if ap.user_id else None
        out = {
            "appointment": {
                "id": ap.id,
                "when": ap.when.isoformat(),
                "stt": ap.stt,
                "user": {"id": user.id, "name": user.name, "phone": user.phone} if user else None,
                "doctor": {"id": doc.id, "name": doc.name} if doc else None,
                "department": dep.name if dep else None,
                "hospital": hosp.name if hosp else None,
                "content": ap.content or {},
            }
        }
        return out


# --------- Admin helpers for content backfill ---------
@app.get("/api/_debug/all-appointments-enriched")
def all_appointments_enriched():
    with get_session() as db:
        rows = db.execute(
            select(Appointment, User, Doctor, Department, Hospital)
            .join(User, Appointment.user_id == User.id)
            .join(Doctor, Appointment.doctor_id == Doctor.id)
            .join(Department, Doctor.department_id == Department.id)
            .join(Hospital, Department.hospital_id == Hospital.id)
            .order_by(Appointment.id.asc())
        ).all()
        out = []
        for ap, u, doc, dep, hosp in rows:
            out.append({
                "id": str(ap.id),
                "when": ap.when.isoformat(),
                "stt": ap.stt,
                "user": {"id": str(u.id), "name": u.name, "phone": u.phone},
                "doctor": {"id": str(doc.id), "name": doc.name},
                "department": {"id": str(dep.id), "name": dep.name},
                "hospital": {"id": str(hosp.id), "name": hosp.name},
                "content": ap.content or None,
            })
        return {"appointments": out}

@app.post("/api/_admin/appointments/{appt_id}/content")
def set_appointment_content(appt_id: int, payload: dict):
    with get_session() as db:
        ap = db.get(Appointment, int(appt_id))
        if not ap:
            raise HTTPException(status_code=404, detail="Appointment not found")
        ap.content = payload or {}
        db.flush()
        return {"ok": True}


@app.get("/api/upcoming")
def list_upcoming(userId: Optional[str] = Query(None)):
    with get_session() as db:
        q = select(Appointment, Doctor, Department, Hospital).join(Doctor, Appointment.doctor_id == Doctor.id).join(Department, Doctor.department_id == Department.id).join(Hospital, Department.hospital_id == Hospital.id).order_by(Appointment.when.asc())
        if userId:
            q = q.where(Appointment.user_id == int(userId))
        rows = db.execute(q).all()
        return [{
            "id": str(a.id),
            "when": a.when.isoformat(),
            "stt": a.stt,
            "hospitalName": h.name,
            "department": d.name,
            "doctorName": doc.name,
        } for (a, doc, d, h) in rows]


# --------- Dev schedule APIs ---------
# Slots table removed; busy time is inferred from appointments


@app.get("/api/dev/schedule")
def dev_schedule(date_str: str, span: str = Query("day", alias="range"), hospital_id: Optional[int] = Query(None)):
    try:
        base = datetime.fromisoformat(date_str).date()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date")

    # days in range
    if span == "day":
        days = [base]
    else:
        start_week = base - timedelta(days=base.weekday())
        days = [start_week + timedelta(days=i) for i in range(7)]
    start_min = datetime.combine(days[0], dtime.min)
    end_max = datetime.combine(days[-1], dtime.max)

    with get_session() as db:
        # 1) hospitals
        qh = select(Hospital)
        if hospital_id:
            qh = qh.where(Hospital.id == int(hospital_id))
        hs = db.execute(qh).scalars().all()
        if not hs:
            return {"range": span, "days": [d.isoformat() for d in days], "hospitals": []}

        hid_list = [h.id for h in hs]

        # 2) departments of these hospitals (batch)
        deps = db.execute(
            select(Department).where(Department.hospital_id.in_(hid_list))
        ).scalars().all()
        deps_by_hid: dict[int, list[Department]] = defaultdict(list)
        for d in deps:
            deps_by_hid[d.hospital_id].append(d)

        dep_ids = [d.id for d in deps]
        if not dep_ids:
            return {"range": span, "days": [d.isoformat() for d in days],
                    "hospitals": [{"id": h.id, "name": h.name, "departments": []} for h in hs]}

        # 3) doctors (batch)
        docs = db.execute(
            select(Doctor).where(Doctor.department_id.in_(dep_ids))
        ).scalars().all()
        docs_by_dep: dict[int, list[Doctor]] = defaultdict(list)
        doc_ids: list[int] = []
        for doc in docs:
            docs_by_dep[doc.department_id].append(doc)
            doc_ids.append(doc.id)

    # 4) windows + busy (from appointments) overlap by range
        wins_by_doc: dict[int, list] = defaultdict(list)
        busy_by_doc: dict[int, list] = defaultdict(list)
        if doc_ids:
            wins = db.execute(
                select(ScheduleWindow)
                .where(
                    ScheduleWindow.doctor_id.in_(doc_ids),
                    ScheduleWindow.start < end_max,
                    ScheduleWindow.end > start_min,
                )
            ).scalars().all()
            for w in wins:
                wins_by_doc[w.doctor_id].append({"id": w.id, "start": w.start.isoformat(), "end": w.end.isoformat(), "kind": w.kind})

            # Busy blocks are 15-minute appointments
            aps = db.execute(
                select(Appointment)
                .where(
                    Appointment.doctor_id.in_(doc_ids),
                    Appointment.when < end_max,
                    Appointment.when >= (start_min - timedelta(minutes=15)),
                )
            ).scalars().all()
            for ap in aps:
                s = ap.when
                e = ap.when + timedelta(minutes=15)
                busy_by_doc[ap.doctor_id].append({"start": s.isoformat(), "end": e.isoformat()})

        # 5) compose response (no per-doctor SQL calls)
        out_h = []
        for h in hs:
            out_d = []
            for dep in deps_by_hid.get(h.id, []):
                out_docs = []
                for doc in docs_by_dep.get(dep.id, []):
                    out_docs.append({
                        "id": doc.id,
                        "name": doc.name,
                        "busy": busy_by_doc.get(doc.id, []),
                        "windows": wins_by_doc.get(doc.id, []),
                    })
                out_d.append({"id": dep.id, "name": dep.name, "doctors": out_docs})
            out_h.append({"id": h.id, "name": h.name, "departments": out_d})
        return {"range": span, "days": [d.isoformat() for d in days], "hospitals": out_h}


# dev/slots endpoints removed since slots table no longer exists


# Doctor schedule management (available / out-of-office)
class WindowUpsert(BaseModel):
    doctorId: int
    start: str
    end: str
    kind: str  # 'available' | 'ooo'


@app.put("/api/dev/windows")
def upsert_window(payload: WindowUpsert):
    if payload.kind not in ("available", "ooo"):
        raise HTTPException(status_code=400, detail="Invalid kind")
    with get_session() as db:
        s = ScheduleWindow(doctor_id=payload.doctorId, start=datetime.fromisoformat(payload.start), end=datetime.fromisoformat(payload.end), kind=payload.kind)
        # Skip if exact duplicate exists
        dup = db.execute(
            select(ScheduleWindow.id).where(
                ScheduleWindow.doctor_id == s.doctor_id,
                ScheduleWindow.kind == s.kind,
                ScheduleWindow.start == s.start,
                ScheduleWindow.end == s.end,
            )
        ).scalar_one_or_none()
        if dup:
            return {"id": dup, "skipped": True}
        # Basic rule: OOO cannot overlap Available; for this demo, we only restrict OOO overlapping existing Available
        if payload.kind == "ooo":
            overlap = db.execute(
                select(ScheduleWindow.id)
                .where(
                    ScheduleWindow.doctor_id == s.doctor_id,
                    ScheduleWindow.kind == "available",
                    ScheduleWindow.start < s.end,
                    ScheduleWindow.end > s.start,
                )
            ).first()
            if overlap:
                raise HTTPException(status_code=409, detail="Out-of-office overlaps available time")
        db.add(s)
        db.flush()
        return {"id": s.id}


@app.delete("/api/dev/windows/{window_id}")
def delete_window(window_id: int):
    with get_session() as db:
        r = db.execute(delete(ScheduleWindow).where(ScheduleWindow.id == window_id))
        if r.rowcount == 0:
            raise HTTPException(status_code=404, detail="Not found")
        return {"ok": True}


# --------- Bulk Adjust Windows (day pattern over date range) ---------
class BulkRule(BaseModel):
    start: str  # HH:MM
    end: str    # HH:MM


class BulkAdjustPayload(BaseModel):
    scopeKind: str  # 'hospital' | 'department' | 'doctor'
    scopeId: int
    dateStart: str  # YYYY-MM-DD
    dateEnd: str    # YYYY-MM-DD (inclusive)
    available: Optional[List[BulkRule]] = None
    ooo: Optional[List[BulkRule]] = None
    overwrite: bool = True


def _parse_hhmm(hhmm: str) -> tuple[int, int]:
    try:
        parts = hhmm.strip().split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        if not (0 <= h <= 24 and 0 <= m < 60):
            raise ValueError
        if h == 24 and m != 0:
            raise ValueError
        return h, m
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid time format HH:MM -> {hhmm}")


def _dt_on(day: date, hh: int, mm: int) -> datetime:
    return datetime.combine(day, dtime(hour=min(hh, 23), minute=mm if hh < 24 else 59, second=59 if hh == 24 else 0))


def _merge_intervals(iv: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    arr = sorted([(s, e) for s, e in iv if s < e], key=lambda x: x[0])
    out: list[tuple[datetime, datetime]] = []
    for s, e in arr:
        if not out:
            out.append((s, e))
        else:
            ps, pe = out[-1]
            if s <= pe:  # overlap or touch
                out[-1] = (ps, max(pe, e))
            else:
                out.append((s, e))
    return out


def _subtract(base: list[tuple[datetime, datetime]], cutters: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    # subtract cutters from base intervals, splitting as needed
    result: list[tuple[datetime, datetime]] = []
    for bs, be in base:
        cur_segments = [(bs, be)]
        for cs, ce in cutters:
            new_segments: list[tuple[datetime, datetime]] = []
            for ss, se in cur_segments:
                if ce <= ss or cs >= se:
                    new_segments.append((ss, se))  # no overlap
                else:
                    # overlap exists -> possibly split into up to two
                    if ss < cs:
                        new_segments.append((ss, max(ss, cs)))
                    if ce < se:
                        new_segments.append((min(ce, se), se))
            cur_segments = [(s, e) for s, e in new_segments if s < e]
        result.extend(cur_segments)
    return _merge_intervals(result)


def _doctors_by_scope(db, kind: str, sid: int) -> List[Doctor]:
    if kind == "doctor":
        d = db.get(Doctor, int(sid))
        return [d] if d else []
    if kind == "department":
        return db.execute(select(Doctor).where(Doctor.department_id == int(sid))).scalars().all()
    if kind == "hospital":
        return db.execute(
            select(Doctor)
            .join(Department, Doctor.department_id == Department.id)
            .where(Department.hospital_id == int(sid))
        ).scalars().all()
    raise HTTPException(status_code=400, detail="Invalid scopeKind")


@app.post("/api/dev/windows/bulk-adjust")
def bulk_adjust_windows(payload: BulkAdjustPayload):
    kind = payload.scopeKind
    if kind not in ("hospital", "department", "doctor"):
        raise HTTPException(status_code=400, detail="scopeKind must be hospital|department|doctor")
    try:
        start_date = datetime.fromisoformat(payload.dateStart).date()
        end_date = datetime.fromisoformat(payload.dateEnd).date()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date range")
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="dateEnd must be >= dateStart")

    rules_av = payload.available or []
    rules_ooo = payload.ooo or []
    # validate times
    av_pairs: list[tuple[int, int, int, int]] = []
    for r in rules_av:
        sh, sm = _parse_hhmm(r.start)
        eh, em = _parse_hhmm(r.end)
        if (eh, em) <= (sh, sm):
            raise HTTPException(status_code=400, detail=f"available start>=end: {r.start}-{r.end}")
        av_pairs.append((sh, sm, eh, em))
    ooo_pairs: list[tuple[int, int, int, int]] = []
    for r in rules_ooo:
        sh, sm = _parse_hhmm(r.start)
        eh, em = _parse_hhmm(r.end)
        if (eh, em) <= (sh, sm):
            raise HTTPException(status_code=400, detail=f"ooo start>=end: {r.start}-{r.end}")
        ooo_pairs.append((sh, sm, eh, em))

    inserted = 0
    deleted = 0
    affected_doctors = 0
    days_count = (end_date - start_date).days + 1
    with get_session() as db:
        doctors = _doctors_by_scope(db, kind, int(payload.scopeId))
        if not doctors:
            return {"ok": True, "inserted": 0, "deleted": 0, "doctors": 0, "days": days_count}
        affected_doctors = len(doctors)
        for doc in doctors:
            cur = start_date
            while cur <= end_date:
                day_start = datetime.combine(cur, dtime.min)
                day_end = datetime.combine(cur, dtime.max)
                # Build intervals on this day
                av_intv = [(_dt_on(cur, sh, sm), _dt_on(cur, eh, em)) for (sh, sm, eh, em) in av_pairs]
                ooo_intv = [(_dt_on(cur, sh, sm), _dt_on(cur, eh, em)) for (sh, sm, eh, em) in ooo_pairs]
                av_intv = _merge_intervals(av_intv)
                ooo_intv = _merge_intervals(ooo_intv)
                # Subtract OOO from available
                final_av = _subtract(av_intv, ooo_intv) if ooo_intv else av_intv
                # Overwrite existing windows in day for this doctor
                if payload.overwrite:
                    r = db.execute(
                        delete(ScheduleWindow)
                        .where(
                            ScheduleWindow.doctor_id == doc.id,
                            ScheduleWindow.start < day_end,
                            ScheduleWindow.end > day_start,
                        )
                    )
                    deleted += int(r.rowcount or 0)
                # Insert merged OOO and available
                for s, e in final_av:
                    # skip exact duplicate
                    exists = db.execute(
                        select(ScheduleWindow.id).where(
                            ScheduleWindow.doctor_id == doc.id,
                            ScheduleWindow.kind == "available",
                            ScheduleWindow.start == s,
                            ScheduleWindow.end == e,
                        )
                    ).scalar_one_or_none()
                    if not exists:
                        db.add(ScheduleWindow(doctor_id=doc.id, start=s, end=e, kind="available"))
                        inserted += 1
                for s, e in ooo_intv:
                    exists = db.execute(
                        select(ScheduleWindow.id).where(
                            ScheduleWindow.doctor_id == doc.id,
                            ScheduleWindow.kind == "ooo",
                            ScheduleWindow.start == s,
                            ScheduleWindow.end == e,
                        )
                    ).scalar_one_or_none()
                    if not exists:
                        db.add(ScheduleWindow(doctor_id=doc.id, start=s, end=e, kind="ooo"))
                        inserted += 1
                cur += timedelta(days=1)
        db.flush()
    return {"ok": True, "inserted": inserted, "deleted": deleted, "doctors": affected_doctors, "days": days_count}


# Endpoint for slots-to-appointment lookup removed


# --------- Debug ---------
@app.get("/api/_debug/db")
def debug_db():
    # Return current DB URL (sanitized), existing tables, and alembic version if any
    from backend.db import engine
    try:
        url = str(engine.url)
        if engine.url.password:
            url = url.replace(engine.url.password, "***")
    except Exception:
        url = "<unknown>"
    try:
        insp = sa_inspect(engine)
        tables = insp.get_table_names()
    except Exception as e:
        tables = [f"<inspect error: {e}"]
    version = None
    try:
        with engine.connect() as conn:
            res = conn.execute(sa_text("SELECT version_num FROM alembic_version")).fetchone()
            if res:
                version = res[0]
    except Exception:
        version = None
    return {"url": url, "tables": tables, "alembic_version": version}


@app.get("/api/_debug/which-db")
def which_db():
    with engine.connect() as c:
        ver = c.execute(sa_text("select version()")).scalar()
        db = c.execute(sa_text("select current_database()")).scalar()
        host = c.execute(sa_text("select inet_server_addr()::text")).scalar()
        # đếm nhanh một vài bảng
        counts = {}
        for t in ["hospitals","departments","doctors","rooms","schedule_windows","appointments","users"]:
            try:
                counts[t] = c.execute(sa_text(f"select count(*) from {t}")).scalar()
            except Exception:
                counts[t] = None
    return {
        "url": str(engine.url.render_as_string(hide_password=True)),
        "server": ver,
        "current_database": db,
        "server_ip": host,
        "counts": counts,
    }


# --------- Admin: Reset and Seed ---------
@app.post("/api/_admin/reset-and-seed")
def admin_reset_and_seed():
    """
    Danger: Resets all core tables and reseeds from JSON with fixed hospital IDs.
    Hospital IDs mapping:
      1: BV Nhân dân Gia Định
      2: BV đa khoa sài gòn
      3: Bệnh viện Bình Dân
    """
    from backend.seed_loader import upsert_hospitals_json
    base_dir = Path(__file__).parent
    seed_giadinh = base_dir / "seed" / "hospitals.json"
    seed_binhdan = base_dir / "seed" / "hospitals_binhdan.json"

    # 1) Truncate all related tables and restart identities
    with engine.begin() as conn:
        conn.execute(sa_text(
            "TRUNCATE TABLE appointments, schedule_windows, doctors, rooms, departments, users, hospitals RESTART IDENTITY CASCADE"
        ))

        # 2) Insert hospitals with fixed IDs
        conn.execute(sa_text(
            "INSERT INTO hospitals (id, name) VALUES (:id1, :n1), (:id2, :n2), (:id3, :n3)"
        ), {
            "id1": 1, "n1": "BV Nhân dân Gia Định",
            "id2": 2, "n2": "BV đa khoa sài gòn",
            "id3": 3, "n3": "Bệnh viện Bình Dân",
        })
        # 3) Fix sequence to MAX(id)
        try:
            conn.execute(sa_text("SELECT setval(pg_get_serial_sequence('hospitals','id'), COALESCE((SELECT MAX(id) FROM hospitals), 0))"))
        except Exception:
            pass

    # 4) Seed only from the two JSON seed files
    if seed_giadinh.exists():
        upsert_hospitals_json(seed_giadinh)
    if seed_binhdan.exists():
        upsert_hospitals_json(seed_binhdan)

    # 5) Return summary
    with get_session() as db:
        hs = db.execute(select(Hospital)).scalars().all()
        out = []
        for h in hs:
            dep_count = db.scalar(select(func.count(Department.id)).where(Department.hospital_id == h.id)) or 0
            doc_count = db.scalar(select(func.count(Doctor.id)).join(Department, Doctor.department_id == Department.id).where(Department.hospital_id == h.id)) or 0
            out.append({"id": h.id, "name": h.name, "departments": dep_count, "doctors": doc_count})
        return {"ok": True, "hospitals": out}


# --------- Admin: Flexible seeding from folder/files ---------
class SeedRequest(BaseModel):
    path: Optional[str] = None  # folder or file
    files: Optional[List[str]] = None  # explicit list of files
    pattern: str = "*.json"
    recursive: bool = False


@app.post("/api/_admin/seed")
def admin_seed(req: SeedRequest):
    """Seed from JSON:
    - if files provided: seed those
    - elif path provided: seed all JSONs under path (by pattern, optional recursive)
    - else: fallback to the two canonical files
    """
    if req.files:
        summary = seed_loader.seed_files(req.files)
        return {"ok": True, "summary": summary}
    if req.path:
        summary = seed_loader.seed_path(req.path, pattern=req.pattern or "*.json", recursive=bool(req.recursive))
        return {"ok": True, "summary": summary}
    # fallback
    summary = seed_loader.seed_two_files_only()
    return {"ok": True, "summary": summary}


# --------- Admin: Seed default weekly schedule ---------
@app.post("/api/_admin/seed-default-schedule")
def admin_seed_default_schedule(weeks: int = 1, fill_ooo: bool = False):
    """
    Create default 'available' windows for each doctor:
    - For the next `weeks` weeks starting today
    - Monday to Saturday
    - 08:00 to 17:00 local time
    Idempotent-ish: skips creating a window if one with exact (start,end,kind) already exists.
    """
    today = datetime.utcnow().date()
    end_date = today + timedelta(days=max(1, weeks) * 7)
    created = 0
    created_ooo = 0
    with get_session() as db:
        doctors = db.execute(select(Doctor)).scalars().all()
        for doc in doctors:
            cur = today
            while cur < end_date:
                # weekday: Mon=0..Sun=6; skip Sundays
                if cur.weekday() != 6:
                    start_dt = datetime.combine(cur, dtime(hour=8))
                    end_dt = datetime.combine(cur, dtime(hour=17))
                    # Check existing exact window
                    exists = db.execute(
                        select(ScheduleWindow.id)
                        .where(
                            ScheduleWindow.doctor_id == doc.id,
                            ScheduleWindow.kind == "available",
                            ScheduleWindow.start == start_dt,
                            ScheduleWindow.end == end_dt,
                        )
                    ).scalar_one_or_none()
                    if not exists:
                        db.add(ScheduleWindow(doctor_id=doc.id, start=start_dt, end=end_dt, kind="available"))
                        created += 1
                    if fill_ooo:
                        # OOO: before 08:00 and after 17:00
                        ooo1_s = datetime.combine(cur, dtime.min)
                        ooo1_e = start_dt
                        ooo2_s = end_dt
                        ooo2_e = datetime.combine(cur, dtime.max)
                        for s, e in ((ooo1_s, ooo1_e), (ooo2_s, ooo2_e)):
                            if s >= e:
                                continue
                            exists_ooo = db.execute(
                                select(ScheduleWindow.id)
                                .where(
                                    ScheduleWindow.doctor_id == doc.id,
                                    ScheduleWindow.kind == "ooo",
                                    ScheduleWindow.start == s,
                                    ScheduleWindow.end == e,
                                )
                            ).scalar_one_or_none()
                            if not exists_ooo:
                                db.add(ScheduleWindow(doctor_id=doc.id, start=s, end=e, kind="ooo"))
                                created_ooo += 1
                else:
                    # Sunday full-day OOO if requested
                    if fill_ooo:
                        s = datetime.combine(cur, dtime.min)
                        e = datetime.combine(cur, dtime.max)
                        exists_ooo = db.execute(
                            select(ScheduleWindow.id)
                            .where(
                                ScheduleWindow.doctor_id == doc.id,
                                ScheduleWindow.kind == "ooo",
                                ScheduleWindow.start == s,
                                ScheduleWindow.end == e,
                            )
                        ).scalar_one_or_none()
                        if not exists_ooo:
                            db.add(ScheduleWindow(doctor_id=doc.id, start=s, end=e, kind="ooo"))
                            created_ooo += 1
                cur += timedelta(days=1)
        db.flush()
    return {"ok": True, "created": created, "created_ooo": created_ooo}


# --------- Hospital-scoped user lists and upcoming ---------
class HospitalUsersOut(BaseModel):
    hospitals: list[dict]


@app.get("/api/hospital-users")
def list_hospital_users(hospitalId: Optional[int] = Query(None)) -> Dict[str, list[dict]]:
    """Return, per hospital, the users who have appointments with its doctors.
    Each user row includes basic info + appointment count and last appointment time in that hospital.
    """
    with get_session() as db:
        # base join
        q = (
            select(
                Hospital.id.label("hid"),
                Hospital.name.label("hname"),
                User.id.label("uid"),
                User.name.label("uname"),
                User.phone.label("uphone"),
                User.cccd.label("ucccd"),
                func.count(Appointment.id).label("acount"),
                func.max(Appointment.when).label("last_when"),
            )
            .join(Department, Department.hospital_id == Hospital.id)
            .join(Doctor, Doctor.department_id == Department.id)
            .join(Appointment, Appointment.doctor_id == Doctor.id)
            .join(User, User.id == Appointment.user_id)
            .group_by(Hospital.id, Hospital.name, User.id, User.name, User.phone, User.cccd)
            .order_by(Hospital.id.asc(), func.max(Appointment.when).desc())
        )
        if hospitalId:
            q = q.where(Hospital.id == int(hospitalId))
        rows = db.execute(q).all()
        groups: Dict[int, dict] = {}
        for hid, hname, uid, uname, uphone, ucccd, acount, last_when in rows:
            g = groups.setdefault(hid, {"id": hid, "name": hname, "users": []})
            g["users"].append({
                "id": str(uid),
                "name": uname,
                "phone": uphone,
                "cccd": ucccd,
                "appointments": int(acount or 0),
                "last_when": last_when.isoformat() if last_when else None,
            })
        # ensure hospitals with no users still appear if filtered by a specific hospital
        if hospitalId and not groups.get(int(hospitalId)):
            h = db.get(Hospital, int(hospitalId))
            if h:
                groups[int(hospitalId)] = {"id": h.id, "name": h.name, "users": []}
        return {"hospitals": list(groups.values())}


@app.get("/api/hospital-user-profile")
def get_hospital_user_profile(hospitalId: int, userId: int):
    """Profile for a user constrained to one hospital: basic user info + all their appointments at this hospital."""
    with get_session() as db:
        h = db.get(Hospital, int(hospitalId))
        if not h:
            raise HTTPException(status_code=404, detail="Hospital not found")
        u = db.get(User, int(userId))
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        # appointments at hospital
        q = (
            select(Appointment, Doctor, Department)
            .join(Doctor, Appointment.doctor_id == Doctor.id)
            .join(Department, Doctor.department_id == Department.id)
            .where(Appointment.user_id == u.id, Department.hospital_id == h.id)
            .order_by(Appointment.when.desc())
        )
        rows = db.execute(q).all()
        appts = [{
            "id": ap.id,
            "when": ap.when.isoformat(),
            "stt": ap.stt,
            "doctorName": doc.name,
            "department": dep.name,
            "content": ap.content or {},
        } for (ap, doc, dep) in rows]
        # Note: BHYT is not modeled in DB; return None to keep the shape
        return {
            "hospital": {"id": h.id, "name": h.name},
            "user": {"id": str(u.id), "name": u.name, "phone": u.phone, "cccd": getattr(u, "cccd", None), "bhyt": None},
            "appointments": appts,
        }


@app.get("/api/hospitals/upcoming")
def list_upcoming_by_hospital():
    """Upcoming appointments grouped by hospital from "now" forward."""
    now = datetime.utcnow()
    with get_session() as db:
        q = (
            select(Appointment, User, Doctor, Department, Hospital)
            .join(User, Appointment.user_id == User.id)
            .join(Doctor, Appointment.doctor_id == Doctor.id)
            .join(Department, Doctor.department_id == Department.id)
            .join(Hospital, Department.hospital_id == Hospital.id)
            .where(Appointment.when >= now)
            .order_by(Hospital.id.asc(), Appointment.when.asc())
        )
        rows = db.execute(q).all()
        groups: Dict[int, dict] = {}
        for ap, user, doc, dep, hosp in rows:
            g = groups.setdefault(hosp.id, {"id": hosp.id, "name": hosp.name, "appointments": []})
            g["appointments"].append({
                "id": str(ap.id),
                "when": ap.when.isoformat(),
                "stt": ap.stt,
                "user": {"id": str(user.id), "name": user.name, "phone": user.phone},
                "department": dep.name,
                "doctorName": doc.name,
            })
        return {"hospitals": list(groups.values())}


# --------- Rooms API (for seeding & lookups) ---------
@app.get("/api/rooms")
def list_rooms(hospital_id: Optional[int] = Query(None), department_id: Optional[int] = Query(None)):
    """List rooms, optionally filtered by hospital or department."""
    with get_session() as db:
        q = select(Room)
        if department_id:
            q = q.where(Room.department_id == int(department_id))
        if hospital_id:
            q = q.where(Room.hospital_id == int(hospital_id))
        rows = db.execute(q.order_by(Room.hospital_id.asc(), Room.department_id.asc(), Room.code.asc())).scalars().all()
        return [{
            "id": r.id,
            "hospital_id": r.hospital_id,
            "department_id": r.department_id,
            "code": r.code,
            "name": r.name,
        } for r in rows]


# --------- Helpers ---------
def _check_slot_constraints(db, doctor_id: int, start_dt: datetime, end_dt: datetime) -> Optional[str]:
    """Return None if slot is valid, or an error message string otherwise."""
    # Must be fully covered by an available window
    avail = db.execute(
        select(ScheduleWindow.id)
        .where(
            ScheduleWindow.doctor_id == doctor_id,
            ScheduleWindow.kind == "available",
            ScheduleWindow.start <= start_dt,
            ScheduleWindow.end >= end_dt,
        )
        .limit(1)
    ).scalar_one_or_none()
    if not avail:
        return "Thời gian này không nằm trong khung giờ làm việc (available) của bác sĩ"

    # Must not overlap an OOO window
    ooo_overlap = db.execute(
        select(ScheduleWindow.id)
        .where(
            ScheduleWindow.doctor_id == doctor_id,
            ScheduleWindow.kind == "ooo",
            ScheduleWindow.start < end_dt,
            ScheduleWindow.end > start_dt,
        )
        .limit(1)
    ).scalar_one_or_none()
    if ooo_overlap:
        return "Khung giờ này trùng thời gian out-of-office của bác sĩ"

    # Must not overlap existing appointment (15-minute busy)
    busy_appt = db.execute(
        select(Appointment.id)
        .where(
            Appointment.doctor_id == doctor_id,
            Appointment.when < end_dt,
            Appointment.when > (start_dt - timedelta(minutes=15)),
        )
        .limit(1)
    ).scalar_one_or_none()
    if busy_appt:
        return "Khung giờ này đã có bệnh nhân đặt"
    return None

