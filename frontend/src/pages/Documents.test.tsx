import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Documents from "./Documents";
import { AuthContext } from "../contexts/authContextValue";
import type { AuthContextType } from "../contexts/authContextValue";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

const { getDocumentMock, listDocumentsMock, sharingMock, reviewMock, deleteMock, uploadMock } = vi.hoisted(() => ({
  getDocumentMock: vi.fn(),
  listDocumentsMock: vi.fn(),
  sharingMock: vi.fn(),
  reviewMock: vi.fn(),
  deleteMock: vi.fn(),
  uploadMock: vi.fn(),
}));

vi.mock("../services/api", () => ({
  deleteDocument: deleteMock,
  getDocument: getDocumentMock,
  listDocuments: listDocumentsMock,
  uploadDocument: uploadMock,
  updateDocumentSharing: sharingMock,
  reviewDocumentSharing: reviewMock,
}));

vi.mock("../contexts/useToast", () => ({
  useToast: () => ({ notify: vi.fn() }),
}));

describe("Documents content viewer", () => {
  beforeEach(() => {
    listDocumentsMock.mockReset();
    getDocumentMock.mockReset();
    sharingMock.mockReset();
    reviewMock.mockReset();
    deleteMock.mockReset();
    uploadMock.mockReset();
    listDocumentsMock.mockResolvedValue([
      {
        id: 7,
        filename: "chuong-te-bao.docx",
        file_type: "docx",
        size: 2048,
        status: "ready",
        grade: 6,
        text_preview: "Tế bào là...",
        text_length: 54,
      },
    ]);
    getDocumentMock.mockResolvedValue({
      id: 7,
      filename: "chuong-te-bao.docx",
      file_type: "docx",
      size: 2048,
      status: "ready",
      grade: 6,
      text_preview: "Tế bào là...",
      text_length: 54,
      extracted_text: "Tế bào là đơn vị cấu tạo cơ bản của cơ thể sống.",
    });
  });

  it("loads and displays the extracted document text", async () => {
    render(
      <MemoryRouter>
        <Documents />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Xem nội dung" }));

    expect(
      await screen.findByText("Tế bào là đơn vị cấu tạo cơ bản của cơ thể sống."),
    ).toBeInTheDocument();
    expect(getDocumentMock).toHaveBeenCalledWith(7);
  });

  function renderRole(role: string) {
    const auth = {
      user: { id: 1, email: "owner@example.test", name: "Owner", role, school_id: 2, is_active: true, created_at: null, can_change_password: true },
      isLoading: false, sessionError: null, isAuthenticated: true,
      login: vi.fn(), logout: vi.fn(), register: vi.fn(), refreshUser: vi.fn(),
    } satisfies AuthContextType;
    render(<MemoryRouter><AuthContext.Provider value={auth}><Documents /></AuthContext.Provider></MemoryRouter>);
  }

  const owned = {
    id: 7, filename: "owned.docx", file_type: "docx", size: 200, status: "extracted", text_length: 50,
    text_preview: "Content", owner_user_id: 1, school_id: 2,
    sharing_scope: "private", sharing_status: "none", version_id: 1,
    can_manage: true, can_share_school: true, can_review: false,
  };

  function select(name: string, option: string) {
    fireEvent.click(screen.getByRole("combobox", { name }));
    fireEvent.click(screen.getByRole("option", { name: option }));
  }

  it.each([
    ["Tự động · OCR khi cần", "auto"],
    ["Chỉ đọc văn bản có sẵn", "native"],
    ["Đọc lại ảnh/trang bằng OCR · bố cục hoặc công thức khó", "ocr"],
  ])("uploads with the selected %s mode and locks its menu during upload", async (label, mode) => {
    const pending = deferred<object>();
    uploadMock.mockReturnValue(pending.promise);
    renderRole("teacher");
    await screen.findByText("chuong-te-bao.docx");
    select("Cách đọc tài liệu", label);
    select("Lọc tài liệu theo khối", "Lớp 8");
    const file = new File(["%PDF-1.4"], "tai-lieu.pdf", { type: "application/pdf" });
    const dropzone = screen.getByText("Kéo thả PDF, DOCX, XLSX hoặc ảnh PNG/JPEG vào đây").closest(".upload-dropzone")!;
    fireEvent.click(screen.getByRole("combobox", { name: "Cách đọc tài liệu" }));
    fireEvent.drop(dropzone, { dataTransfer: { files: [file] } });
    expect(uploadMock).toHaveBeenCalledWith(file, 8, mode);
    expect(screen.getByRole("combobox", { name: "Cách đọc tài liệu" })).toBeDisabled();
    expect(screen.queryByRole("listbox", { name: "Cách đọc tài liệu" })).not.toBeInTheDocument();
    await act(async () => pending.resolve({}));
    expect(screen.getByRole("combobox", { name: "Cách đọc tài liệu" })).toBeEnabled();
    expect(screen.getByRole("combobox", { name: "Cách đọc tài liệu" })).toHaveTextContent(label);
  });

  it("keeps the current library when an older list request finishes later", async () => {
    const old = deferred<typeof owned[]>();
    listDocumentsMock.mockReturnValueOnce(old.promise).mockResolvedValue([{ ...owned, filename: "system.docx" }]);
    renderRole("teacher");
    select("Chọn kho tài liệu", "Toàn hệ thống");
    await screen.findByText("system.docx");
    await act(async () => old.resolve([{ ...owned, filename: "old-private.docx" }]));
    expect(screen.getByText("system.docx")).toBeInTheDocument();
    expect(screen.queryByText("old-private.docx")).not.toBeInTheDocument();
  });

  it("does not display errors from superseded library requests", async () => {
    const old = deferred<typeof owned[]>();
    listDocumentsMock.mockReturnValueOnce(old.promise).mockResolvedValue([owned]);
    renderRole("teacher");
    select("Chọn kho tài liệu", "Toàn hệ thống");
    await screen.findByText("owned.docx");
    await act(async () => old.reject(new Error("Stale request failed")));
    expect(screen.queryByText("Stale request failed")).not.toBeInTheDocument();
  });

  it("keeps the latest selected preview when earlier detail requests arrive late", async () => {
    const old = deferred<object>();
    listDocumentsMock.mockResolvedValue([owned, { ...owned, id: 8, filename: "second.docx" }]);
    getDocumentMock.mockReturnValueOnce(old.promise).mockResolvedValue({ ...owned, id: 8, filename: "second.docx", extracted_text: "Latest content" });
    renderRole("teacher");
    const buttons = await screen.findAllByRole("button", { name: "Xem nội dung" });
    fireEvent.click(buttons[0]);
    fireEvent.click(buttons[1]);
    await screen.findByText("Latest content");
    await act(async () => old.resolve({ ...owned, extracted_text: "Stale content" }));
    expect(screen.getByText("Latest content")).toBeInTheDocument();
    expect(screen.queryByText("Stale content")).not.toBeInTheDocument();
  });

  it("does not reopen a pending preview after changing libraries", async () => {
    const old = deferred<object>();
    listDocumentsMock.mockResolvedValueOnce([owned]).mockResolvedValue([]);
    getDocumentMock.mockReturnValue(old.promise);
    renderRole("teacher");
    fireEvent.click(await screen.findByRole("button", { name: "Xem nội dung" }));
    select("Chọn kho tài liệu", "Toàn hệ thống");
    await waitFor(() => expect(listDocumentsMock).toHaveBeenLastCalledWith(undefined, "system"));
    await act(async () => old.resolve({ ...owned, extracted_text: "Stale content" }));
    expect(screen.queryByText("Stale content")).not.toBeInTheDocument();
  });

  it("refreshes the currently selected library after a pending sharing update", async () => {
    const pending = deferred<object>();
    listDocumentsMock.mockResolvedValue([owned]);
    sharingMock.mockReturnValue(pending.promise);
    renderRole("teacher");
    await screen.findByText("owned.docx");
    select("Phạm vi chia sẻ của owned.docx", "Trong trường");
    select("Chọn kho tài liệu", "Toàn hệ thống");
    await waitFor(() => expect(listDocumentsMock).toHaveBeenLastCalledWith(undefined, "system"));
    await act(async () => pending.resolve({}));
    await waitFor(() => expect(listDocumentsMock).toHaveBeenCalledTimes(3));
    expect(listDocumentsMock).toHaveBeenLastCalledWith(undefined, "system");
  });

  it("lets owners share within school then request global approval and withdraw", async () => {
    let document = { ...owned };
    listDocumentsMock.mockImplementation(async () => [document]);
    sharingMock.mockImplementation(async (_id, scope, version) => {
      document = { ...document, sharing_scope: scope, sharing_status: scope === "system" ? "pending" : "none", version_id: version + 1 };
      return document;
    });
    renderRole("teacher");
    expect(await screen.findByRole("button", { name: "Xóa" })).toBeInTheDocument();
    select("Phạm vi chia sẻ của owned.docx", "Trong trường");
    await waitFor(() => expect(sharingMock).toHaveBeenCalledWith(7, "school", 1));
    expect(await screen.findByRole("button", { name: "Thu hồi chia sẻ" })).toBeInTheDocument();
    select("Phạm vi chia sẻ của owned.docx", "Toàn hệ thống · cần duyệt");
    await waitFor(() => expect(sharingMock).toHaveBeenCalledWith(7, "system", 2));
    expect(await screen.findByText("Toàn hệ thống · chờ duyệt")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Duyệt toàn hệ thống" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Thu hồi chia sẻ" }));
    await waitFor(() => expect(sharingMock).toHaveBeenCalledWith(7, "private", 3));
  });

  it("shows shared recipients read controls without mutation controls", async () => {
    listDocumentsMock.mockResolvedValue([{ ...owned, can_manage: false, can_share_school: false, sharing_scope: "system", sharing_status: "approved" }]);
    renderRole("teacher");
    expect(await screen.findByRole("button", { name: "Xem nội dung" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Xóa" })).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Phạm vi chia sẻ của owned.docx" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Thu hồi chia sẻ" })).not.toBeInTheDocument();
    select("Chọn kho tài liệu", "Toàn hệ thống");
    await waitFor(() => expect(listDocumentsMock).toHaveBeenLastCalledWith(undefined, "system"));
  });

  it("lets Super Admin review the pending library with an optional note", async () => {
    listDocumentsMock.mockResolvedValue([{ ...owned, sharing_scope: "system", sharing_status: "pending", version_id: 2, can_review: true }]);
    reviewMock.mockResolvedValue({});
    renderRole("super_admin");
    expect(await screen.findByRole("button", { name: "Duyệt toàn hệ thống" })).toBeInTheDocument();
    select("Chọn kho tài liệu", "Chờ duyệt toàn hệ thống");
    await waitFor(() => expect(listDocumentsMock).toHaveBeenLastCalledWith(undefined, "pending"));
    fireEvent.change(await screen.findByRole("textbox", { name: "Ghi chú duyệt owned.docx" }), { target: { value: "Nguồn phù hợp" } });
    fireEvent.click(screen.getByRole("button", { name: "Duyệt toàn hệ thống" }));
    await waitFor(() => expect(reviewMock).toHaveBeenCalledWith(7, "approve", 2, "Nguồn phù hợp"));
    expect(await screen.findByRole("button", { name: "Từ chối" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Từ chối" }));
    await waitFor(() => expect(reviewMock).toHaveBeenLastCalledWith(7, "reject", 2, "Nguồn phù hợp"));
  });

  it("blocks school sharing without school eligibility and supports resubmission", async () => {
    listDocumentsMock.mockResolvedValue([{ ...owned, can_share_school: false, sharing_scope: "system", sharing_status: "rejected", review_note: "Kiểm tra lại nguồn", version_id: 4 }]);
    sharingMock.mockResolvedValue({});
    renderRole("teacher");
    expect(await screen.findByText("Ghi chú duyệt: Kiểm tra lại nguồn")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("combobox", { name: "Phạm vi chia sẻ của owned.docx" }));
    expect(screen.getByRole("option", { name: "Trong trường" })).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(screen.getByRole("option", { name: "Trong trường" }));
    expect(sharingMock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Gửi duyệt lại" }));
    await waitFor(() => expect(sharingMock).toHaveBeenCalledWith(7, "system", 4));
  });
});
