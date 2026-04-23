import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { UDMTree } from "@/components/UDMTree"

afterEach(() => cleanup())

describe("UDMTree", () => {
  it("renders humanized top-level labels", () => {
    render(
      <UDMTree
        device={{
          model: "qy70",
          multi_part: [],
          system: { master_volume: 100 },
        }}
        onSelect={vi.fn()}
        selectedPath={null}
      />,
    )

    expect(screen.getByText("Model")).toBeInTheDocument()
    expect(screen.getByText("Multi Part")).toBeInTheDocument()
    expect(screen.getByText("System")).toBeInTheDocument()
  })

  it("builds array paths without an extra dot", () => {
    const onSelect = vi.fn()
    render(
      <UDMTree
        device={{ patterns: [{ tempo_bpm: 120 }] }}
        onSelect={onSelect}
        selectedPath={null}
      />,
    )

    fireEvent.click(screen.getByText("Item 1"))

    expect(onSelect).toHaveBeenCalledWith("patterns[0]")
  })

  it("filters fields using the search query", () => {
    render(
      <UDMTree
        device={{
          system: { master_volume: 100, transpose: 0 },
        }}
        onSelect={vi.fn()}
        selectedPath={null}
        query="transpose"
      />,
    )

    expect(screen.getByText("Transpose")).toBeInTheDocument()
    expect(screen.queryByText("Master Volume")).not.toBeInTheDocument()
  })
})
