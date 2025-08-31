Medly backend quickstart

- Env: set DATABASE_URL or DB_* vars; see backend/db.py.
- Install deps: pip install -r backend/requirements.txt
- Migrations: cd backend; alembic upgrade head
- Seed data: on app startup, it loads backend/seed/hospitals.json and optionally backend/seed/doctors_BinhDanHos_grouped.json for "Bệnh viện Bình Dân".
- APIs: see backend/main.py for routes.
