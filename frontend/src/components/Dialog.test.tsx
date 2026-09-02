import { describe, expect, it, vi } from "vitest";
import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Dialog } from "./Dialog";
import { Button } from "./Button";

function Harness() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Open
      </button>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Delete recipe?"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={() => setOpen(false)}>
              Delete
            </Button>
          </>
        }
      >
        <p>This cannot be undone.</p>
      </Dialog>
    </>
  );
}

describe("Dialog", () => {
  it("is not in the DOM while closed", () => {
    render(<Harness />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("exposes a modal dialog with an accessible name from the title", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "Open" }));
    const dialog = screen.getByRole("dialog", { name: "Delete recipe?" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
  });

  it("moves focus into the dialog on open", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "Open" }));
    const dialog = screen.getByRole("dialog");
    expect(dialog.contains(document.activeElement)).toBe(true);
  });

  it("closes on Escape and restores focus to the opener", async () => {
    render(<Harness />);
    const opener = screen.getByRole("button", { name: "Open" });
    await userEvent.click(opener);
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });

  it("traps Tab within the dialog", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "Open" }));
    const close = screen.getByRole("button", { name: "Close dialog" });
    const del = screen.getByRole("button", { name: "Delete" });

    del.focus();
    await userEvent.tab();
    expect(close).toHaveFocus();

    await userEvent.tab({ shift: true });
    expect(del).toHaveFocus();
  });

  it("closes when the backdrop is clicked", async () => {
    const onClose = vi.fn();
    render(
      <Dialog open onClose={onClose} title="T">
        <p>body</p>
      </Dialog>,
    );
    await userEvent.click(screen.getByRole("dialog").parentElement!);
    expect(onClose).toHaveBeenCalled();
  });
});
