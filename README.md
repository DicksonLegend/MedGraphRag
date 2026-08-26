# MedGraphRAG — Clinical Graph-Grounded RAG System

MedGraphRAG is a self-verifying, graph-grounded Retrieval-Augmented Generation (RAG) system for clinical queries, diagnostic lab reports, and multimodal medical imaging (DICOM / X-ray triage).

---

## Security Architecture & Key Rotation

### 1. Environment Configuration
- `APP_ENV`: Set to `production` or `staging` in deployment. In non-dev environments, the backend refuses to boot unless secrets are explicitly provided.
- `MEDGRAPH_JWT_SECRET`: 256-bit cryptographically secure secret used for HS256 JWT signing.
- `MEDGRAPH_MASTER_KEY`: 256-bit master secret used for HKDF-SHA256 per-report and per-scan AES-256-GCM encryption.
- `DEMO_USER_PASSWORD` & `ADMIN_PASSWORD`: Salted scrypt password hashes are computed on startup.

### 2. Secret & Master Key Rotation Procedures

#### Rotating `MEDGRAPH_JWT_SECRET`
1. Generate a new 256-bit random secret:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```
2. Update the `MEDGRAPH_JWT_SECRET` environment variable in your production secrets store / container environment.
3. Restart the FastAPI service.
4. *Effect*: Existing user JWT tokens will be safely invalidated; users will re-authenticate to receive fresh tokens signed with the new key.

#### Rotating `MEDGRAPH_MASTER_KEY`
1. Set the new master key and run the offline migration utility:
   ```bash
   python scripts/migrate_private_store.py
   ```
2. The migration tool re-encrypts all stored diagnostic report payloads and scan metadata with the new HKDF-derived keys and enforces POSIX `0700` (directory) and `0600` (file) permissions.

### 3. Git Pre-Push Security Hook
To ensure no credentials, API keys, or private key materials are accidentally committed:
```bash
git config core.hooksPath .githooks
```

---

## Quickstart

### Backend
```bash
cd backend
PYTHONPATH=. ../Data_Normalization/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend
```bash
cd frontend
npm run dev
```
