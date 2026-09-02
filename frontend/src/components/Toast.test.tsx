import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { ToastProvider, useToast } from "./Toast";

function Trigger() {
  const { show } = useToast();
  return (
    <>
      <button
        type="button"
        onClick={() => show("Saved", { variant: "success" })}
      >
        success
      </button>
      <button type="button" onClick={() => show("Boom", { variant: "error" })}>
        error
      </button>
    </>
  );
}

function renderWithProvider() {
  return render(
    <ToastProvider>
      <Trigger />
    </ToastProvider>,
  );
}

afterEach(() => {
  vi.useRealTimers();
});

describe("Toast", () => {
  it("throws when used outside a provider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Trigger />)).toThrow(/ToastProvider/);
    spy.mockRestore();
  });

  it("announces toasts through a polite live region", () => {
    renderWithProvider();
    fireEvent.click(screen.getByRole("button", { name: "success" }));
    const region = screen.getByRole("region", { name: "Notifications" });
    expect(region).toHaveAttribute("aria-live", "polite");
    expect(region).toHaveTextContent("Saved");
  });

  it("auto-dismisses a non-error toast, pausing while hovered", () => {
    vi.useFakeTimers();
    renderWithProvider();
    fireEvent.click(screen.getByRole("button", { name: "success" }));

    const toast = screen.getByText("Saved").closest('[role="status"]')!;
    fireEvent.mouseEnter(toast);
    act(() => void vi.advanceTimersByTime(10_000));
    expect(screen.getByText("Saved")).toBeInTheDocument();

    fireEvent.mouseLeave(toast);
    act(() => void vi.advanceTimersByTime(5_000));
    expect(screen.queryByText("Saved")).not.toBeInTheDocument();
  });

  it("keeps an error toast until it is dismissed", () => {
    vi.useFakeTimers();
    renderWithProvider();
    fireEvent.click(screen.getByRole("button", { name: "error" }));

    act(() => void vi.advanceTimersByTime(60_000));
    expect(screen.getByText("Boom")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Dismiss notification" }),
    );
    expect(screen.queryByText("Boom")).not.toBeInTheDocument();
  });
});
