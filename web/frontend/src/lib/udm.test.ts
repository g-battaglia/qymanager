import { describe, expect, it } from "vitest"

import { getNodeSummary, humanizeKey, joinPath } from "@/lib/udm"

describe("udm helpers", () => {
  it("joins array paths without inserting a dot", () => {
    expect(joinPath("patterns", "[0]")).toBe("patterns[0]")
    expect(joinPath("patterns[0]", "tempo_bpm")).toBe("patterns[0].tempo_bpm")
  })

  it("humanizes common UDM keys", () => {
    expect(humanizeKey("multi_part")).toBe("Multi Part")
    expect(humanizeKey("master_volume")).toBe("Master Volume")
    expect(humanizeKey("[3]")).toBe("Item 4")
  })

  it("summarizes booleans and collections", () => {
    expect(getNodeSummary(true)).toBe("On")
    expect(getNodeSummary([1, 2])).toBe("2 items")
    expect(getNodeSummary({ a: 1 })).toBe("1 field")
  })
})
