# Module: Platform Security

**Path:** `backend/src/work_frontier/platform/security`
**Role:** Deterministic browser headers, egress policy, upload validation, value redaction, and TLS configuration enforcement.

## Public interface

- `EgressPolicy` — HTTPS-only allowlist for server-side outbound requests.
- `validate_upload(filename, content_type, size_bytes, max_size_bytes)` — validates filename, media type, and bounded size.
- `redact(value)` — recursively redacts secret-bearing keys and bearer-like values.
- `require_tls_configuration(public_base_url, database_url, object_store_url)` — rejects production configuration with plaintext transports.
- `validate_upload` with allowlisted content types (JSON, CSV, Markdown, plain text).

## Internal structure

- `hardening.py` — all security hardening controls.

## Depends on

- No internal module dependencies; stdlib only (ipaddress, re, dataclasses, pathlib, urllib.parse).

## Used by

None confirmed.

## Data & side effects

- Pure validation controls; no I/O.

---

_Traced from source on 2026-07-14. Files examined in depth: all 2 files._
