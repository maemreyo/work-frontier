# DecisionRecord: Pydantic / Zod Compatibility

How the contract flows and where it diverges.

## Generation pipeline

```
Python source (decision_record.py)
    ↓  model_json_schema()
JSON Schema (contracts/generated/decision-record.schema.json)
    ↓  x-to-zod + addMinPropertiesRefinements()
Zod output (frontend/src/contracts/decision-record.generated.ts)
```

Pydantic is the source of truth. The JSON Schema and Zod files are generated
artifacts, checked in for cross-language validation.

## Classification key

| Tag | Meaning |
|---|---|
| **generated-equivalent** | Different mechanism, same parse-time behavior. No runtime gap. |
| **allowed-difference** | Intentional. No feasible cross-language equivalent, or metadata-only. |
| **known-deviation** | Semantic gap. One side is stricter than the other. |

## Observed differences

### 1. `computed_at` timezone enforcement

**Tag: known-deviation**

| Layer | Representation |
|---|---|
| Pydantic | `datetime` — accepts both naive and aware ISO strings |
| JSON Schema | `{"format": "date-time", "type": "string"}` — no enforcement at schema level |
| Zod | `z.string().datetime({ offset: true })` — requires timezone offset |

`x-to-zod` interprets `format: date-time` per RFC 3339, which mandates a
timezone offset. Pydantic's `datetime` is more permissive and happily parses
`"2026-01-01T00:00:00"` (naive). Zod rejects it.

**Current impact:** None in practice. Both the Python and TypeScript test suites
construct `computed_at` with explicit UTC offsets (`datetime(…, tzinfo=UTC)` and
`"2026-07-12T00:00:00Z"`). If a naive datetime string ever reaches the Zod
schema, it will fail where the Pydantic side would have accepted it.

### 2. Immutability (`frozen=True`)

**Tag: allowed-difference**

Pydantic sets `frozen=True`, making the model immutable after construction.
Zod has no equivalent. The `.strict()` call only prevents extra properties, not
reassignment.

This is a Python-side concern. JavaScript consumers treat the parsed object as a
plain data structure. No runtime gap.

### 3. Field-level `title` metadata

**Tag: allowed-difference**

JSON Schema carries a `"title"` on every property (e.g., `"title": "Decision
Id"`). `x-to-zod` drops these. The top-level contract title
(`"DecisionRecordContract"`) is also absent from the Zod output.

Pure documentation metadata. No runtime impact.

### 4. `source_revision_set` minimum-length enforcement

**Tag: generated-equivalent**

| Layer | Mechanism |
|---|---|
| Pydantic | `Field(min_length=1)` on `dict[str, str]` |
| JSON Schema | `"minProperties": 1` |
| Zod | `.refine((obj) => Object.keys(obj).length >= 1, …)` |

JSON Schema's `minProperties` doesn't map to a native Zod primitive, so the
custom `addMinPropertiesRefinements()` post-processor injects a `.refine()`.
The constraint fires at parse time and rejects empty objects, same as Pydantic.
The error shape differs (Zod `ZodError` with refine message vs Pydantic
`ValidationError`), but the pass/fail boundary is identical.

### 5. All other fields

Every remaining field translates without semantic change:

- **`extra="forbid"` → `.strict()`** — both reject unknown properties.
- **`min_length=1` on strings → `.min(1)`** — identical check.
- **`min_length=64, max_length=64` on hashes → `.min(64).max(64)`** — identical.
- **`ge=1` on `int` → `.number().int().gte(1)`** — `.int()` checks
  `Number.isInteger()`, equivalent to Pydantic's `int` type constraint.
- **`str | None = Field(min_length=1)` → `.union([z.string().min(1), z.null()])`**
  — the `min_length` applies only to the string variant. Both sides agree.
- **`bool` → `z.boolean()`** — direct mapping.

## Summary

| # | Field(s) | Tag | Severity |
|---|---|---|---|
| 1 | `computed_at` | known-deviation | Low (no current test failure; strictness goes one way) |
| 2 | All fields (frozen) | allowed-difference | None |
| 3 | All fields (titles) | allowed-difference | None |
| 4 | `source_revision_set` | generated-equivalent | None |
| 5 | All other fields | generated-equivalent | None |

One known deviation, zero current breakage. The Zod schema is a strict subset
of what Pydantic accepts, restricted to timezone-aware datetime strings, which
is already how the contract is produced in practice.
