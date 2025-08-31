## Backend (FastAPI + PostgreSQL)

1) Create and activate venv
2) pip install -r backend/requirements.txt
3) Set DATABASE_URL in backend/.env (copy backend/.env.example)
4) Run migrations: alembic upgrade head
5) Start server: uvicorn backend.main:app --reload

### Seeding hospitals/departments/doctors via YAML

- Place a YAML file at `backend/seed/hospitals.yaml` (sample provided) or set an environment variable `SEED_YAML` to an absolute path of your YAML file.
- On first startup, the app will read the YAML and idempotently upsert Hospitals, Departments, and Doctors.
- If the YAML is missing or fails to load, a tiny built-in sample seed is applied.

YAML shape:

```yaml
hospitals:
	- name: "Hospital A"
		departments:
			- name: "Cardiology"
				doctors:
					- name: "Dr. Alice"
					- name: "Dr. Bob"
```
This is a mobile-first Next.js app with a voice agent that helps book hospital appointments. Frontend: Next 15 + React 19 + Tailwind v4. Backend: Python FastAPI (stub, in-memory), database placeholder for PostgreSQL 17.

Quick start

Frontend

1. Create a `.env.local` file and set the backend URL (default matches local backend):

	NEXT_PUBLIC_BACKEND_URL=http://localhost:8000

2. Install and run dev server:

	npm install
	npm run dev

Backend (Python 3.12)

1. Create venv and install deps:

	python -m venv .venv
	.\.venv\Scripts\activate
	pip install -r backend/requirements.txt

2. Setup database (PostgreSQL 17):

	- Create database `medly` and user if needed.
	- Copy env: `cp backend/.env.example backend/.env` and adjust.

3. Run migrations:

	$env:DATABASE_URL=(Get-Content backend/.env | ForEach-Object { if($_ -match "^DATABASE_URL=") { ($_ -split '=',2)[1] } })
	alembic -c backend/alembic.ini upgrade head

4. Run server:

	uvicorn backend.main:app --reload --port 8000

Pages

- /: Voice agent flow
- /history: Booking history (conversation summaries)
- /upcoming: Upcoming appointments
- /conversations: Conversation history list
- /dev: Dev mode schedule grid (placeholder UI)
	- API: GET /api/dev/schedule?date=YYYY-MM-DD&range=day|week, PUT /api/dev/slots, DELETE /api/dev/slots/{id}
	- UI sẽ được nâng cấp để hỗ trợ drag-resize trên desktop.

Database

- Currently using in-memory stores. Replace with PostgreSQL 17 later.

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
