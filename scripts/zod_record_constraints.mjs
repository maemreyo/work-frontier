/** Preserve JSON Schema record constraints that x-to-zod does not emit. */

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value)
}

function integerConstraint(value) {
  return Number.isInteger(value) && value >= 0 ? value : null
}

export function collectRecordConstraints(schema) {
  const constraints = []

  function visit(node, path, insideArray) {
    if (!isObject(node)) return

    const additionalProperties = node.additionalProperties
    const propertyNames = node.propertyNames
    const minProperties = integerConstraint(node.minProperties)
    const keyMinLength = isObject(propertyNames)
      ? integerConstraint(propertyNames.minLength)
      : null
    const isRecord = node.type === "object" && isObject(additionalProperties)

    if (isRecord && (minProperties !== null || keyMinLength !== null)) {
      if (insideArray) {
        throw new Error(
          `Record constraints inside arrays are unsupported at ${path.join(".")}`,
        )
      }
      constraints.push({ path: [...path], minProperties, keyMinLength })
    }

    if (isObject(node.properties)) {
      for (const [property, child] of Object.entries(node.properties)) {
        visit(child, [...path, property], insideArray)
      }
    }
    for (const keyword of ["allOf", "anyOf", "oneOf"]) {
      const variants = node[keyword]
      if (Array.isArray(variants)) {
        for (const variant of variants) visit(variant, path, insideArray)
      }
    }
    if (node.items !== undefined) visit(node.items, path, true)
  }

  visit(schema, [], false)
  return constraints
}

function accessExpression(path) {
  return path
    .map((segment, index) =>
      `${index === 0 ? "" : "?."}[${JSON.stringify(segment)}]`,
    )
    .join("")
}

function pathExpression(path, trailing = null) {
  const values = path.map((segment) => JSON.stringify(segment))
  if (trailing !== null) values.push(trailing)
  return `[${values.join(", ")}]`
}

export function renderRecordConstraintRefinement(
  schemaName,
  baseSchemaName,
  constraints,
) {
  if (constraints.length === 0) return ""
  const lines = [
    `export const ${schemaName} = ${baseSchemaName}.superRefine((value, ctx) => {`,
  ]
  constraints.forEach((constraint, index) => {
    const label = constraint.path.join(".") || "record"
    lines.push(`  const record${index} = value${accessExpression(constraint.path)}`)
    lines.push(`  if (record${index} != null) {`)
    if (constraint.minProperties !== null) {
      lines.push(
        `    if (Object.keys(record${index}).length < ${constraint.minProperties}) {`,
        "      ctx.addIssue({",
        '        code: "custom",',
        `        path: ${pathExpression(constraint.path)},`,
        `        message: ${JSON.stringify(`${label} must contain at least ${constraint.minProperties} property`)},`,
        "      })",
        "    }",
      )
    }
    if (constraint.keyMinLength !== null) {
      lines.push(
        `    for (const key of Object.keys(record${index})) {`,
        `      if (key.length < ${constraint.keyMinLength}) {`,
        "        ctx.addIssue({",
        '          code: "custom",',
        `          path: ${pathExpression(constraint.path, "key")},`,
        `          message: ${JSON.stringify(`${label} keys must contain at least ${constraint.keyMinLength} character`)},`,
        "        })",
        "      }",
        "    }",
      )
    }
    lines.push("  }")
  })
  lines.push("})")
  return lines.join("\n")
}
