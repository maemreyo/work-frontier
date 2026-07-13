import assert from "node:assert/strict"
import test from "node:test"

import {
  collectRecordConstraints,
  renderRecordConstraintRefinement,
} from "./zod_record_constraints.mjs"

test("collects minProperties and propertyNames constraints", () => {
  const constraints = collectRecordConstraints({
    type: "object",
    properties: {
      source_revision_set: {
        type: "object",
        additionalProperties: { type: "string" },
        minProperties: 1,
        propertyNames: { minLength: 1 },
      },
    },
  })

  assert.deepEqual(constraints, [
    {
      path: ["source_revision_set"],
      minProperties: 1,
      keyMinLength: 1,
    },
  ])
})

test("renders a root superRefine without hard-coded field names", () => {
  const rendered = renderRecordConstraintRefinement(
    "DecisionRecordSchema",
    "DecisionRecordSchemaBase",
    [
      {
        path: ["source_revision_set"],
        minProperties: 1,
        keyMinLength: 1,
      },
    ],
  )

  assert.match(rendered, /Object\.keys\(record0\)\.length < 1/)
  assert.match(rendered, /path: \["source_revision_set"\]/)
  assert.match(rendered, /path: \["source_revision_set", key\]/)
})

test("fails closed for constrained records nested inside arrays", () => {
  assert.throws(
    () =>
      collectRecordConstraints({
        type: "array",
        items: {
          type: "object",
          additionalProperties: { type: "string" },
          minProperties: 1,
        },
      }),
    /inside arrays are unsupported/,
  )
})
