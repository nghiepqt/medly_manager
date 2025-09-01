Medly backend quickstart

- Env: set DATABASE_URL or DB_* vars; see backend/db.py.
- Install deps: pip install -r backend/requirements.txt
- Migrations: cd backend; alembic upgrade head (if use new database) hoặc hỏi tao để xem t đào được cái link database k nhé =))
- Seed data: on app startup, it loads 2 json files in backend/seed/hospitals, nhưng t xoá script đó rồi
- APIs: see backend/main.py for routes.
