import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Input, Select, Textarea } from "./Input";

describe("Input / Textarea / Select (standalone, no Field)", () => {
  it("Input is controlled and forwards value + onChange", async () => {
    const onChange = vi.fn();
    render(<Input aria-label="name" value="ab" onChange={onChange} />);
    const input = screen.getByLabelText("name");
    expect(input).toHaveValue("ab");
    await userEvent.type(input, "c");
    expect(onChange).toHaveBeenCalled();
  });

  it("honors an explicit aria-invalid and aria-describedby with no Field context", () => {
    render(
      <>
        <Input aria-label="x" aria-invalid aria-describedby="hint-x" />
        <span id="hint-x">bad</span>
      </>,
    );
    const input = screen.getByLabelText("x");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAttribute("aria-describedby", "hint-x");
  });

  it("Textarea and Select render their native elements and merge className", () => {
    render(
      <>
        <Textarea aria-label="notes" className="extra" />
        <Select aria-label="cuisine">
          <option>Italian</option>
        </Select>
      </>,
    );
    const ta = screen.getByLabelText("notes");
    expect(ta.tagName).toBe("TEXTAREA");
    expect(ta.className).toContain("extra");
    expect(screen.getByLabelText("cuisine").tagName).toBe("SELECT");
  });
});
