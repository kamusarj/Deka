import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DemoApp from "./DemoApp";
import { seedExam } from "./data";

const storageKey = "deka-public-demo-v1";

function openDemo(path: string) {
  window.history.replaceState({}, "", `/#${path}`);
  return render(<DemoApp />);
}

beforeEach(() => {
  localStorage.clear();
  window.history.replaceState({}, "", "/");
});

describe("public demo workflow", () => {
  it("tells the visitor when browser storage cannot save their changes", async () => {
    const save = vi
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {
        throw new DOMException("Storage full", "QuotaExceededError");
      });
    try {
      openDemo("/dashboard");
      expect(await screen.findByRole("status")).toHaveTextContent(
        "không thể lưu",
      );
      expect(screen.getByRole("status")).toHaveTextContent("tải lại trang");
    } finally {
      save.mockRestore();
    }
  });

  it("tells the visitor when saved demo data cannot be read", async () => {
    const read = vi
      .spyOn(Storage.prototype, "getItem")
      .mockImplementation(() => {
        throw new DOMException("Storage blocked", "SecurityError");
      });
    try {
      openDemo("/dashboard");
      expect(await screen.findByRole("status")).toHaveTextContent(
        "không thể lưu",
      );
      expect(
        screen.getByRole("heading", { name: "Chào mừng đến với Deka." }),
      ).toBeInTheDocument();
    } finally {
      read.mockRestore();
    }
  });

  it("runs the public workflow without an API connection", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const xhrSpy = vi.spyOn(XMLHttpRequest.prototype, "open");
    try {
      const user = userEvent.setup();
      openDemo("/");
      await user.click(screen.getByRole("link", { name: "Thử tạo đề mẫu" }));
      await user.click(screen.getByRole("button", { name: "Tạo bộ đề mẫu" }));
      await user.click(
        screen.getAllByRole("button", { name: "Duyệt câu hỏi" })[0],
      );
      await user.click(screen.getByRole("link", { name: "Ngân hàng câu hỏi" }));
      await user.click(screen.getByRole("link", { name: "Tài liệu" }));
      expect(
        screen.getByRole("heading", { name: "Nguồn tham khảo mẫu" }),
      ).toBeInTheDocument();
      expect(fetchSpy).not.toHaveBeenCalled();
      expect(xhrSpy).not.toHaveBeenCalled();
    } finally {
      fetchSpy.mockRestore();
      xhrSpy.mockRestore();
    }
  });

  it("creates an exam from the selected settings and restores it after a reload", async () => {
    const user = userEvent.setup();
    const view = openDemo("/create");

    await user.selectOptions(screen.getByLabelText("Lớp"), "9");
    await user.selectOptions(
      screen.getByLabelText("Loại kiểm tra"),
      "Cuối kỳ II",
    );
    await user.selectOptions(screen.getByLabelText("Thời gian làm bài"), "90");
    await user.clear(screen.getByLabelText("Nội dung kiểm tra"));
    await user.type(
      screen.getByLabelText("Nội dung kiểm tra"),
      "Điện trở và an toàn điện",
    );
    await user.click(screen.getByRole("button", { name: "Tạo bộ đề mẫu" }));

    const title = "Đề kiểm tra Cuối kỳ II · KHTN 9";
    expect(
      await screen.findByRole("heading", { name: title, level: 1 }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Điện trở và an toàn điện · 90 phút · 10 điểm"),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("article")).toHaveLength(4);
    expect(
      screen.getByRole("heading", { name: /mức cản trở dòng điện/ }),
    ).toBeInTheDocument();

    view.unmount();
    render(<DemoApp />);

    expect(
      await screen.findByRole("heading", { name: title, level: 1 }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Điện trở và an toàn điện · 90 phút · 10 điểm"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "← Đề đã tạo" }));
    expect(
      await screen.findByRole("link", { name: new RegExp(title) }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Đề kiểm tra Giữa kỳ I · KHTN 8/ }),
    ).toBeInTheDocument();
  });

  it("adds an approved question to the bank and keeps that approval after a reload", async () => {
    const user = userEvent.setup();
    const view = openDemo("/exams/de-minh-hoa-khtn-8");
    const firstQuestion = screen.getAllByRole("article")[0];
    const questionText =
      within(firstQuestion).getByRole("heading").textContent!;

    await user.click(
      within(firstQuestion).getByRole("button", { name: "Duyệt câu hỏi" }),
    );
    expect(screen.getByText("1/4 câu")).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Ngân hàng câu hỏi" }));

    expect(
      await screen.findByRole("heading", { name: "Những câu hỏi đã duyệt" }),
    ).toBeInTheDocument();
    expect(screen.getByText(questionText)).toBeInTheDocument();
    expect(
      screen.queryByText("Chưa có câu hỏi được duyệt"),
    ).not.toBeInTheDocument();

    view.unmount();
    render(<DemoApp />);
    expect(screen.getByText(questionText)).toBeInTheDocument();
    await user.click(
      screen.getByRole("link", { name: (name) => name.includes(questionText) }),
    );
    expect(
      await screen.findByRole("button", { name: "✓ Đã duyệt" }),
    ).toBeInTheDocument();
  });

  it("shows a grade 6 matrix that matches the levels of its questions", async () => {
    const user = userEvent.setup();
    openDemo("/create");
    await user.selectOptions(screen.getByLabelText("Lớp"), "6");
    await user.click(screen.getByRole("button", { name: "Tạo bộ đề mẫu" }));

    expect(
      await screen.findByRole("heading", {
        name: "Đề kiểm tra Giữa kỳ I · KHTN 6",
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/^Nhận biết/)).toHaveLength(1);
    expect(screen.getAllByText(/^Thông hiểu/)).toHaveLength(2);
    expect(screen.getAllByText(/^Vận dụng/)).toHaveLength(1);

    await user.click(screen.getByRole("tab", { name: "Ma trận" }));
    const rows = within(screen.getByRole("table")).getAllByRole("row");
    expect(
      within(rows[1])
        .getAllByRole("cell")
        .map((cell) => cell.textContent),
    ).toEqual(["1 câu", "2 câu", "1 câu", "4 câu"]);
  });

  it("replaces a regenerated question with another local sample and asks for approval again", async () => {
    const user = userEvent.setup();
    openDemo("/exams/de-minh-hoa-khtn-8");
    const firstQuestion = screen.getAllByRole("article")[0];
    const originalText = within(firstQuestion).getByRole("heading").textContent;

    await user.click(
      within(firstQuestion).getByRole("button", { name: "Duyệt câu hỏi" }),
    );
    await user.click(
      within(firstQuestion).getByRole("button", { name: "Tạo lại bản mẫu" }),
    );

    const regenerated = screen.getAllByRole("article")[0];
    expect(within(regenerated).getByRole("heading").textContent).not.toEqual(
      originalText,
    );
    expect(
      within(regenerated).getByRole("button", { name: "Duyệt câu hỏi" }),
    ).toBeInTheDocument();
    expect(
      within(regenerated).queryByRole("button", { name: "✓ Đã duyệt" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("0/4 câu")).toBeInTheDocument();
  });

  it.each([
    ["invalid JSON", "{broken"],
    ["an empty collection", "[]"],
    ["duplicate exam IDs", JSON.stringify([seedExam, seedExam])],
    ["an incomplete exam", JSON.stringify([{ id: "broken", questions: [] }])],
    [
      "an invalid question",
      JSON.stringify([
        {
          id: "broken",
          title: "Invalid",
          grade: 8,
          term: "Giữa kỳ I",
          duration: 45,
          topic: "Invalid",
          createdAt: "2026-09-15T08:00:00.000Z",
          questions: [null],
        },
      ]),
    ],
  ])(
    "restores the sample safely when saved data contains %s",
    async (_description, savedData) => {
      const user = userEvent.setup();
      localStorage.setItem(storageKey, savedData);
      openDemo("/dashboard");

      expect(
        screen.getByRole("heading", { name: "Chào mừng đến với Deka." }),
      ).toBeInTheDocument();
      expect(screen.queryByRole("status")).not.toBeInTheDocument();
      await user.click(
        screen.getByRole("link", { name: /Đề kiểm tra Giữa kỳ I · KHTN 8/ }),
      );
      expect(
        await screen.findByRole("heading", {
          name: "Đề kiểm tra Giữa kỳ I · KHTN 8",
        }),
      ).toBeInTheDocument();
      expect(screen.getAllByRole("article")).toHaveLength(4);
    },
  );
});
