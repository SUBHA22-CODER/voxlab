# Deployment Guide

> **Assumptions:**
> - Supports both single-host Docker Compose deployment and split cloud deployment (Vercel + Railway/Render).

---

## 1. Single-Server Deployment (Docker Compose)

### 1.1 Prerequisites
- Docker Engine $\ge 24.0$ & Docker Compose v2.

### 1.2 Step-by-Step Instructions
1. Clone the repository and configure `.env`:
   ```bash
   cp .env.example .env
   ```
2. Generate production secrets:
   ```bash
   # Set a random 32+ character secret key
   SECRET_KEY=$(openssl rand -hex 32)
   # Generate Fernet encryption key
   ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
   ```
3. Update `.env`:
   ```ini
   SECRET_KEY=<YOUR_GENERATED_SECRET_KEY>
   ENCRYPTION_KEY=<YOUR_GENERATED_ENCRYPTION_KEY>
   LLM_API_KEY=<YOUR_GROQ_OR_OPENAI_KEY>
   ALLOW_LOCAL_ENDPOINTS=false
   CORS_ORIGINS=https://voxlab.yourdomain.com
   NEXT_PUBLIC_API_URL=https://api.yourdomain.com
   ```
4. Build and start all services:
   ```bash
   docker compose --profile full up -d --build
   ```

---

## 2. Cloud Platform Deployment (Vercel + Railway/Render)

### 2.1 Backend on Railway / Render
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Attached Addons:** Managed PostgreSQL database (`DATABASE_URL=postgresql+asyncpg://...`).

### 2.2 Frontend on Vercel
- **Root Directory:** `frontend/`
- **Framework Preset:** Next.js
- **Environment Variables:**
  - `NEXT_PUBLIC_API_URL`: URL of the deployed backend service (e.g., `https://backend.railway.app`).
