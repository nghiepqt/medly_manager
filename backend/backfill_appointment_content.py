import os
from datetime import datetime
import requests

BASE_URL = os.getenv("MEDLY_API", "http://localhost:8000")


def api(path: str) -> str:
    return f"{BASE_URL}{path if path.startswith('/') else '/' + path}"


def list_enriched(limit: int | None = None):
    # Reuse existing /api/hospitals/upcoming shape plus history, but we need all; we add a new helper endpoint instead
    r = requests.get(api("/api/_debug/all-appointments-enriched"), timeout=60)
    r.raise_for_status()
    data = r.json()
    rows = data.get("appointments", [])
    return rows[:limit] if limit else rows


def get_random_room_code(dep_id: int | None) -> str | None:
    if not dep_id:
        return None
    try:
        r = requests.get(api("/api/rooms"), params={"department_id": str(dep_id)}, timeout=20)
        if r.ok:
            items = r.json()
            if isinstance(items, list) and items:
                return (items[0 if len(items)==1 else __import__('random').randint(0, len(items)-1)]).get("code")
    except Exception:
        pass
    return None


def build_content(row: dict) -> dict:
    # row contains: id, when, user, doctor, department, hospital
    ap_when = row.get("when")
    hname = (row.get("hospital") or {}).get("name")
    dname = (row.get("doctor") or {}).get("name")
    dep = (row.get("department") or {})
    depname = dep.get("name")
    dep_id = dep.get("id")
    uname = (row.get("user") or {}).get("name")
    uphone = (row.get("user") or {}).get("phone")
    room = get_random_room_code(int(dep_id)) if dep_id is not None else None
    if not room:
        room = "R101"
    # Construct snapshot same shape as the sample
    content = {
        "hospital": hname,
        "patient_name": uname,
        "phone_number": uphone,
        "doctor_name": dname,
        "department_name": depname,
        "room_code": room,
        "time_slot": ap_when,
        "symptoms": [],
    }
    # preserve existing symptoms if any
    old = row.get("content") or {}
    if isinstance(old, dict) and isinstance(old.get("symptoms"), list) and old.get("symptoms"):
        content["symptoms"] = old["symptoms"]
    return content


def update_content(appt_id: int, content: dict):
    r = requests.post(api(f"/api/_admin/appointments/{appt_id}/content"), json=content, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    rows = list_enriched()
    updated = 0
    for r in rows:
        apid = int(r["id"])
        content = build_content(r)
        update_content(apid, content)
        updated += 1
        print(f"Updated appointment {apid}")
    print(f"Backfill done. Updated: {updated}")


if __name__ == "__main__":
    main()
