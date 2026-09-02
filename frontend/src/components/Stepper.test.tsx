import { describe, expect, it, vi } from "vitest";
import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Stepper } from "./Stepper";

function Harness({ initial = 1 }: { initial?: number }) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <Stepper label="Multiplier" value={value} onChange={setValue} />
      <output data-testid="value">{value}</output>
    </>
  );
}

describe("Stepper", () => {
  it("exposes a labelled group", () => {
    render(<Harness />);
    expect(
      screen.getByRole("group", { name: "Multiplier" }),
    ).toBeInTheDocument();
  });

  it("sets the value from a preset and reflects it with aria-pressed", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "½" }));
    expect(screen.getByTestId("value")).toHaveTextContent("0.5");
    expect(screen.getByRole("button", { name: "½" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("increments and decrements by the step", async () => {
    render(<Harness initial={2} />);
    await userEvent.click(screen.getByRole("button", { name: "Increase" }));
    expect(screen.getByTestId("value")).toHaveTextContent("3");
    await userEvent.click(screen.getByRole("button", { name: "Decrease" }));
    expect(screen.getByTestId("value")).toHaveTextContent("2");
  });

  it("disables decrement when a step down would not stay > 0", () => {
    render(<Harness initial={1} />);
    expect(screen.getByRole("button", { name: "Decrease" })).toBeDisabled();
  });

  it("rejects a free-input value of 0 and snaps back", async () => {
    render(<Harness initial={3} />);
    const input = screen.getByLabelText("Exact value");
    await userEvent.clear(input);
    await userEvent.type(input, "0");
    await userEvent.tab();
    expect(screen.getByTestId("value")).toHaveTextContent("3");
    expect(input).toHaveValue(3);
  });

  it("accepts a valid free-input value", async () => {
    const onChange = vi.fn();
    render(<Stepper aria-label="M" value={1} onChange={onChange} />);
    const input = screen.getByLabelText("Exact value");
    await userEvent.clear(input);
    await userEvent.type(input, "2.5");
    await userEvent.tab();
    expect(onChange).toHaveBeenLastCalledWith(2.5);
  });
});
