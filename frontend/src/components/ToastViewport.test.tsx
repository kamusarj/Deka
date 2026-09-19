import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ToastViewport from "./ToastViewport";
import { ToastProvider } from "../contexts/ToastContext";
import { useToast } from "../contexts/useToast";

/** Minimal consumer that lets a test fire toasts through the public hook. */
function Trigger() {
  const { notify } = useToast();
  return (
    <>
      <button type="button" onClick={() => notify("Đã lưu đề", "success")}>
        fire-success
      </button>
      <button type="button" onClick={() => notify("Hỏng rồi", "error")}>
        fire-error
      </button>
    </>
  );
}

function renderToasts() {
  return render(
    <ToastProvider>
      <Trigger />
      <ToastViewport />
    </ToastProvider>,
  );
}

describe("ToastViewport", () => {
  it("renders nothing until a toast is fired", () => {
    renderToasts();
    expect(screen.queryByRole("region", { name: "Thông báo" })).not.toBeInTheDocument();
  });

  it("shows a fired toast", async () => {
    const user = userEvent.setup();
    renderToasts();

    await user.click(screen.getByText("fire-success"));

    expect(screen.getByText("Đã lưu đề")).toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("uses role=alert for errors so they interrupt", async () => {
    const user = userEvent.setup();
    renderToasts();

    await user.click(screen.getByText("fire-error"));

    expect(screen.getByRole("alert")).toHaveTextContent("Hỏng rồi");
  });

  it("stacks multiple toasts", async () => {
    const user = userEvent.setup();
    renderToasts();

    await user.click(screen.getByText("fire-success"));
    await user.click(screen.getByText("fire-error"));

    expect(screen.getByText("Đã lưu đề")).toBeInTheDocument();
    expect(screen.getByText("Hỏng rồi")).toBeInTheDocument();
  });

  it("dismisses on the close button", async () => {
    const user = userEvent.setup();
    renderToasts();

    await user.click(screen.getByText("fire-success"));
    await user.click(screen.getByRole("button", { name: "Đóng thông báo" }));

    expect(screen.queryByText("Đã lưu đề")).not.toBeInTheDocument();
  });
});

describe("ToastViewport auto-dismiss", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  /* fireEvent, not userEvent: userEvent awaits real delays, which never
     resolve while the timers are faked. */
  it("clears a toast after the timeout", () => {
    renderToasts();

    act(() => {
      fireEvent.click(screen.getByText("fire-success"));
    });
    expect(screen.getByText("Đã lưu đề")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(screen.queryByText("Đã lưu đề")).not.toBeInTheDocument();
  });
});
