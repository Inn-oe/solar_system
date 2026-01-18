# Data Persistence Guide

This application is configured to use **PostgreSQL** for persistent data storage when deployed, and **SQLite** for local development.

## 1. Verify Render Configuration
Your `render.yaml` file already includes a database definition. To ensure your data persists:

1.  **Log in to Render Dashboard**.
2.  Go to your **Dashboard**.You should see two services created by the Blueprint:
    *   `giebee-erp` (Web Service)
    *   `giebee-db` (Postgres Database)
3.  **Check Environment Variables**:
    *   Select `giebee-erp`.
    *   Go to **Environment**.
    *   Verify that `DATABASE_URL` is set. It should be automatically linked to `giebee-db`.

## 2. If Data is Still Resetting
If you find that data is still disappearing after a redeploy, it means the Web Service is not actually connected to the Database.

1.  **Manually Link Database**:
    *   In Render Dashboard, go to your Web Service (`giebee-erp`).
    *   Go to **Environment**.
    *   If `DATABASE_URL` is missing, you must add it.
    *   Open your Database service (`giebee-db`) in a new tab.
    *   Find the **Internal Connection String** (starts with `postgres://...`).
    *   Copy it.
    *   Go back to Web Service -> Environment.
    *   Add Key: `DATABASE_URL`, Value: (Paste the Internal Connection String).
    *   Save Changes.

## 3. Important Notes
*   **Existing Data**: If you were previously running without a separate database service, your data was stored in a temporary file inside the web container. **That data is lost** every time the container restarts.
*   **New Data**: Once connected to PostgreSQL, your data will be safe and persistent across all future deployments.
*   **Local Development**: When running on your computer, the app uses `instance/database.db` (SQLite). This file is not uploaded to the server.
