# Remote Deployment & Screener-Only Guide

This guide explains how to deploy **CypherScreen** to the cloud or access it remotely on your phone or laptop, customized for **screening-only use** where you execute trades manually directly on Binance.

---

## 🔒 Screener-Only Mode: Why It's 100% Safe & Zero-Risk

Since you plan to manually execute trades on Binance yourself:
1. **No Binance API Keys or Secret Keys Needed on the Server**:
   - The screener, technical indicators (RSI, MACD, EMA, Bollinger Bands), candlestick charts, high-delta scanner, and market regimes **all use Binance's public REST endpoints**.
   - You can leave `API_KEY` and `SECRET_KEY` blank or unset.
2. **Zero Financial Risk**:
   - No funds can ever be moved or trades placed from this terminal.
3. **No Geo-Blocking**:
   - Binance public market data feeds are globally accessible without exchange account IP restrictions.

---

## 🛡️ Private Access: Single-User Password Protection

To ensure **only you** can access your screener when deployed publicly on the web:
Set the `DASHBOARD_PASSWORD` environment variable (in your cloud dashboard or `.env` file):

```env
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=YourSecurePassword123!
SCREENER_ONLY_MODE=true
```

When you visit your deployed URL on any phone or computer, your browser will show a standard login prompt. Enter your credentials once, and your browser will remember them.

---

## Deployment Options

### Option 1: 1-Click Free Cloud Deployment on Render (Recommended)

Render gives you a free `https://<your-app>.onrender.com` URL with automatic HTTPS SSL.

1. **Push your code to GitHub**:
   - Create a private repository on GitHub and push this project.
2. **Create a Web Service on Render**:
   - Go to [dashboard.render.com](https://dashboard.render.com) and click **New + > Web Service**.
   - Select your GitHub repository.
3. **Configure Settings**:
   - **Environment**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
4. **Add Environment Variables**:
   - `SCREENER_ONLY_MODE`: `true`
   - `DASHBOARD_USERNAME`: `admin`
   - `DASHBOARD_PASSWORD`: `<choose your password>`
5. Click **Deploy Web Service**.
   - Within 2–3 minutes, your screener is live at `https://<your-app-name>.onrender.com`!

*(Note: Render already recognizes the included [render.yaml](file:///C:/Users/rvsdc/crypto-analysis/render.yaml) blueprint if you use Blueprints.)*

---

### Option 2: Railway or Fly.io

1. **Railway**:
   - Go to [railway.app](https://railway.app), click **New Project > Deploy from GitHub repo**.
   - Railway automatically reads the included [Procfile](file:///C:/Users/rvsdc/crypto-analysis/Procfile) and binds to `$PORT`.
   - In the **Variables** tab, set `DASHBOARD_PASSWORD=<your-password>` and `SCREENER_ONLY_MODE=true`.

2. **Fly.io**:
   - Run `fly launch` in your terminal. Fly will detect the included [Dockerfile](file:///C:/Users/rvsdc/crypto-analysis/Dockerfile) and deploy globally.

---

### Option 3: VPS / Cloud VM (Docker & Docker Compose)

If you have a Linux server (DigitalOcean, Hetzner, AWS EC2, or Oracle Free Tier):

1. Clone your repository to the server.
2. Edit password in [docker-compose.yml](file:///C:/Users/rvsdc/crypto-analysis/docker-compose.yml):
   ```yaml
   environment:
     - DASHBOARD_USERNAME=admin
     - DASHBOARD_PASSWORD=MySecretPassword123
     - SCREENER_ONLY_MODE=true
   ```
3. Run:
   ```bash
   docker compose up -d --build
   ```
4. Access via `http://<your-server-ip>:8000`.

---

### Option 4: Free Remote Access from Your Home PC (No Cloud Deployment Needed)

If you already run this on your Windows PC and just want to view the screener on your phone or laptop when you are away from home, you don't even need to rent a cloud server!

#### Using Cloudflare Tunnel (100% Free & Secure):
1. Install [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/).
2. Run:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```
3. Cloudflare gives you a temporary or permanent HTTPS URL (e.g. `https://random-words.trycloudflare.com`) that securely routes to your PC.

#### Using Tailscale (Free Private Mesh Network):
1. Install Tailscale on your PC and on your phone.
2. Sign in to both devices.
3. Open `http://<pc-tailscale-ip>:8000` on your phone browser.
4. Only your own devices can reach it—nothing is exposed to the public internet!
