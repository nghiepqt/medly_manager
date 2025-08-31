import os
import random
import string
from datetime import datetime, timedelta
import requests

# Config
BASE_URL = os.getenv("MEDLY_API", "http://localhost:8000")
RANDOM_SEED = int(os.getenv("SEED", "42"))
USERS_COUNT = int(os.getenv("USERS", "10"))
APPTS_PER_USER = int(os.getenv("APPTS", "3"))

random.seed(RANDOM_SEED)


def api(path: str) -> str:
    return f"{BASE_URL}{path if path.startswith('/') else '/' + path}"


def fetch_schedule_week(start_date: datetime, hospital_id: int | None = None):
    params = {
        "date_str": start_date.strftime("%Y-%m-%d"),
        "range": "week",
    }
    if hospital_id:
        params["hospital_id"] = str(hospital_id)
    r = requests.get(api("/api/dev/schedule"), params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def create_or_fetch_user(name: str, phone: str, cccd: str | None):
    r = requests.post(api("/api/users"), json={"name": name, "phone": phone, "cccd": cccd}, timeout=30)
    r.raise_for_status()
    return r.json()  # {id, phone, name}


def ingest_booking(payload_json: dict):
    """Create appointment via /api/bookings which persists the JSON snapshot in Appointment.content."""
    r = requests.post(api("/api/bookings"), json=payload_json, timeout=30)
    if r.status_code == 409:
        return None
    r.raise_for_status()
    return r.json()


def to_local_naive_iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def name_generator() -> str:
    first = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng"]
    middle = ["Văn", "Thị", "Hữu", "Ngọc", "Gia", "Minh", "Quang", "Tuấn", "Thanh", "Hải"]
    last = ["Anh", "Bình", "Cường", "Dũng", "Đạt", "Huy", "Khoa", "Linh", "My", "Trang", "Vy", "Nam"]
    return f"{random.choice(first)} {random.choice(middle)} {random.choice(last)}"


def phone_generator(existing: set[str]) -> str:
    while True:
        # 10-digit VN-like number starting with 09 or 03
        prefix = random.choice(["09", "03", "08"])  # common prefixes
        rest = "".join(random.choices(string.digits, k=8))
        phone = prefix + rest
        if phone not in existing:
            existing.add(phone)
            return phone


def cccd_generator(existing: set[str]) -> str:
    while True:
        c = "".join(random.choices(string.digits, k=12))
        if c not in existing:
            existing.add(c)
            return c


SYMPTOMS_POOL = [
    "Ho khan",
    "Sốt nhẹ",
    "Đau đầu",
    "Đau họng",
    "Mệt mỏi",
    "Đau bụng",
    "Chóng mặt",
    "Hắt hơi",
    "Nghẹt mũi",
    "Đau lưng",
]


def random_symptoms() -> list[str]:
    k = random.randint(1, 3)
    return random.sample(SYMPTOMS_POOL, k)


def minutes(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute


def collect_free_slots_for_doctor(doc: dict, days: list[str]) -> list[datetime]:
    """Return list of candidate 15-min start times within next week for a doctor based on windows minus busy."""
    busy = [(datetime.fromisoformat(b["start"]), datetime.fromisoformat(b["end"])) for b in doc.get("busy", [])]
    windows = [(datetime.fromisoformat(w["start"]), datetime.fromisoformat(w["end"])) for w in doc.get("windows", []) if w.get("kind") == "available"]
    busy.sort()
    candidates: list[datetime] = []
    for day in days:
        day_start = datetime.fromisoformat(day + "T00:00:00")
        day_end = datetime.fromisoformat(day + "T23:59:59")
        # windows intersecting this day
        for ws, we in windows:
            s = max(ws, day_start)
            e = min(we, day_end)
            if e <= s:
                continue
            # 15-min grid
            cur = s.replace(second=0, microsecond=0)
            # round up to next 15-min
            add = (15 - (minutes(cur) % 15)) % 15
            cur = cur + timedelta(minutes=add)
            while cur + timedelta(minutes=15) <= e:
                ce = cur + timedelta(minutes=15)
                # check overlap busy
                overlapped = any(not (ce <= bs or cur >= be) for bs, be in busy)
                if not overlapped:
                    candidates.append(cur)
                cur += timedelta(minutes=15)
    # Shuffle for randomness
    random.shuffle(candidates)
    return candidates


def main():
    today = datetime.now().date()
    sched = fetch_schedule_week(datetime.combine(today, datetime.min.time()))
    hospitals = sched.get("hospitals", [])
    days = sched.get("days", [])
    if not hospitals or not days:
        print("No hospitals or days returned; is the backend running and seeded?")
        return

    # Build quick index: hospital -> departments -> doctors; doctor id -> (hospital, department, doctor)
    all_docs = []
    for h in hospitals:
        for dep in h.get("departments", []):
            for doc in dep.get("doctors", []):
                all_docs.append((h, dep, doc))

    if not all_docs:
        print("No doctors found; seed hospitals/departments/doctors first.")
        return

    used_phones: set[str] = set()
    used_cccd: set[str] = set()
    created = []

    for i in range(USERS_COUNT):
        name = name_generator()
        phone = phone_generator(used_phones)
        cccd = cccd_generator(used_cccd)
        user = create_or_fetch_user(name, phone, cccd)
        uid = user["id"]

        # pick a random hospital for this user
        hosp = random.choice(hospitals)
        hosp_name = hosp["name"]
        hosp_id = int(hosp["id"])
        # prepare candidate doctors in this hospital
        hosp_docs = []
        for dep in hosp.get("departments", []):
            for doc in dep.get("doctors", []):
                hosp_docs.append((dep, doc))
        if not hosp_docs:
            # fallback to any doctor
            dep, doc = random.choice([(d, c) for (_, d, c) in all_docs])
        # Choose appointments
        appt_jsons = []
        created_count = 0
        protection_seen_slots: set[str] = set()  # doctor_id@iso
        tries = 0
        while created_count < APPTS_PER_USER and tries < 100:
            tries += 1
            dep, doc = random.choice(hosp_docs)
            # pick a random room in this department if available
            room_code = None
            try:
                rr = requests.get(api("/api/rooms"), params={"department_id": str(dep["id"])}, timeout=20)
                if rr.ok:
                    lst = rr.json()
                    if isinstance(lst, list) and lst:
                        room_code = random.choice(lst).get("code")
            except Exception:
                pass
            # compute free slots for this doc
            free_slots = collect_free_slots_for_doctor(doc, days)
            if not free_slots:
                continue
            random_slot = random.choice(free_slots)
            key = f"{doc['id']}@{to_local_naive_iso(random_slot)}"
            if key in protection_seen_slots:
                continue
            protection_seen_slots.add(key)
            # Build JSON content
            payload_json = {
                "hospital": hosp_name,
                "patient_name": name,
                "phone_number": phone,
                "doctor_name": doc["name"],
                "department_name": dep["name"],
                "room_code": room_code or f"R{random.randint(101, 399)}",
                "time_slot": to_local_naive_iso(random_slot),
                "symptoms": random_symptoms(),
            }
            # Create via /api/bookings to store content JSON
            ok = ingest_booking(payload_json)
            if ok is None:
                # conflict; try again
                continue
            created_count += 1
            appt_jsons.append(payload_json)

        created.append({
            "user": user,
            "hospital": {"id": hosp_id, "name": hosp_name},
            "appointments": appt_jsons,
        })
        print(f"Created user {i+1}/{USERS_COUNT}: {name} ({phone}) -> {created_count} appts")

    # Summary
    total_appts = sum(len(x["appointments"]) for x in created)
    print(f"Done. Users: {len(created)}, Appointments created: {total_appts}")


if __name__ == "__main__":
    main()
