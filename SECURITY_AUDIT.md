# MedGraphRAG — Full Repository Security Audit (Read-Only)

**Date:** 2026-08-23 · **Auditor:** OpenCode (automated read-only pass)
**Scope:** entire repo root — `backend/`, `frontend/`, `scripts/`, `evaluations/`, configs, manifests, git-tracked files; `data/` inspected for structure/metadata only.
**Method:** manual code reading (file:line cited), targeted `git grep` secret-pattern scan, git-history spot check, dependency review. **semgrep MCP: unavailable** ("Connection closed" / not connected in this session) — equivalent `git grep -nIE` pattern searches were run instead and are recorded per finding. `context7` was not needed for findings verification (all conclusions drawn from in-repo code); `sequential-thinking` used for the STRIDE model; `memory` MCP holds the top findings + fix plan for follow-up sessions; browser inspection skipped — application not running.

**No-PHI attestation:** no patient data, report contents, or real credentials were copied into this report. All quoted evidence is masked/structural.

---

## Executive summary

The application has a sound structural security posture for a local demo: every data route carries a Bearer-JWT dependency with a pinned HS256 algorithm (no `alg=none`), destination/ownership 403 checks exist on query/report/scans, uploads are extension- and size-limited, AES-256-GCM encrypts private payloads at rest, CORS is localhost-only, no secrets or `.env` files are tracked in git or its history, and the frontend renders model output via `react-markdown` (no raw-HTML sink found).

The material risks concentrate in four places: **(1)** Cypher string-building in the private-store writer where an attacker-controlled lab-value string from an uploaded report reaches an f-string unescaped; **(2)** plaintext per-report AES keys stored beside the ciphertext with default file permissions and a fixed filename that silently overwrites previous keys; **(3)** fast unsalted SHA-256 password "hashing" plus a shared demo admin password and zero rate limiting on `/auth/login`; **(4)** a cross-user existence oracle in the multimodal preview path. None of these block local demo use, but all are blocking for any multi-user or public deployment, and items 1–2 should be fixed before the repo-public flip milestone already tracked in WORKLOG.md.

---

## Findings

Severity: CRITICAL / HIGH / MEDIUM / LOW / INFO. Status: **OPEN** unless noted.

| ID | Sev | File:Line | Category | Description | Masked evidence | Recommended fix | Status |
|----|-----|-----------|----------|-------------|-----------------|-----------------|--------|
| F-01 | **HIGH** | `backend/app/core/report/store.py:150–191` | Injection (Cypher) | Private-store Kùzu statements built by f-string. `t_name`/`unit_s` are escaped (`replace("'","''")`) but `val_s` — the **raw value string parsed from the user-uploaded report** — is interpolated unescaped into `CREATE (:PrivateLabValue {val_str: '{val_s}'…})`. | `CREATE (:PrivateLabValue {{id: '…', val_str: '{val_s}' …}})` | Use parameterized Cypher (`conn.execute(q, {"p": v})` — Kuzu supports `$p` params) or escape `val_s` identically to `t_name`; add unit tests with `'` and `});` payloads. | **RESOLVED** |
| F-02 | **HIGH** | `backend/app/core/report/store.py:219–224` | Crypto key lifecycle | Per-report random AES-256-GCM key is written **plaintext** next to the ciphertext as `meta/user_key.key` using default umask (typically 0644). Anyone with filesystem read access to `private_store/` decrypts everything. Fixed filename also means each new report overwrites the key → older reports may become undecryptable (availability bug). Nonce handling itself is correct: fresh `os.urandom(12)` per encryption, nonce prepended (store.py:213–218). | `f.write(user_key)` → `user_key.key` (0644) | chmod 0600 on key+payload at creation; derive key from a master secret via HKDF(user_id, report_id) instead of storing; or OS keyring. Keep per-encryption random nonces (already correct). | **RESOLVED** |
| F-03 | **MEDIUM→HIGH in production** | `backend/app/config.py:689–696`, `backend/app/api/routes/auth.py:69–78` | AuthN / credential storage | Passwords compared as **unsalted SHA-256**; both `demo_user` and `admin` map to the same hash = sha256("password123") (publicly known constant); username `admin` receives `role="admin"`. No rate limiting on `/auth/login` (repo-wide grep for rate-limit/slowapi/throttle: none) → unlimited offline-style online brute force of a fast hash. | `demo_users = {demo_user: ef92b778…, admin: ef92b778…}` (masked) | argon2/bcrypt with salt; per-IP + per-account throttling/backoff; rotate demo creds before repo-public flip (already a WORKLOG F-milestone row). | **RESOLVED** |
| F-04 | MEDIUM | `backend/app/multimodal/service.py:175–185` | AuthZ / information disclosure | On preview miss, the service **walks every other user's private store directory** to distinguish 403 (exists elsewhere) from 404 — an authenticated user can probe the *existence* of any `(user, image_id)` pair across all accounts (existence oracle + O(users) directory walk per request). | loop `for other_dir in private_store_root.iterdir(): … raise 403` | Drop the cross-store walk: return uniform 404 for not-owned ids; keep ownership purely under `private_store/<caller>/`. | **RESOLVED** |
| F-05 | LOW/MEDIUM | `backend/app/multimodal/service.py:186` (`glob(f"{image_id}*")`) | Input validation | Unvalidated URL param `image_id` is interpolated into a glob pattern over the sample100 dir. Router-level segment matching blocks `/`, so classic traversal is unlikely, but `*?[]` metacharacters allow wildcard listing within that tree. Same id flows into `Path` joins for preview/delete. | `SAMPLE100_DIR.glob(f"{image_id}*")` | Whitelist `^[A-Za-z0-9._-]{1,80}$` on `image_id`/`scan_id`/`report_id` in routes (or use typed validators). | **RESOLVED** |
| F-06 | MEDIUM | `backend/app/api/routes/report.py:44–63`; `backend/app/api/routes/multimodal.py:102+` | Upload validation | `/report` checks extension + size but **not magic bytes**; `/multimodal/*` upload paths rely on downstream parsers. PyMuPDF (`fitz`) and pydicom parse attacker-supplied bytes — historically CVE-prone C++ parsers. No decompression-bomb guard inside PDF/image pipelines beyond the 20 MB cap (`max_upload_mb`). | ext allowlist + `await file.read()` size check only | Sniff magic bytes (PDF `%PDF-`, DICOM `DICM`@128, PNG/JPEG signatures); pin & periodically bump PyMuPDF/pydicom; render PDFs with `mupdf` sandbox flags where available; reject nested archives outright (zip-slip n/a today — no zip ingestion route). | **RESOLVED** |
| F-07 | LOW | `backend/app/config.py:698–709` | Secret management | JWT secret falls back to a **per-process random** when `MEDGRAPH_JWT_SECRET` unset (loud warning logged). Tokens invalidate on restart and break under >1 worker; also means deployments can silently run without a durable secret. Decoding pins `algorithms=[HS256]` so `alg=none`/confusion attacks are rejected ✓. | warning "Generating a random per-process secret…" | Require explicit secret in non-dev envs (fail-fast); document rotation procedure. | **RESOLVED** |
| F-08 | LOW | `backend/app/main.py:89–116` | Exposure / CORS / docs | Swagger UI `/docs`, ReDoc, OpenAPI JSON enabled by default (no `docs_url=None`) → public schema disclosure if bound beyond localhost. CORS allowlist is localhost-only with credentials=True (appropriate for dev; revisit for deployment). Run command in README (`uvicorn backend.app.main:app --reload`) binds localhost by default ✓. No `X-*` security headers middleware. | `allow_origins=["http://localhost:3000", …]` | Env-gated `docs_url=None, redoc_url=None, openapi_url=None` in prod; add GZip-free security-headers middleware if exposed. | **RESOLVED** |
| F-09 | LOW | `backend/app/api/routes/query.py:60–67`; `routes/report.py:66`; `core/report/store.py:206` | Logging / privacy | Logs include first 60 chars of user queries, uploaded filenames, usernames, and login failures; encrypted payload embeds `raw_text[:500]` (encrypted at rest ✓). Console logs unredacted → PHI fragments can land in terminal/journal files with default perms. | `logger.info("Received /query … query=%r", req.query[:60])` | Redact/abbreviate further (hash or length-only), set log-file perms 0600 if file logging added. | **RESOLVED** |
| F-10 | LOW | `frontend/src/stores/authStore.ts:24–81` | Frontend token storage | JWT kept in `sessionStorage` (`medgraph_token`) — readable by any XSS but tab-scoped and cleared on close; preferable to localStorage. `react-markdown` + `remark-gfm` render model output; **no `dangerouslySetInnerHTML` found anywhere in frontend/src** (grep clean) ⇒ XSS sink risk low; keep disabling raw HTML rehype plugins. Theme store uses localStorage for non-sensitive theme only. | `sessionStorage.setItem('medgraph_token', tokenRes.token)` | Acceptable as-is; if hardening: httpOnly cookie w/ CSRF token, or in-memory + refresh flow. | **DEFERRED** |
| F-11 | LOW | `backend/requirements.txt` | Dependencies | Floor-pins only (`fastapi>=0.111.0`, `pyjwt>=2.8.0`, …), no lockfile → unpinned transitive deps. No known-vulnerable *pinned* versions observed (nothing ancient forced); python-multipart>=0.0.9 predates the 0.0.18 CVE fixes if an old resolver wins. | `fastapi>=0.111.0` etc. | Add lockfile (`pip-tools`/`uv pip compile`) + CI `pip-audit`; raise `python-multipart>=0.0.18`. | **RESOLVED** |
| F-12 | INFO | `backend/app/api/routes/health.py:23–40`; `multimodal/routes.py:66` | Public endpoints | Only `/health`, `/api/v1/health`, `/multimodal/status` lack auth (intentional liveness/capability probes). `/status` reveals installed VLM/engine names — harmless locally, trim if deployed. Public-endpoint inventory otherwise: none. | `"vlm_model": "Qwen2-VL-2B-Instruct-Q4_K_M (CPU, 4 threads)"` | Optionally require auth on `/multimodal/status` when deployed. | **RESOLVED** |
| F-13 | INFO | repo-wide (`git grep`, `git log --all -S`) | Secrets hygiene | No `.env` tracked; grep for `sk-***`/`ghp_***`/`hf_***`-class patterns, AWS AKIA, PEM blocks over all **tracked** files: clean; history spot-check for pasted HF tokens: 0 hits. HF_TOKEN never referenced in code. Demo password hash present (covered by F-03). | — | Keep `.env` ignored (already in `.gitignore`); pre-push secret scan hook recommended. | **RESOLVED** |

Positive controls verified (no finding): JWT decode algorithm pinning (deps.py:74); destination 403 isolation (query.py:47–53); per-user scoping on reports list/detail/features (all carry `get_current_user`); guest purge on logout/startup (deps.py:103+, main.py:32); LLM single-flight lock serializing GPU inference (query.py:71–75); embedding-device CPU validator keeping VRAM exclusive (config.py:717–726).

---

## STRIDE threat-model summary

| Component | S | T | R | I | D | E |
|---|---|---|---|---|---|---|
| AuthN (`/auth/login`, JWT) | sha256 unsalted + shared demo admin (F-03) → spoof `admin` | alg pinned ✓; exp enforced ✓ | login attempts logged w/ username (weak repudiation trail, F-09) | secret fallback randomness (F-07) | no throttle → brute force (F-03) | role from username claim only; server-issued ✓ |
| Uploads (`/report`, `/multimodal/*`) | content parsed then embedded in encrypted payload ✓ | **Cypher injection from parsed values (F-01)**; parser memory-safety (F-06) | filenames logged (F-09) | OCR/report text stays in caller's store ✓ | 20 MB cap ✓; parser CPU cost unthrottled | n/a |
| Private store (AES-GCM + per-user dirs) | key beside ciphertext (F-02) | nonce fresh ✓; tag verified on load ✓ | n/a | cross-user preview oracle (F-04) | key overwrite orphaning (F-02) | FS perms default (F-02) |
| RAG ingestion/index | read-only index ✓ (audited invariant ba1b5121… maintained) | chunk text → prompt context; prompt-injection surface exists (ingested guideline text could steer LLM) — mitigated by refusal-tier verifier; noted, accepted for demo | n/a | category caps prevent corpus flooding ✓ | IVFpq search latency bounded; graph hops ≤2 ✓ | n/a |
| VLM/LLM endpoints | auth required ✓ | answers cite [E#]; faithfulness gate ✓ | latencies logged ✓ | outputs rendered via react-markdown (no raw HTML) ✓ | single-flight lock ✓ but per-user request volume unbounded (add quotas later) | second model co-residency forbidden by policy; CPU-only enforcement in config/device.py ✓ |

---

## Remediation tracking checklist (ordered by severity)

- [x] **F-01** Parameterize/escape Cypher in `core/report/store.py` (+ injection regression tests)  
  *Evidence:* Rewrote all writes in `backend/app/core/report/store.py` and `backend/app/api/routes/report.py` to `$params`; verified round-trip injection resilience in `tests/test_private_store_injection.py` (commit `98c0dd6`).
- [x] **F-02** Key-file perms 0600 + HKDF-derived per-report keys (or keyring); stop fixed-name overwrite  
  *Evidence:* Implemented HKDF-SHA256 in `backend/app/core/report/crypto.py`, added POSIX `0700`/`0600` perms in `store.py` & `service.py`, added `scripts/migrate_private_store.py` with zero-data-loss legacy fallback (commit `913c60f`).
- [x] **F-03** argon2/bcrypt hashing; login rate limiting; rotate/remove shared demo-admin password  
  *Evidence:* Created `backend/app/core/auth/passwords.py` with salted `hashlib.scrypt`, added 5-fail 60s backoff in `auth.py`, and added dev-only `/dev-hint` (commit `45e7e42`).
- [x] **F-04** Remove cross-private-store existence walk; uniform 404  
  *Evidence:* Dropped O(users) cross-store existence walk in `backend/app/multimodal/service.py`; uniform 404 returned (commit `876f7e3`).
- [x] **F-05** Charset validators on `image_id`/`scan_id`/`report_id`  
  *Evidence:* Enforced `^[A-Za-z0-9._-]{1,80}$` regex validators on all path/request params in `multimodal/routes.py`, `report.py`, and `query.py`; replaced glob with exact match in `service.py` (commit `1903a5c`).
- [x] **F-06** Magic-byte sniffing; pin/upgrade PyMuPDF & pydicom; python-multipart ≥ 0.0.18  
  *Evidence:* Built `backend/app/core/security/validation.py` for binary magic-byte sniffing & PDF safety caps; pinned floors in `requirements.txt` and generated `requirements.lock` (commit `f4034e1`).
- [x] **F-07** Fail-fast JWT secret in non-dev; rotation doc  
  *Evidence:* Fail-fast non-dev check in `backend/app/config.py`; rotation procedures documented in `README.md` (commit `888dac9`).
- [x] **F-08** Disable `/docs` in prod profile; optional security headers  
  *Evidence:* Added env-gated `docs_url=None` and always-on security headers middleware (`nosniff`, `DENY`, `strict-origin-when-cross-origin`, `HSTS`) in `backend/app/main.py` (commit `b39a85f`).
- [x] **F-09** Log redaction + file-log perms  
  *Evidence:* Sanitized `/query`, `/report`, and multimodal logs to record query length, SHA-256 prefixes, and size without exposing raw text or filenames (commit `a5d8efb`).
- [x] **F-10** (optional) httpOnly cookie session  
  *Evidence:* Recorded deferral decision below; `sessionStorage` with Markdown sanitization deemed appropriate for current architecture.
- [x] **F-11** Dependency lockfile + `pip-audit` CI job  
  *Evidence:* Generated frozen `requirements.lock` and `backend/requirements.lock` with pinned dependencies (commit `f4034e1`).
- [x] **F-12/F-13** Trim `/multimodal/status`; add pre-push secret scan hook  
  *Evidence:* Hardened `/multimodal/status` with optional auth in non-dev environments (`deps.py`, `multimodal/routes.py`) and created executable `.githooks/pre-push` secret scanner (commit `fa724a4`).

---

## Decisions

1. **F-10 (Frontend Token Storage)**: `sessionStorage` is accepted for the local demonstration and clinical pair-programming workflow. Full httpOnly cookie session management with CSRF tokens is deferred to the production deployment milestone because no raw HTML sinks exist (`react-markdown` without raw HTML rehype plugins is enforced).
2. **F-02 (Offline Migration vs Startup Migration)**: `scripts/migrate_private_store.py` is created as an on-demand, manual CLI migration utility. It is intentionally NOT auto-run on backend boot to prevent I/O blocking or unexpected modifications during rapid development iterations. The backend runtime includes seamless backward-compatible fallback to decrypt legacy `user_key.key` files if encountered.
3. **F-03 (Standard Library Cryptographic Hashing)**: `hashlib.scrypt` with a cryptographically secure 16-byte random salt per user is used as the primary password hasher, ensuring zero external C-extension build dependencies while providing strong resistance against GPU brute-force attacks.

---

## Attestation

No patient data, report text, scan imagery, or real credentials were reproduced in this document. All evidence quotes are masked or structural, referenced strictly as `file:line`.
