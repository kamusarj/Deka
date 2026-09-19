import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { DifficultyRatio } from "../types";
import DifficultyRatioInput from "./DifficultyRatioInput";

const standard: DifficultyRatio = { nhan_biet: 30, thong_hieu: 40, van_dung: 30 };

function ControlledInput({ initial = standard }: { initial?: DifficultyRatio }) {
  const [value, setValue] = useState(initial);
  return <DifficultyRatioInput value={value} onChange={setValue} />;
}

function slider(label: string) {
  return screen.getByRole("slider", { name: `Tỷ lệ ${label}` });
}

function percentageInput(label: string) {
  return screen.getByRole("spinbutton", { name: `Tỷ lệ ${label} (phần trăm)` });
}

function expectRatio(first: number, second: number, third: number) {
  expect(slider("Nhận biết")).toHaveValue(String(first));
  expect(slider("Thông hiểu")).toHaveValue(String(second));
  expect(slider("Vận dụng")).toHaveValue(String(third));
  expect(screen.getByRole("img", {
    name: `Tỷ lệ: Nhận biết ${first}%, Thông hiểu ${second}%, Vận dụng ${third}%`,
  })).toBeInTheDocument();
}

describe("DifficultyRatioInput", () => {
  it("keeps Nhận biết fixed after it is moved and lower sliders are adjusted", () => {
    render(<ControlledInput />);
    fireEvent.change(slider("Nhận biết"), { target: { value: "35" } });
    expectRatio(35, 40, 25);

    fireEvent.change(slider("Thông hiểu"), { target: { value: "50" } });
    expectRatio(35, 50, 15);

    fireEvent.change(slider("Vận dụng"), { target: { value: "30" } });
    expectRatio(35, 35, 30);
    expect(percentageInput("Nhận biết")).toHaveValue(35);
    expect(percentageInput("Thông hiểu")).toHaveValue(35);
    expect(percentageInput("Vận dụng")).toHaveValue(30);
  });

  it("allows reversing a drag while keeping the first percentage unchanged", () => {
    render(<ControlledInput initial={{ nhan_biet: 35, thong_hieu: 40, van_dung: 25 }} />);
    for (const value of [41, 60, 65, 30, 0, 40]) {
      fireEvent.change(slider("Thông hiểu"), { target: { value: String(value) } });
      expectRatio(35, value, 65 - value);
    }
  });

  it("restricts lower controls to the remaining percentage and handles 0 and 100", () => {
    render(<ControlledInput />);
    fireEvent.change(slider("Nhận biết"), { target: { value: "35" } });
    for (const label of ["Thông hiểu", "Vận dụng"]) {
      expect(slider(label)).toHaveAttribute("max", "65");
      expect(percentageInput(label)).toHaveAttribute("max", "65");
    }

    fireEvent.change(slider("Nhận biết"), { target: { value: "100" } });
    expectRatio(100, 0, 0);
    expect(slider("Thông hiểu")).toHaveAttribute("max", "0");
    expect(slider("Vận dụng")).toHaveAttribute("max", "0");

    fireEvent.change(slider("Nhận biết"), { target: { value: "0" } });
    expectRatio(0, 0, 100);
    expect(slider("Thông hiểu")).toHaveAttribute("max", "100");
  });

  it("lets a teacher clear and type a percentage without resetting it mid-entry", async () => {
    const user = userEvent.setup();
    render(<ControlledInput />);
    const input = percentageInput("Nhận biết");
    await user.clear(input);
    expect(input).toHaveValue(null);
    expectRatio(30, 40, 30);

    await user.type(input, "35");
    expect(input).toHaveValue(35);
    expectRatio(30, 40, 30);
    await user.tab();
    expect(input).toHaveValue(35);
    expectRatio(35, 40, 25);
  });

  it("restores an empty percentage on blur without changing the ratio", async () => {
    const user = userEvent.setup();
    render(<ControlledInput />);
    const input = percentageInput("Thông hiểu");
    await user.clear(input);
    expectRatio(30, 40, 30);
    await user.tab();
    expect(input).toHaveValue(40);
    expectRatio(30, 40, 30);
  });

  it("normalizes entered values on Enter and keeps the established first percentage", async () => {
    const user = userEvent.setup();
    render(<ControlledInput initial={{ nhan_biet: 35, thong_hieu: 40, van_dung: 25 }} />);
    const input = percentageInput("Thông hiểu");
    await user.clear(input);
    await user.type(input, "90{Enter}");
    expect(input).toHaveValue(65);
    expectRatio(35, 65, 0);
  });

  it("cancels a number edit with Escape and restores the previous distribution", async () => {
    const user = userEvent.setup();
    render(<ControlledInput initial={{ nhan_biet: 35, thong_hieu: 40, van_dung: 25 }} />);
    const input = percentageInput("Thông hiểu");
    await user.clear(input);
    await user.type(input, "50");
    expect(input).toHaveValue(50);
    expectRatio(35, 40, 25);
    await user.keyboard("{Escape}");
    expect(input).toHaveValue(40);
    expectRatio(35, 40, 25);
  });

  it("applies a preset completely when clicking it also blurs an unfinished number edit", async () => {
    const user = userEvent.setup();
    render(<ControlledInput />);
    await user.clear(percentageInput("Nhận biết"));
    await user.type(percentageInput("Nhận biết"), "90");
    await user.click(screen.getByRole("button", { name: "Cân bằng" }));
    expectRatio(33, 34, 33);
    expect(percentageInput("Nhận biết")).toHaveValue(33);
    expect(screen.getByRole("button", { name: "Cân bằng" })).toHaveAttribute("aria-pressed", "true");
  });

  it("does not mark a restored invalid total as valid and rebalances on the next adjustment", () => {
    render(<ControlledInput initial={{ nhan_biet: 30, thong_hieu: 40, van_dung: 20 }} />);
    expect(screen.getByText("Tổng: 90%")).toHaveClass("error");
    expect(screen.getByText("Tổng: 90%")).not.toHaveClass("pass");
    fireEvent.change(slider("Thông hiểu"), { target: { value: "45" } });
    expectRatio(30, 45, 25);
    expect(screen.getByText("Tổng: 100% ✓")).toHaveClass("pass");
  });

  it.each([
    { nhan_biet: 120, thong_hieu: -10, van_dung: -10 },
    { nhan_biet: 30, thong_hieu: -5, van_dung: 75 },
    { nhan_biet: 35.5, thong_hieu: 40, van_dung: 24.5 },
  ])("marks invalid individual restored percentages as errors even when they total 100", (initial) => {
    render(<ControlledInput initial={initial} />);
    expect(screen.getByText("Tổng: 100%")).toHaveClass("error");
    expect(screen.getByText("Tổng: 100%")).not.toHaveClass("pass");
    expect(screen.queryByText("Tổng: 100% ✓")).not.toBeInTheDocument();
  });

  it("uses nonnegative control bounds and repairs an invalid restored anchor when committing", async () => {
    const user = userEvent.setup();
    render(<ControlledInput initial={{ nhan_biet: 120, thong_hieu: -10, van_dung: -10 }} />);
    for (const label of ["Thông hiểu", "Vận dụng"]) {
      expect(slider(label)).toHaveAttribute("max", "0");
      expect(percentageInput(label)).toHaveAttribute("max", "0");
    }
    await user.clear(percentageInput("Thông hiểu"));
    await user.type(percentageInput("Thông hiểu"), "50{Enter}");
    expectRatio(100, 0, 0);
    expect(screen.getByText("Tổng: 100% ✓")).toHaveClass("pass");
  });

  it.each([
    ["Cân bằng", 33, 34, 33],
    ["Tiêu chuẩn 30/40/30", 30, 40, 30],
    ["Nặng vận dụng 20/40/40", 20, 40, 40],
  ] as const)("applies the complete %s preset after manual edits", async (name, first, second, third) => {
    const user = userEvent.setup();
    render(<ControlledInput initial={{ nhan_biet: 80, thong_hieu: 20, van_dung: 0 }} />);
    await user.click(screen.getByRole("button", { name }));
    expectRatio(first, second, third);
    expect(percentageInput("Nhận biết")).toHaveValue(first);
    expect(percentageInput("Thông hiểu")).toHaveValue(second);
    expect(percentageInput("Vận dụng")).toHaveValue(third);
  });
});
