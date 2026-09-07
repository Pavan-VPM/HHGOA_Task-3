# 🚂 Deploying to Railway

This repository is pre-configured for 1-click deployment on **[Railway.app](https://railway.app)**.

---

## ⚡ Option A: Deployment via Railway Web Dashboard (Easiest)

1. **Push your repository** to GitHub (already completed).
2. Go to **[railway.app](https://railway.app)** and log in with your GitHub account.
3. Click **"New Project"** -> Select **"Deploy from GitHub repo"**.
4. Choose `HHGOA_Task-3` (or your repository name).
5. Railway will automatically detect the `Procfile` and `railway.json` and start building with Python 3.
6. Click on your project -> **"Variables"** tab and optionally add your environment variables:
   - `SERPAPI_API_KEY`: *(Optional for live Google Lens search)*
   - `BLOCKCHAIN_MODE`: `local` *(or `remote` if using Sepolia)*
7. Click **"Settings"** -> **"Networking"** -> **"Generate Domain"** to get your live public URL (e.g., `https://hhgoa-task-3-production.up.railway.app`).

---

## 🛠️ Option B: Deployment via Railway CLI

```bash
# 1. Install Railway CLI
npm i -g @railway/cli

# 2. Log in to Railway
railway login

# 3. Link to a new project
railway init

# 4. Deploy repository
railway up

# 5. Open live URL
railway open
```

---

## 📋 Included Pre-Configurations

- **`Procfile`**: Defines the web process `web: python3 server.py`.
- **`railway.json`**: Explicitly configures Nixpacks builder & auto-restart policy.
- **Dynamic `$PORT` Support**: `server.py` reads `os.environ.get("PORT", 3000)` dynamically.
