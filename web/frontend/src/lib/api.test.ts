import { describe, it, expect, vi } from "vitest"
import { api } from "@/lib/api"

describe("api.uploadDevice", () => {
  it("constructs FormData with file", async () => {
    const mockResponse = {
      ok: true,
      json: () =>
        Promise.resolve({
          id: "test-id",
          device: { model: "qy70" },
          warnings: [],
        }),
    }
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(mockResponse as unknown as Response)

    const file = new File(["data"], "test.syx", { type: "application/octet-stream" })
    const result = await api.uploadDevice(file)

    expect(fetchSpy).toHaveBeenCalledWith("/api/devices", {
      method: "POST",
      body: expect.any(FormData),
    })
    expect(result.id).toBe("test-id")

    fetchSpy.mockRestore()
  })
})
