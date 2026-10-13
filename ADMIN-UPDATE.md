# ThermoVolt admin update - GitHub and Render

## What changes

- The original five cars and their PINs remain.
- Password-protected Administrator access appears on the login page.
- Admin can see all vehicles, owner names, models, conditions, temperature,
  SOC, saved-reading counts, active alerts and last update time.
- Open a row to inspect that vehicle's full existing five-page workspace.
- Register more vehicle accounts without editing source code.
- Every new account automatically receives a persistent simulation stream.
- Assign a scenario once during registration; the user does not choose it
  during monitoring. It remains simulated telemetry, not real-car data.

## Use the update ZIP

1. Extract ThermoVolt-Admin-Update.zip. Upload its CONTENTS, not the ZIP or
   the enclosing extracted folder.
2. In GitHub open mShailly/Thermovolt on branch main.
3. Add file > Upload files. Upload these files/folders together at repository
   root, preserving their nested paths:

   app.py
   thermovolt/ (admin.py, registry.py and updated fleet.py)
   sql/ (updated postgres.sql and sqlite.sql)
   frontend/src/ (Admin.tsx, updated page.tsx and globals.css)
   web/ (index.html and new assets)
   README.md
   ADMIN-UPDATE.md
   test_admin.py

4. Commit changes with message "Add admin dashboard and vehicle registration".
   GitHub updates matching files and adds new ones. Keep the other existing
   files in thermovolt/, frontend/, web/data/, c/ and data/.
5. To make uploading easier, the update ZIP contains a frontend/ folder with
   its changed src/ contents. Drag frontend/ directly into the root upload.
   Do not upload src/ at the root.

## Render environment - required

Open the EXISTING ThermoVolt WEB SERVICE (not the Postgres database).
Environment > Add environment variable:

ADMIN_USERNAME = admin
ADMIN_PASSWORD = your own password of at least 10 characters

Do not use the database password as the admin password. Do not send either
password in chat or store it in GitHub. Keep the existing DATABASE_URL,
HOST and PORT settings and keep the same PostgreSQL database.
Save the environment settings. If Render starts a deployment, let it finish.
Otherwise Manual Deploy > Deploy latest commit.
If auto-deploy is enabled, your GitHub commit may already start the deployment.
No new Render service, PostgreSQL instance or repository is needed.

## Database upgrade

The app creates two new tables at startup: fleet_profiles and
fleet_admin_sessions. Existing accounts, readings and alerts are not deleted.
The original five vehicle profiles are seeded only if they are absent.
Do not DROP any tables and do not replace your existing database.

## Check after Live

1. Open the same public Render website link. Refresh with Command+Shift+R.
2. Click Administrator access.
3. Username: admin. Password: the one set in Render ADMIN_PASSWORD.
4. Confirm all five original cars appear in Registered vehicles.
5. Click Register vehicle, and enter a new unique login ID, owner/user name,
   vehicle display name, model, four-digit PIN, type, battery details and
   automatic scenario.
6. Submit. Wait for the next worker cycle, normally a few seconds.
7. The new row's readings and last-update values should begin changing.
8. Open the new car to inspect its Overview, Thermal & cooling, Alerts,
   Vehicle data and System status pages.
9. Use Admin logout before testing ordinary vehicle access in the same browser.
   Log in with the new Vehicle ID and PIN.

## Local upgrade

Merge the update's folders/files into your existing extracted project folder.
Do not remove unchanged files. Add ADMIN_USERNAME and ADMIN_PASSWORD to your
local .env and restart python app.py. Prebuilt web assets are included.
No frontend build or new Python dependency is required to run this update.
When editing the frontend, npm run build in frontend/ rebuilds web/.

## Optional verification in pgAdmin

SELECT vehicle_id, profile::json ->> 'owner' AS owner,
       profile::json ->> 'model' AS model
FROM fleet_profiles ORDER BY vehicle_id;

SELECT vehicle_id, COUNT(*) AS readings, MAX(observed_at) AS latest
FROM fleet_readings GROUP BY vehicle_id ORDER BY vehicle_id;

The newly registered vehicle should appear in both results after the writer
has run. Conditions are fixed scenario profiles with continuous variation.
The service must be running. Render free-tier sleep still pauses generation.
More registrations are supported without a fixed five-car limit, but throughput
and storage remain limited by your hosting resources.
