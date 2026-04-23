import { getByPath } from "@/lib/path"
import { describe, it, expect } from "vitest"

describe("getByPath", () => {
  it("navigates nested objects", () => {
    const obj = { system: { master_volume: 100 } }
    expect(getByPath(obj, "system.master_volume")).toBe(100)
  })

  it("handles array index", () => {
    const obj = { multi_part: [{ volume: 80 }, { volume: 90 }] }
    expect(getByPath(obj, "multi_part[1].volume")).toBe(90)
  })

  it("returns undefined for missing path", () => {
    expect(getByPath({}, "foo.bar")).toBeUndefined()
  })
})
