import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ComponentsDemo from "./ComponentsDemo";

describe("ComponentsDemo", () => {
  it("exposes a single <main> landmark", () => {
    render(<ComponentsDemo />);
    expect(screen.getByRole("main")).toBeInTheDocument();
  });

  it("renders a light and a dark pane, each forcing its theme", () => {
    render(<ComponentsDemo />);
    const light = screen.getByRole("region", { name: "Light theme" });
    const dark = screen.getByRole("region", { name: "Dark theme" });
    expect(light).toHaveAttribute("data-theme", "light");
    expect(dark).toHaveAttribute("data-theme", "dark");
  });

  it("shows every primitive section in both panes", () => {
    render(<ComponentsDemo />);
    for (const pane of ["Light theme", "Dark theme"]) {
      const region = screen.getByRole("region", { name: pane });
      for (const heading of [
        "Buttons",
        "Fields",
        "Card",
        "Badges",
        "Stepper",
        "DataTable",
        "Overlays",
      ]) {
        expect(
          within(region).getByRole("heading", { name: heading }),
        ).toBeInTheDocument();
      }
    }
  });

  it("opens the demo dialog inside the originating themed pane", async () => {
    render(<ComponentsDemo />);
    const dark = screen.getByRole("region", { name: "Dark theme" });
    await userEvent.click(
      within(dark).getByRole("button", { name: "Open dialog" }),
    );
    const dialog = within(dark).getByRole("dialog", { name: "Delete recipe?" });
    expect(dialog).toBeInTheDocument();
  });
});
