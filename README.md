# ThermoVolt - standalone fleet thermal monitoring

Latest update: see COMBINED-UPDATE.md for public registration approval,
account controls, audit logs, date-range export, AI assistant configuration
and one-minute audible alert reminders. The earlier five-car-only instructions
below describe the default profiles; additional approved vehicles are supported.

## Admin registration update

See ADMIN-UPDATE.md for GitHub/Render upgrade steps. Add ADMIN_USERNAME=admin
and your own ADMIN_PASSWORD (at least 10 characters) in Render's Environment.
Click Administrator access on the login screen. Admins can list all registered
vehicles, open their monitoring pages, and create more vehicle/user accounts.
The existing five accounts and database readings are retained.
Each new profile persists in fleet_profiles and automatically joins the writer.
Vehicle PINs are hashed. The admin password stays in the server environment.
Do not run the old hosted-source synchronization helper over frontend/ because
the standalone frontend now includes additional administration functionality.

All source code is included. The application runs on your own computer at
http://127.0.0.1:5050 with ordinary Vehicle ID/PIN login. It has no external
sign-in or cloud account dependency. Use this folder as your VS Code project.

## Automatic fleet

| Vehicle ID | PIN | Model | Assigned condition |
| --- | --- | --- | --- |
| TV-URBAN-01 | 1842 | Eon City | Healthy city driving |
| TV-FAMILY-02 | 2764 | Aster X7 | Hot weather, environmental warning |
| TV-SPORT-03 | 3907 | Veloce S | Sustained discharge load, load warning |
| TV-TRACK-04 | 4518 | Ion R9 | Cell hotspot, temperature/spread warning |
| TV-FLEET-05 | 5683 | Carry E5 | Coolant-flow loss, critical flow alert |

All five cars start together. No condition selection is needed. The background
writer adds one reading per car every three seconds while the backend runs,
even if you close your browser or log out. One sample advances twenty simulated
seconds. Values vary smoothly within each assigned condition. The readings are
synthetic; these are controlled monitoring scenarios, not measured car data.
The four abnormal cars have alerts on startup; the urban car remains healthy.
Local records are retained until you explicitly remove them. The dashboard
loads the latest 120 readings and displays the latest 36 in charts.

## 1. Run on your Mac immediately

Requires Python 3.11+ and a C compiler (Apple Command Line Tools).
Open the extracted folder in VS Code. In its terminal run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5050 and enter one Vehicle ID and its PIN above.
The compiled frontend is included in `web/`, so Node is optional for running.
`bash start.command` performs these setup steps too. If `cc` is missing, run
`xcode-select --install` on your Mac and retry. Stop with Ctrl+C; restart using
`source .venv/bin/activate` then `python app.py`. History persists across restarts.

Without a DATABASE_URL the app uses a local SQLite file. That is the quickest
first launch. Follow the next section to use PostgreSQL for your DBMS work.

## 2. Connect your existing PostgreSQL

In pgAdmin, create a login role `thermovolt` with your own password and create
a database `thermovolt` owned by that role. Create a `.env` file in this folder
from `.env.example` and change its connection URL:

```bash
cp .env.example .env
```

```text
DATABASE_URL=postgresql://thermovolt:YOUR_PASSWORD@localhost:5432/thermovolt
HOST=127.0.0.1
PORT=5050
```

Restart `python app.py`. Tables are initialized automatically from
`sql/postgres.sql`. If your password includes @, :, /, # or %, percent-encode
those characters in the URL. Your existing pgAdmin username can be used instead
of `thermovolt` if it owns the database. Never include your actual `.env` when
sharing the project.

Verify live records in pgAdmin:

```sql
SELECT vehicle_id, COUNT(*) AS readings, MAX(observed_at) AS latest
FROM fleet_readings GROUP BY vehicle_id ORDER BY vehicle_id;

SELECT vehicle_id, severity, title, status
FROM fleet_alerts WHERE status = 'active' ORDER BY vehicle_id;
```

Run the first query again after a few seconds: counts rise for all five cars.
SQLite and PostgreSQL are separate stores; switching does not migrate old rows.

## 3. Optional: automatic PostgreSQL setup with Docker

Install and open Docker Desktop. Create `.env` from the example and replace
`DB_PASSWORD=change-this-password` with your own alphanumeric password. Then:

```bash
docker compose up --build -d
```

Open http://127.0.0.1:5050. PostgreSQL and the app start together. The database
uses a persistent volume. Stop with `docker compose down` (without `-v`, so
the data remains). You do not need a separately installed PostgreSQL for this
option. The direct Python option and Docker option should not run on port 5050
at the same time.

## 4. Edit the website in VS Code

All React/TypeScript/CSS source is in `frontend/`. Requires Node 22.13+:

```bash
cd frontend
npm install
npm run dev
```

Keep Python running in another terminal. Vite prints its development URL and
forwards `/api` to the Python backend. After edits:

```bash
npm run build
```

This rebuilds `web/`. Return to http://127.0.0.1:5050 and refresh.
Conditions are assigned in `thermovolt/fleet.py` (`AUTOMATIC`). Names/models and
frontend identities are in `frontend/lib/fleet.ts`; keep IDs in both files
consistent. Every source file needed to rebuild the website is included.

## 5. Deploy independently

Localhost is accessible on your own laptop. For a public URL you need a host
that runs Python and PostgreSQL. This folder is independent of the preview
hosting service. Upload it to your chosen Python/Docker host, set DATABASE_URL,
and use `bash start-production.sh` with HOST=0.0.0.0 and PORT supplied by the
host. It starts one telemetry writer and Gunicorn web workers. Use exactly one
writer service per database. A host that stops idle processes also stops the
stream; choose an always-running worker if continuous collection is required.
On services with separate web/worker processes, use `gunicorn app:app` for the
web command (bind the host's port) and `python worker.py` for the single worker.
The Dockerfile and compose file provide the equivalent local arrangement.

## Navigation

- Overview: condition, temperature, SOC, speed, flow, contributors and alerts.
- Thermal & cooling: C01-C10 reported cell temperatures, hottest-cell badge,
  cell spread, recommended vs delivered flow, cooling response and trends.
- Alerts: warning/critical records, recommended action, acknowledgement and history.
- Vehicle data: grouped measurements, recent rows and CSV export.
- System status: automatic monitoring state, vehicle profile and appearance.
- Theme button: change accent colours. Sidebar arrow: collapse navigation.
- Bottom vehicle card: name/model/ID. Its exit icon returns to vehicle login.

Acknowledgement records that an alert was seen; it does not repair the condition.
Readings, alerts and sessions are persisted separately. PINs use salted PBKDF2
hashes and login creates an HTTP-only cookie scoped to that vehicle.

## Exact files and folders

| Path | What it does |
| --- | --- |
| app.py | Flask backend, database initialization and localhost server |
| worker.py | Dedicated background feed for production hosting |
| thermovolt/fleet.py | Five profiles, automatic scenarios, alerts and login |
| thermovolt/core.py | Thermal simulator, trained surrogate and cooling optimizer |
| thermovolt/storage.py | Shared PostgreSQL/SQLite connections and transactions |
| thermovolt/monitor.py | Optional gateway intake API |
| thermovolt/segment.py, c/segment_tree.c | C segment-tree integration |
| frontend/src/page.tsx | Editable dashboard and login interface |
| frontend/src/globals.css | Styles, layouts and colour themes |
| frontend/src/main.tsx | React entry point |
| frontend/lib/ | Frontend vehicle profiles and thermal utilities |
| frontend/public/data/ | Bundled datasets and model weights |
| frontend/package.json, vite.config.ts, index.html | Frontend dependencies/build |
| web/ | Ready-to-run compiled frontend |
| data/ | Python model weights and statistics |
| sql/postgres.sql, sql/sqlite.sql | Database schemas |
| sql/monitoring_viva.sql, sql/viva.sql | DBMS inspection/example queries |
| requirements.txt | Python dependencies |
| .env.example | Your local connection/settings template |
| Dockerfile, compose.yaml | Optional independent app/PostgreSQL deployment |
| start.command, start-production.sh | Local and production startup |
| test_fleet.py, test_project.py, test_monitor.py | Verification scripts |
| gui.py | Optional Tkinter companion |
| train_models.py | Reproduce the synthetic thermal surrogate |
| analyze_dataset.py, evaluate_soc.py | Original dataset analysis/SOC exercises |

## Verify

```bash
python test_fleet.py
python test_project.py
```

The fleet test uses a temporary SQLite database and proves background writes
without browser requests, all five scenarios, four alerting cars and ID isolation.
It does not test your local PostgreSQL installation. Use the pgAdmin queries
above to verify that connection after setup.

## Model limits

The ten-cell thermal model and forecast are illustrative, trained on synthetic
thermal cases. Flow units refer to the microchannel model, not a complete EV
coolant circuit. Warnings are operating rules; they are not a validated
failure-probability classifier. The four hardware-dependent dataset attributes
are not collected. Cisco Packet Tracer is not connected yet.
