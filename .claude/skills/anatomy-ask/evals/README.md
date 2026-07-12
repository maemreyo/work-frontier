# Trigger eval notes

This set protects the routing boundary introduced by the reliability update:

- `anatomy-ask` owns narrow, read-only questions answered from an existing trace.
- `anatomy` owns create, refresh, migrate, and re-trace requests.
- `anatomy-gate` owns pass/fail source-vs-doc freshness checks.

There are 6 positive and 6 negative cases. They have been reviewed manually
against the skill descriptions, but a real model trigger loop has **not** been
run in this environment. Run the repository's normal skill eval harness before
using trigger percentages as release evidence.
