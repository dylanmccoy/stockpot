import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Field } from "./Field";
import { Input, Select, Textarea } from "./Input";

describe("Field", () => {
  it("associates the label with the nested control", () => {
    render(
      <Field label="Recipe name">
        <Input />
      </Field>,
    );
    expect(screen.getByLabelText("Recipe name")).toHaveProperty(
      "tagName",
      "INPUT",
    );
  });

  it("links a hint via aria-describedby", () => {
    render(
      <Field label="Servings" hint="Whole number">
        <Input />
      </Field>,
    );
    const input = screen.getByLabelText("Servings");
    const describedBy = input.getAttribute("aria-describedby");
    expect(describedBy).toBeTruthy();
    expect(document.getElementById(describedBy!)).toHaveTextContent(
      "Whole number",
    );
    expect(input).not.toHaveAttribute("aria-invalid");
  });

  it("marks the control invalid and points aria-describedby at the error", () => {
    render(
      <Field label="Servings" hint="Whole number" error="Must be > 0">
        <Input />
      </Field>,
    );
    const input = screen.getByLabelText("Servings");
    expect(input).toHaveAttribute("aria-invalid", "true");
    const ids = input.getAttribute("aria-describedby")!.split(" ");
    const texts = ids.map((id) => document.getElementById(id)?.textContent);
    expect(texts).toContain("Whole number");
    expect(texts).toContain("Must be > 0");
    expect(screen.getByRole("alert")).toHaveTextContent("Must be > 0");
  });

  it("renders multiple errors as a list", () => {
    render(
      <Field label="Name" error={["Too short", "Already taken"]}>
        <Input />
      </Field>,
    );
    const items = screen.getAllByRole("listitem");
    expect(items.map((li) => li.textContent)).toEqual([
      "Too short",
      "Already taken",
    ]);
  });

  it("wires Textarea and Select the same way", () => {
    render(
      <>
        <Field label="Notes" error="bad">
          <Textarea />
        </Field>
        <Field label="Cuisine" error="bad">
          <Select>
            <option>Italian</option>
          </Select>
        </Field>
      </>,
    );
    expect(screen.getByLabelText("Notes")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(screen.getByLabelText("Cuisine")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  });

  it("propagates required to the nested control", () => {
    render(
      <Field label="Recipe name" required>
        <Input />
      </Field>,
    );
    expect(screen.getByLabelText(/Recipe name/)).toBeRequired();
  });

  it("lets an explicit id win over the generated one", () => {
    render(
      <Field label="Email" id="email-x">
        <Input />
      </Field>,
    );
    expect(screen.getByLabelText("Email")).toHaveAttribute("id", "email-x");
  });
});
