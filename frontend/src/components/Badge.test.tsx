import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "./Badge";

describe("Badge", () => {
  it("always renders a text label (status is never color-only)", () => {
    render(
      <Badge tone="warn" icon="!">
        Check what you have
      </Badge>,
    );
    expect(screen.getByText("Check what you have")).toBeInTheDocument();
  });

  it("hides a decorative icon from assistive tech", () => {
    const { container } = render(
      <Badge tone="ok" icon="✓">
        Available
      </Badge>,
    );
    expect(container.querySelector('[aria-hidden="true"]')).toHaveTextContent(
      "✓",
    );
  });
});
