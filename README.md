# Medly Manager — Medical Booking System

Mobile‑first appointment booking and schedule management for hospitals and clinics.

- Frontend: Next.js App Router + React + Tailwind CSS (mobile‑first UX)
- Backend: FastAPI + SQLAlchemy + PostgreSQL


## Features

- 15‑minute appointment booking with server‑side validation
	- Must fall inside doctor “available” windows
	- Must not overlap “out‑of‑office” (OOO) windows
	- Must not collide with existing appointments (busy derived from appointments)
- Day/week scheduler for admins
	- Drag to select, drag/resize windows, multi‑select doctors (Explorer‑style)
	- Bulk adjust available/OOO by hospital/department/doctor over date ranges
	- Auto‑refresh every 5 minutes; background toast
- “Giấy hẹn khám” printable slip for user appointments
- Sequence number (STT) per doctor per day, auto‑assigned on creation
- Seed/reset utilities and debug endpoints


## Repository layout

- `backend/` — FastAPI app, models, migrations, seed utilities
- `src/` — Next.js frontend (App Router)
- Root config files: `package.json`, `eslint.config.mjs`, `postcss.config.mjs`, `tsconfig.json`, etc.


## Prerequisites

- Node.js 18+ (or 20+ recommended)
- Python 3.11+ (3.12 OK)
- PostgreSQL 14+ (17 OK)
- Windows PowerShell (examples use PowerShell commands)


## Quick start (Windows)

1) Backend: create venv and install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

2) Database: configure env and migrate

```powershell
# Create a DB and user as needed, then set DATABASE_URL in backend/.env
Copy-Item backend/.env.example backend/.env
# Edit backend/.env and set e.g.:
# DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/medly

# Run Alembic migrations
$env:DATABASE_URL = (Get-Content backend/.env | Where-Object { $_ -match '^DATABASE_URL=' } | ForEach-Object { ($_ -split '=',2)[1] })
alembic -c backend/alembic.ini upgrade head
```

3) Start backend server

```powershell
uvicorn backend.main:app --reload --port 8000
```

4) Frontend: configure and run

```powershell
# In project root
Set-Content -Path .env.local -Value "NEXT_PUBLIC_BACKEND_URL=http://localhost:8000"
npm install
npm run dev
# Open http://localhost:3000
```


## Backend details

### Environment

- `backend/.env` with `DATABASE_URL` (PostgreSQL)
- CORS is open during development

### Models (simplified)

- Hospital(id, name, address?)
- Department(id, hospital_id, name)
- Doctor(id, department_id, name, phone?, roles?)
- User(id, name, phone, cccd?)
- Appointment(id, user_id, doctor_id, when, stt, need?, symptoms?, created_at, content JSON)
- ScheduleWindow(id, doctor_id, start, end, kind: available|ooo)
- Room(id, hospital_id, department_id, code, name?)

Notes:
- Busy is derived from Appointment (15‑minute blocks). Slots table is not used.
- STT (sequence number) is computed per doctor per day when an appointment is created. A startup best‑effort migration backfills missing STT.

### Seeding and utilities

- On startup, the backend will seed from two canonical JSON files if present
	(via `seed_two_files_only`).
- Admin endpoints:
	- POST `/api/_admin/reset-and-seed` — reset core tables and reseed hospitals/departments/doctors
	- POST `/api/_admin/seed-default-schedule?weeks=1&fill_ooo=true` — create default working hours and optional OOO
	- POST `/api/_admin/seed` — flexible seeding from files/folders
- Dev schedule windows:
	- GET `/api/dev/schedule?date_str=YYYY-MM-DD&range=day|week[&hospital_id=ID]`
	- PUT `/api/dev/windows` — upsert a single window (available|ooo)
	- DELETE `/api/dev/windows/{id}` — delete a window
	- POST `/api/dev/windows/bulk-adjust` — bulk rules over a date range
- Content backfill (snapshot JSON in Appointment.content):
	- GET `/api/_debug/all-appointments-enriched`
	- POST `/api/_admin/appointments/{id}/content` — overwrite content for an appointment
- Rooms lookup:
	- GET `/api/rooms[?hospital_id=..&department_id=..]`

### Core booking endpoints (high‑level)

- POST `/api/users` — create/fetch by phone and name
- POST `/api/book` — create a booking (15‑minute)
- POST `/api/bookings` — external ingest (ensures entities), stores a content snapshot
- GET `/api/bookings[?userId=]` — list bookings (id, created_at, stt, content)
- GET `/api/bookings/{id}` — booking detail (id, created_at, stt, content)
- GET `/api/appointments/lookup?doctor_id=&start=` — find appointment in a 15‑minute window
- GET `/api/upcoming[?userId=]` — upcoming appointments (includes stt)
- GET `/api/hospital-users[?hospitalId=]` — users with appointments in each hospital
- GET `/api/hospital-user-profile?hospitalId=&userId=` — profile + appointments in that hospital (includes stt)
- GET `/api/hospitals/upcoming` — upcoming by hospital (includes stt)

Validation rules enforced by the server:
1) The 15‑minute slot must be fully inside at least one Available window
2) Must not overlap any OOO window
3) Must not overlap any existing appointment (busy)


## Frontend details

- Next.js App Router app in `src/app`
- Pages of note:
	- `/dev` — Admin schedule grid (day/week), drag‑resize, multi‑select, bulk adjust
	- `/user-appointments` — Hospitals → users; profile view renders a printable “Giấy hẹn khám” slip; shows STT when available
	- Other supporting pages (history, conversations) may be stubs or WIP
- Configure backend base URL via `.env.local`:
	- `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000`
	- The frontend prefers relative `/api` rewrites when available

Scheduler UI hints:
- Day view (24h): double‑click to create a 60‑minute Available block, drag to select any span, drag/resize existing blocks (15‑minute snapping)
- Multi‑select doctors with Ctrl/Cmd and Shift (range in same department)
- Fixed action bar offers “Điều chỉnh” (bulk adjust) and “Xóa” of existing windows


## Scripts (optional)

Some helper scripts live in `backend/` (if present in your branch):

- `seed_demo_users_and_appointments.py` — creates demo users and valid appointments next week
- `backfill_appointment_content.py` — rebuilds Appointment.content for all records

Run with:

```powershell
cd backend
py seed_demo_users_and_appointments.py
py backfill_appointment_content.py
```


## Troubleshooting

- SQLAlchemy/psycopg import errors in editor
	- Ensure you’ve activated the venv where dependencies are installed
- Cannot connect to Postgres
	- Verify `DATABASE_URL` and that the database exists and is reachable
- New endpoints 404 after code change
	- Restart the backend development server
- Timezone drift
	- The system uses local‑naive ISO strings on the admin UI; the API treats appointment windows as local time ranges


## License

Proprietary — internal project. Do not distribute.
