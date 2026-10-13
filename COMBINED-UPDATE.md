# Combined registration, administration, history, AI chat and sound update

Upload this combined ZIP instead of uploading several separate patches.
The existing five cars, PINs, saved readings and your public Render URL remain.

## GitHub

Extract ThermoVolt-Combined-Update.zip. Open the root of mShailly/Thermovolt,
branch main. Add file > Upload files. Drag ALL files/folders INSIDE the extracted
update folder into GitHub, keeping their nested paths. Commit changes.
Do not upload the ZIP or the enclosing extracted folder.

The update contains app.py, thermovolt/, sql/, frontend/src/, web/,
README.md, COMBINED-UPDATE.md and test files. Keep the other existing project
files. Old unused hashed assets may remain in GitHub; the new index.html points
to the new JS/CSS files. No local npm build is needed to deploy this package.

## Render

Open the EXISTING Web Service. Keep DATABASE_URL, HOST and PORT.
Keep ADMIN_USERNAME=admin and your own ADMIN_PASSWORD of at least 10 characters.
Save settings, then Manual Deploy > Deploy latest commit if deployment does
not start automatically. Wait for Live. Open your same URL and hard refresh
with Command+Shift+R. Do not create a new database or drop tables.

## AI assistant configuration

The trained thermal surrogate still runs locally in Python as before.
The conversational assistant is a separate hosted language-model integration.
To enable it, add OPENAI_API_KEY to the Render Web Service Environment,
using your own API key. AI_MODEL defaults to gpt-4o-mini and can be changed to
a supported Chat Completions model available to your API account.
API use may require billing/credit. No ChatGPT sign-in appears on this website.
Never put the key in GitHub or frontend code, and never send it in chat.

Without the key, the widget appears but returns a clear configuration message.
It does not pretend that canned replies are AI. The backend sends the selected
vehicle's numerical telemetry, alerts, aggregate history and chat messages to
the provider. It does not send PIN hashes, passwords, owner names or other cars.
No real API key was available for an end-to-end provider test in this update.
Authorization and the provider response contract were tested with a mock.
The assistant cannot approve users, modify data, control cars or execute SQL.

## Registration flow

1. Normal login page > Request vehicle registration.
2. Applicant enters owner name, vehicle name/model, a unique Vehicle ID,
   four-digit PIN, type and battery details.
3. Request starts Pending. Applicant gets a private tracking code and can
   check status on that form. The browser saves the most recent tracking code.
4. Admin > Registration requests. Inspect the request, assign a simulation
   condition, then Approve. Or enter a reason and Reject.
5. Approval creates the hashed login and profile in one transaction.
6. The worker starts simulated readings at its next cycle. The user can
   log in using the ID and PIN chosen during registration.

PINs are never shown to the administrator. The original five cars are already
approved. Admin can still register accounts directly from the dashboard.
There is no fixed five-car limit, but available CPU and storage limit capacity.
Public requests default to normal driving; the administrator assigns their
automatic simulation scenario at approval. Users do not manually generate data.

## Admin features

- Complete vehicle list and access to each five-page workspace.
- Search by owner, ID, vehicle name or model.
- Filters: all, healthy, warning, critical, suspended.
- Suspend/reactivate without deleting history. Suspended cars pause their
  simulation and normal-user access. Admins can inspect retained history.
- Reset PIN. Existing normal-user sessions are invalidated.
- Activity log for approval, rejection, direct registration, suspension,
  reactivation and PIN reset. No passwords or PINs are written to the log.

## Date-range history

Vehicle data > Date-range history. Select start/end dates and Load history.
Date filters use UTC. The display shows local dates/times with up to 500 rows.
Download date-range CSV streams all rows within the chosen snapshot range.
Date and time also appear in page update labels, readings and the admin table.

## One-minute sound

Click Enable sound on the vehicle header or admin dashboard. This browser
gesture unlocks audio. It beeps immediately if active alerts exist, then
reminds once per minute while active alerts remain and the page is running.
Every vehicle page shares its header control. The admin view tracks fleet alerts.
Use Mute reminders to stop. Acknowledged and resolved alerts do not repeat.
Healthy cars are silent. Sound does not itself acknowledge or resolve anything.
No email, SMS, push notification or closed-browser alarm is implemented.
Browsers may throttle background tabs. A returning visible page checks whether
a reminder is overdue. The user may need to enable sound again after a reload.

## PostgreSQL

fleet_profiles and fleet_admin_sessions support administration.
This update additionally creates fleet_requests and fleet_audit at startup.
Existing fleet_users, fleet_sessions, fleet_readings and fleet_alerts remain.

SELECT vehicle_id,status,created_at,reviewed_at,reason
FROM fleet_requests ORDER BY created_at DESC;

SELECT vehicle_id,COUNT(*) AS readings,MAX(observed_at) AS latest
FROM fleet_readings GROUP BY vehicle_id ORDER BY vehicle_id;

SELECT actor,action,vehicle_id,created_at FROM fleet_audit
ORDER BY created_at DESC;

Do not display pin_salt, pin_hash, session tokens or tracking-token hashes
when presenting. Refresh pgAdmin's Tables node to see newly created tables.

## Laptop

Merge the update into the existing project, preserving unchanged files and .env.
Set the new variables in your own .env as required, then restart python app.py.
The full project ZIP provides all source files and the prebuilt frontend.
Tests: python test_workflow.py; python test_admin.py; python test_fleet.py.
