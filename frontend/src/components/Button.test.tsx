import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "./Button";

describe("Button", () => {
  it("renders a real <button> defaulting to type=button", () => {
    render(<Button>Save</Button>);
    const btn = screen.getByRole("button", { name: "Save" });
    expect(btn.tagName).toBe("BUTTON");
    expect(btn).toHaveAttribute("type", "button");
  });

  it("honors an explicit type", () => {
    render(<Button type="submit">Go</Button>);
    expect(screen.getByRole("button", { name: "Go" })).toHaveAttribute(
      "type",
      "submit",
    );
  });

  it("when loading, disables the button and marks it busy", async () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Saving
      </Button>,
    );
    const btn = screen.getByRole("button", { name: "Saving" });
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute("aria-busy", "true");
    await userEvent.click(btn);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("fires onClick when enabled", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Tap</Button>);
    await userEvent.click(screen.getByRole("button", { name: "Tap" }));
    expect(onClick).toHaveBeenCalledOnce();
  });
});
