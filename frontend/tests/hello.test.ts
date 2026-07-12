import { describe, expect, it } from "vitest"

import { helloContract } from "../src/hello"

describe("helloContract", () => {
  it("returns the stable product identifier when invoked", () => {
    // Given the Control Room bootstrap module
    // When its baseline contract is invoked
    const result = helloContract()

    // Then it identifies Work Frontier
    expect(result).toBe("work-frontier")
  })
})
