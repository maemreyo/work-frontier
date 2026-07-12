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

## Strict validation mode

Pydantic runs with `strict=True`, `frozen=True`, and `extra="forbid"`.
This disables type coercion at the model level:
- Strings are not coerced to int, bool, or datetime
- `AwareDatetime` requires timezone-aware ISO 8601 strings
- Unknown fields are rejected

Zod mirrors this with `.strict()` which prevents extra properties,
though Zod's `z.number().int()` still accepts numeric strings.
Both sides reject `"1"` as `int` and `"true"` as `bool` in strict mode.

## Observed differences

### 1. `computed_at` timezone enforcement

**Tag: generated-equivalent** (downgraded from known-deviation)

| Layer | Representation |
|---|---|
| Pydantic | `AwareDatetime` — requires timezone-aware ISO strings |
| JSON Schema | `{"type": "string", "format": "date-time"}` — no runtime enforcement |
| Zod | `z.string().datetime({ offset: true })` — requires timezone offset |

Pydantic now uses `AwareDatetime` which rejects naive datetime strings.
Both Pydantic and Zod require timezone-aware datetime. No semantic gap.

### 2. Type coercion rejection

**Tag: generated-equivalent**

Both Pydantic (`strict=True`) and Zod (`.strict()`) reject type coercion:
- `"1"` is not accepted as `int`
- `"true"` is not accepted as `bool`
- String hash values are rejected when regex pattern expects hex

### 3. Lowercase hex hash pattern

**Tag: generated-equivalent**

| Layer | Representation |
|---|---|
| Pydantic | `Field(pattern=r"^[0-9a-f]{64}$")` |
| JSON Schema | `"pattern": "^[0-9a-f]{64}$"` |
| Zod | `.regex(/^[0-9a-f]{64}$/)` |

All three hash fields (`normalized_snapshot_hash`, `policy_bundle_hash`,
`ranking_pipeline_hash`) enforce lowercase hex via regex pattern.

### 4. Immutability (`frozen=True`)

**Tag: allowed-difference**

Pydantic sets `frozen=True`, making the model immutable after construction.
Zod has no equivalent. The `.strict()` call only prevents extra properties, not
reassignment.

This is a Python-side concern. JavaScript consumers treat the parsed object as a
plain data structure. No runtime gap.

### 5. Field-level `title` metadata

**Tag: allowed-difference**

JSON Schema carries a `"title"` on every property (e.g., `"title": "Decision
Id"`). `x-to-zod` drops these. The top-level contract title
(`"DecisionRecordContract"`) is also absent from the Zod output.

Pure documentation metadata. No runtime impact.

### 6. `source_revision_set` minimum-length enforcement

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

### 7. `schema_version` default value

**Tag: allowed-difference**

| Layer | Representation |
|---|---|
| Pydantic | `Field(default="1.0.0")` |
| JSON Schema | `"default": "1.0.0"` |
| Zod | `.default("1.0.0")` |

When omitted from input, Pydantic and Zod both populate `schema_version`
with `"1.0.0"`. The parsed output always includes this field.

### 8. All other fields

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
| 1 | `computed_at` | generated-equivalent | None |
| 2 | Type coercion | generated-equivalent | None |
| 3 | Hash patterns | generated-equivalent | None |
| 4 | All fields (frozen) | allowed-difference | None |
| 5 | All fields (titles) | allowed-difference | None |
| 6 | `source_revision_set` | generated-equivalent | None |
| 7 | `schema_version` | allowed-difference | None |
| 8 | All other fields | generated-equivalent | None |

Zero known deviations. Pydantic and Zod agree on all validation boundaries.
The Zod schema is a faithful translation of the Pydantic model's strict
constraints.
