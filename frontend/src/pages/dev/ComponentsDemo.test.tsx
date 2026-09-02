import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToastProvider } from "../../components";
import ComponentsDemo from "./ComponentsDemo";

function renderDemo() {
  return render(
    <ToastProvider>
      <ComponentsDemo />
    </ToastProvider>,
  );
}

describe("ComponentsDemo", () => {
  it("renders a light and a dark pane, each forcing its theme", () => {
    renderDemo();
    const light = screen.getByRole("region", { name: "Light theme" });
    const dark = screen.getByRole("region", { name: "Dark theme" });
    expect(light).toHaveAttribute("data-theme", "light");
    expect(dark).toHaveAttribute("data-theme", "dark");
  });

  it("shows every primitive section in both panes", () => {
    renderDemo();
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

  it("opens the demo dialog from a pane", async () => {
    renderDemo();
    const dark = screen.getByRole("region", { name: "Dark theme" });
    await userEvent.click(
      within(dark).getByRole("button", { name: "Open dialog" }),
    );
    expect(
      screen.getByRole("dialog", { name: "Delete recipe?" }),
    ).toBeInTheDocument();
  });
});
