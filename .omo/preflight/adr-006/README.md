# ADR-006 P0 preflight

This directory is the executable **documentation-contract** gate required before
repository bootstrap. It validates the seven `WF-P0-*` obligations, their
canonical documentation markers, and their positive/negative fixture coverage.

It does not claim to test PostgreSQL RLS, queue leases, audit anchoring, or
percentile computation at runtime. Those runtime proofs remain release-blocking
future harness evidence identified in `docs/quality/verification-strategy.md`.

Run from the repository root:

```sh
node .omo/preflight/adr-006/validate.mjs
```

The validator writes `.omo/evidence/preflight-adr-006/validation.json`.
