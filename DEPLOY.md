# RehanCodex — Render deploy

## 1. Neon Postgres (free forever)

- https://neon.tech → sign up (GitHub ok)
- Create Project → region: Singapore
- Copy the connection string — looks like:
  `postgresql://user:pass@ep-xxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`

That is your `DATABASE_URL`.

## 2. Push code to GitHub

    git init
    git add .
    git commit -m "rehancodex render ready"
    git branch -M main
    git remote add origin https://github.com/YOUR_USER/rehancodex.git
    git push -u origin main

## 3. Render deploy

- https://render.com → sign up (GitHub)
- Dashboard → **New +** → **Blueprint**
- Connect the repo → Render reads `render.yaml`
- Fill the env vars:

| Key | Value |
|---|---|
| BOT_TOKEN | your bot token |
| ADMIN_ID | your telegram id |
| DATABASE_URL | the Neon string |

- Click **Apply** → wait ~2 min

Render assigns a URL automatically — like
`https://rehancodex-xxxx.onrender.com`.

The code detects `RENDER_EXTERNAL_URL` on its own.
You do not need to set `BASE_URL`.

## 4. Keep-alive (kill the 15 min sleep)

- https://uptimerobot.com → sign up (free)
- Add New Monitor
  - Type: HTTP(s)
  - URL: `https://rehancodex-xxxx.onrender.com/`
  - Interval: 5 minutes
- Save

The `/` route returns `OK`, Render stays awake.

## 5. Kill Termux

    pkill -9 -f "python main.py"
    pkill -9 -f ngrok
    pkill -9 -f cloudflared
    termux-wake-unlock

Bot now lives on Render, 24/7.

## Verify

- Browser: `https://rehancodex-xxxx.onrender.com/` → `OK`
- Telegram: `/start` → panel appears
- Generate a camera link → URL should be the render domain
- Open link on phone → permission prompt → admin DM gets the photo
