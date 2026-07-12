# Mutation Descriptor Types

This document defines the four executable mutation types used in ADR-006 preflight negative fixtures. Each mutation type targets a specific category of contract violation and produces an invalid document that should be rejected by the corresponding P0 contract validator.

## Schema Location

`mutation-schema.json` - JSON Schema defining the mutation descriptor structure

## Mutation Types

### 1. `remove_field`

**Purpose**: Remove a required field from the document to test missing data contract violations.

**Primary Contracts**: WF-P0-02 (reproducibility identity)

**Payload**: None required (the target specifies what to remove)

**Examples**:

```json
{
  "type": "remove_field",
  "target": "$.decision",
  "comment": "Removes the decision field to trigger WF-P0-02 missing reproducibility identity"
}
```

```json
{
  "type": "remove_field",
  "target": "$.source_revision_set",
  "comment": "Removes source_revision_set to trigger WF-P0-02 reproducibility identity violation"
}
```

**Use Cases**:
- Testing missing required fields that establish decision reproducibility
- Validating that essential identity fields are enforced
- Ensuring the schema rejects incomplete documents

**Target Format**: JSONPath expression pointing to the field to remove (e.g., `$.decision`, `$.workspace_id`, `$.source_revision_set.commit_sha`)

---

### 2. `add_invalid_field`

**Purpose**: Add a field that violates the schema's `additionalProperties: false` constraint to test taxonomy enforcement.

**Primary Contracts**: WF-P0-01 (taxonomy enforcement)

**Payload** (required):
- `field` (string): Name of the field to add
- `value` (any): Value to assign to the added field

**Examples**:

```json
{
  "type": "add_invalid_field",
  "target": "$",
  "payload": {
    "field": "extra_metadata",
    "value": "not_allowed"
  },
  "comment": "Adds field violating additionalProperties:false to trigger WF-P0-01 taxonomy enforcement"
}
```

```json
{
  "type": "add_invalid_field",
  "target": "$.source_revision_set",
  "payload": {
    "field": "unauthorized_field",
    "value": {"nested": "data"}
  },
  "comment": "Adds nested field violating strict schema to trigger WF-P0-01 taxonomy drift"
}
```

**Use Cases**:
- Testing schema strictness and taxonomy boundaries
- Validating that undocumented fields are rejected
- Ensuring the schema prevents ad-hoc field additions
- Testing nested object taxonomy enforcement

**Target Format**: JSONPath expression pointing to the object where the field should be added (use `$` for document root, `$.source_revision_set` for nested objects)

---

### 3. `violate_constraint`

**Purpose**: Change a field's value to violate its schema constraint (type, minimum, minLength, pattern, enum, etc.)

**Primary Contracts**: WF-P0-02, WF-P0-03, WF-P0-07

**Payload** (required):
- `invalid_value` (any): The value that violates the field's constraint

**Examples**:

```json
{
  "type": "violate_constraint",
  "target": "$.ranking_position",
  "payload": {
    "invalid_value": -1
  },
  "comment": "Sets ranking_position < 1 violating minimum constraint to trigger WF-P0-07"
}
```

```json
{
  "type": "violate_constraint",
  "target": "$.workspace_id",
  "payload": {
    "invalid_value": ""
  },
  "comment": "Sets workspace_id to empty string violating minLength constraint to trigger WF-P0-03"
}
```

```json
{
  "type": "violate_constraint",
  "target": "$.audit_anchor.timestamp",
  "payload": {
    "invalid_value": "not-a-timestamp"
  },
  "comment": "Sets timestamp to invalid format violating ISO 8601 constraint to trigger WF-P0-04"
}
```

**Use Cases**:
- Testing numeric constraints (minimum, maximum, exclusiveMinimum, etc.)
- Testing string constraints (minLength, maxLength, pattern)
- Testing format validations (date-time, email, uri, etc.)
- Testing enum restrictions
- Testing business rule constraints

**Target Format**: JSONPath expression pointing to the specific field to modify (e.g., `$.ranking_position`, `$.workspace_id`, `$.audit_anchor.timestamp`)

---

### 4. `malform_structure`

**Purpose**: Replace a field's value with a fundamentally wrong type to break the document structure.

**Primary Contracts**: WF-P0-04 (audit integrity)

**Payload** (required):
- `malformed` (any): The malformed value that violates the type constraint

**Examples**:

```json
{
  "type": "malform_structure",
  "target": "$.source_revision_set",
  "payload": {
    "malformed": []
  },
  "comment": "Changes object to array violating type constraint to trigger WF-P0-04 audit integrity"
}
```

```json
{
  "type": "malform_structure",
  "target": "$.alternatives",
  "payload": {
    "malformed": "not-an-array"
  },
  "comment": "Changes array to string violating type constraint to trigger WF-P0-02 or WF-P0-04"
}
```

**Use Cases**:
- Testing type constraints (object vs array vs primitive)
- Testing structural integrity of complex nested objects
- Validating that type coercion doesn't bypass validation
- Testing union type enforcement

**Target Format**: JSONPath expression pointing to the field whose structure should be malformed (e.g., `$.source_revision_set`, `$.alternatives`)

---

## Contract Mapping

| Mutation Type | Primary Contracts | Secondary Contracts | Typical Targets |
|---------------|-------------------|---------------------|-----------------|
| `remove_field` | WF-P0-02 | — | `$.decision`, `$.source_revision_set`, `$.workspace_id` |
| `add_invalid_field` | WF-P0-01 | — | `$`, `$.source_revision_set`, nested objects |
| `violate_constraint` | WF-P0-02, WF-P0-03, WF-P0-07 | WF-P0-04, WF-P0-05, WF-P0-06 | `$.ranking_position`, `$.workspace_id`, `$.audit_anchor.*` |
| `malform_structure` | WF-P0-04 | WF-P0-02 | `$.source_revision_set`, `$.alternatives`, complex objects |

## Execution Model

Each mutation descriptor is applied to a **valid baseline document** to produce an **invalid mutated document**. The preflight validator:

1. Loads the baseline document (a valid DecisionRecord or other entity)
2. Applies the mutation descriptor using the specified type and target
3. Runs the P0 contract validator against the mutated document
4. Verifies the validator rejects the document with the expected contract ID
5. Records the result as `rejected_by_contract` or flags a failure if validation passed

This approach ensures negative fixtures are **executable** rather than relying on prose assertions.

## JSONPath Target Format

All mutation types use JSONPath expressions to specify the target location:

- `$` - Document root
- `$.field` - Top-level field
- `$.nested.field` - Nested field (dot notation)
- `$.array[0]` - Array element by index
- `$.object.array[*]` - All array elements (use with caution)

**Note**: The mutation injection implementation (Task 10) will use a JSONPath library to resolve targets and apply mutations.

## Schema Validation

The mutation descriptor schema enforces:

1. **Type safety**: Only the 4 defined mutation types are allowed
2. **Required fields**: `type` and `target` are always required
3. **Conditional payloads**: 
   - `add_invalid_field` requires `payload.field` and `payload.value`
   - `violate_constraint` requires `payload.invalid_value`
   - `malform_structure` requires `payload.malformed`
   - `remove_field` does not require a payload
4. **No extra properties**: Schema uses `additionalProperties: false` to prevent undefined fields

## Next Steps

- **Task 10**: Implement mutation injection logic in `validate.mjs`
- **Task 11**: Add mutation descriptors to all 16 negative fixtures
- **Task 12**: Update validation to execute mutations and verify contract rejections
