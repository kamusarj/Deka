import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import SelectControl from "./SelectControl";

const gradeOptions = [
  { value: "", label: "Tất cả khối" },
  { value: 6, label: "Lớp 6" },
  { value: 7, label: "Lớp 7" },
  { value: 8, label: "Lớp 8", disabled: true },
];

describe("SelectControl", () => {
  it("opens a portalled listbox with selected and disabled states", async () => {
    const user = userEvent.setup();
    render(
      <SelectControl
        ariaLabel="Lọc theo khối"
        value={6}
        options={gradeOptions}
        onChange={vi.fn()}
      />,
    );

    const trigger = screen.getByRole("combobox", { name: "Lọc theo khối" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");

    await user.click(trigger);

    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("listbox", { name: "Lọc theo khối" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Lớp 6" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("option", { name: "Lớp 8" })).toHaveAttribute("aria-disabled", "true");
  });

  it("selects an enabled option once and closes the panel", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <SelectControl
        ariaLabel="Lọc theo khối"
        value={6}
        options={gradeOptions}
        onChange={onChange}
      />,
    );

    await user.click(screen.getByRole("combobox"));
    await user.click(screen.getByRole("option", { name: "Lớp 7" }));

    expect(onChange).toHaveBeenCalledOnce();
    expect(onChange).toHaveBeenCalledWith(7);
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("does not select disabled options", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <SelectControl
        ariaLabel="Lọc theo khối"
        value={6}
        options={gradeOptions}
        onChange={onChange}
      />,
    );

    await user.click(screen.getByRole("combobox"));
    await user.click(screen.getByRole("option", { name: "Lớp 8" }));

    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByRole("listbox")).toBeInTheDocument();
  });

  it("supports arrow selection and Escape without moving focus", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <SelectControl
        ariaLabel="Lọc theo khối"
        value={6}
        options={gradeOptions}
        onChange={onChange}
      />,
    );
    const trigger = screen.getByRole("combobox");

    trigger.focus();
    await user.keyboard("{ArrowDown}{ArrowDown}{Enter}");
    expect(onChange).toHaveBeenCalledWith(7);
    expect(trigger).toHaveFocus();

    await user.keyboard("{Enter}{Escape}");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("supports Home, End, and Tab while skipping disabled options", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <SelectControl
        ariaLabel="Lọc theo khối"
        value={6}
        options={gradeOptions}
        onChange={onChange}
      />,
    );
    const trigger = screen.getByRole("combobox");

    trigger.focus();
    await user.keyboard("{ArrowDown}{End}{Enter}");
    expect(onChange).toHaveBeenLastCalledWith(7);

    await user.keyboard("{Enter}{Home}{Enter}");
    expect(onChange).toHaveBeenLastCalledWith("");

    await user.keyboard("{Enter}{Tab}");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("supports type-ahead and click-outside dismissal", async () => {
    const user = userEvent.setup();
    render(
      <div>
        <SelectControl
          ariaLabel="Chọn AI"
          value="gemini"
          options={[
            { value: "gemini", label: "Gemini" },
            { value: "mistral", label: "Mistral" },
          ]}
          onChange={vi.fn()}
        />
        <button type="button">Bên ngoài</button>
      </div>,
    );

    const trigger = screen.getByRole("combobox");
    await user.click(trigger);
    await user.keyboard("m");

    const mistral = screen.getByRole("option", { name: "Mistral" });
    expect(trigger).toHaveAttribute("aria-activedescendant", mistral.id);

    await user.click(screen.getByRole("button", { name: "Bên ngoài" }));
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("cannot open when the whole control is disabled", async () => {
    const user = userEvent.setup();
    render(
      <SelectControl
        ariaLabel="Khối"
        value={6}
        options={gradeOptions}
        onChange={vi.fn()}
        disabled
      />,
    );

    const trigger = screen.getByRole("combobox");
    expect(trigger).toBeDisabled();
    await user.click(trigger);
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("closes an open popup when disabled and stays closed after re-enabling", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const props = {
      ariaLabel: "Khối",
      value: 6,
      options: gradeOptions,
      onChange,
    };
    const { rerender } = render(<SelectControl {...props} />);
    const trigger = screen.getByRole("combobox");

    await user.click(trigger);
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("listbox")).toBeInTheDocument();
    expect(trigger).toHaveAttribute("aria-activedescendant");

    rerender(<SelectControl {...props} disabled />);

    expect(trigger).toBeDisabled();
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(trigger).not.toHaveAttribute("aria-activedescendant");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    await user.click(trigger);
    await user.keyboard("{Enter}");
    expect(onChange).not.toHaveBeenCalled();

    rerender(<SelectControl {...props} />);

    expect(trigger).toBeEnabled();
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    await user.click(trigger);
    await user.click(screen.getByRole("option", { name: "Lớp 7" }));
    expect(onChange).toHaveBeenCalledExactlyOnceWith(7);
  });

  it("rejects a portalled selection after its native fieldset is disabled", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const { container } = render(
      <fieldset>
        <SelectControl
          ariaLabel="Khối"
          value={6}
          options={gradeOptions}
          onChange={onChange}
        />
      </fieldset>,
    );
    const trigger = screen.getByRole("combobox");

    await user.click(trigger);
    const option = screen.getByRole("option", { name: "Lớp 7" });
    const fieldset = container.querySelector("fieldset")!;
    fieldset.disabled = true;

    expect(trigger).toBeDisabled();
    fireEvent.click(option);
    expect(onChange).not.toHaveBeenCalled();
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();

    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });
});
