from __future__ import annotations

from typing import Dict, Any, Optional, List, Union
from pathlib import Path
import json

from sqlalchemy import select

from backend.db import get_session
from backend.models import Hospital, Department, Doctor, Room


def load_json(file_path: str | Path) -> Dict[str, Any]:
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Seed file not found: {file_path}")
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("Seed JSON must be an object with key 'hospitals'")
    return data


def _coerce_phone(val: Any) -> Optional[str]:
    if val is None:
        return None
    s = "".join(ch for ch in str(val) if ch.isdigit())
    return s or None


def upsert_hospitals_json(file_path: str | Path) -> Dict[str, int]:
    """Load a hospitals.json-style file and upsert hospitals, departments, rooms, and doctors.

    Expected schema:
    {
      "hospitals": [
        {
          "name": str,
          "departments": [
            {
              "name": str,
              "rooms": [ { "code": str, "name": Optional[str] } | str, ...],
              "doctors": [ { "name": str, "role": Optional[str], "phone": Optional[str] }, ...]
            }
          ]
        }
      ]
    }
    """
    data = load_json(file_path)
    hospitals = data.get("hospitals", [])
    if not isinstance(hospitals, list):
        raise ValueError("'hospitals' must be a list")

    stats = {"hospitals": 0, "departments": 0, "doctors": 0, "rooms": 0}
    with get_session() as db:
        for h in hospitals:
            if not isinstance(h, dict):
                continue
            h_name = str(h.get("name", "")).strip()
            if not h_name:
                continue
            hosp = db.execute(select(Hospital).where(Hospital.name == h_name)).scalars().first()
            if not hosp:
                hosp = Hospital(name=h_name)
                db.add(hosp)
                db.flush()
                stats["hospitals"] += 1

            for d in h.get("departments", []) or []:
                if not isinstance(d, dict):
                    continue
                d_name = str(d.get("name", "")).strip()
                if not d_name:
                    continue
                dep = db.execute(
                    select(Department).where(Department.hospital_id == hosp.id, Department.name == d_name)
                ).scalars().first()
                if not dep:
                    dep = Department(name=d_name, hospital_id=hosp.id)
                    db.add(dep)
                    db.flush()
                    stats["departments"] += 1

                # doctors
                for doc in d.get("doctors", []) or []:
                    if not isinstance(doc, dict):
                        continue
                    doc_name = str(doc.get("name", "")).strip()
                    if not doc_name:
                        continue
                    role_val = str(doc.get("role", "")).strip() or None
                    phone_val = _coerce_phone(doc.get("phone"))
                    existing = db.execute(
                        select(Doctor).where(Doctor.department_id == dep.id, Doctor.name == doc_name)
                    ).scalars().first()
                    if not existing:
                        roles_payload = [role_val] if role_val else None
                        db.add(Doctor(name=doc_name, department_id=dep.id, phone=phone_val, roles=roles_payload))
                        stats["doctors"] += 1
                    else:
                        if phone_val and getattr(existing, "phone", None) != phone_val:
                            existing.phone = phone_val
                        if role_val:
                            roles = list(existing.roles or [])
                            if role_val not in roles:
                                roles.append(role_val)
                                existing.roles = roles

                # rooms
                for rm in d.get("rooms", []) or []:
                    code = None
                    name = None
                    if isinstance(rm, str):
                        code = rm.strip()
                    elif isinstance(rm, dict):
                        code = str(rm.get("code", "")).strip()
                        name = str(rm.get("name")) if rm.get("name") else None
                    if not code:
                        continue
                    existing_room = db.execute(
                        select(Room).where(Room.hospital_id == hosp.id, Room.code == code)
                    ).scalars().first()
                    if not existing_room:
                        db.add(Room(department_id=dep.id, hospital_id=hosp.id, code=code, name=name))
                        stats["rooms"] += 1
                    else:
                        if existing_room.department_id != dep.id:
                            existing_room.department_id = dep.id
                        if name and existing_room.name != name:
                            existing_room.name = name
    return stats


def seed_two_files_only() -> Dict[str, Dict[str, int]]:
    """Load exactly backend/seed/hospitals.json and backend/seed/hospitals_binhdan.json, if present."""
    base = Path(__file__).resolve().parent / "seed"
    out: Dict[str, Dict[str, int]] = {}
    gd = base / "hospitals.json"
    if gd.exists():
        out["hospitals.json"] = upsert_hospitals_json(gd)
    bd = base / "hospitals_binhdan.json"
    if bd.exists():
        out["hospitals_binhdan.json"] = upsert_hospitals_json(bd)
    return out


# -------- Flexible seeding utilities --------
def seed_files(files: List[Union[str, Path]]) -> Dict[str, Any]:
    """Seed from a list of JSON files. Returns per-file stats or error.

    Each file is expected to follow the hospitals.json schema.
    """
    summary: Dict[str, Any] = {}
    for f in files:
        p = Path(f)
        key = p.name
        if not p.exists():
            summary[key] = {"error": f"missing: {p}"}
            continue
        try:
            summary[key] = upsert_hospitals_json(p)
        except Exception as e:
            summary[key] = {"error": str(e)}
    return summary


def seed_path(path: Union[str, Path], pattern: str = "*.json", recursive: bool = False) -> Dict[str, Any]:
    """Seed all JSON files under a path (file or directory).

    - If path is a file: seed just that file.
    - If directory: glob by pattern (non-recursive by default).
    """
    p = Path(path)
    if p.is_file():
        return seed_files([p])
    if not p.exists():
        return {"error": f"path not found: {p}"}
    files = list(p.rglob(pattern) if recursive else p.glob(pattern))
    # stable order
    files = sorted(files)
    return seed_files(files)
