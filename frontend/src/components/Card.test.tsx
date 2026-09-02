import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Card } from "./Card";

describe("Card", () => {
  it("renders its children", () => {
    render(
      <Card>
        <span>panel body</span>
      </Card>,
    );
    expect(screen.getByText("panel body")).toBeInTheDocument();
  });

  it("merges an extra className and forwards DOM props", () => {
    render(
      <Card className="extra" data-testid="c" aria-label="Weeknight pasta">
        x
      </Card>,
    );
    const el = screen.getByTestId("c");
    expect(el.className).toContain("extra");
    expect(el).toHaveAttribute("aria-label", "Weeknight pasta");
  });
});
