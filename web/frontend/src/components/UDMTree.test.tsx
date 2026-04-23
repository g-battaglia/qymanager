import { render, screen, fireEvent } from "@testing-library/react"
import { describe, it, expect, vi } from "vitest"
import { UDMTree } from "@/components/UDMTree"

describe("UDMTree", () => {
  it("renders top-level keys", () => {
    const device = {
      model: "QY70",
      system: { master_volume: 100, transpose: 0 },
    }
    render(<UDMTree device={device} onSelect={vi.fn()} />)

    expect(screen.getAllByText(/model/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/system/).length).toBeGreaterThan(0)
  })

  it("expands nested objects on click", () => {
    const device = {
      system: { master_volume: 100 },
    }
    render(<UDMTree device={device} onSelect={vi.fn()} />)

    const buttons = screen.getAllByText(/system/)
    fireEvent.click(buttons[0])
    expect(screen.getAllByText(/master_volume/).length).toBeGreaterThan(0)
  })
})
