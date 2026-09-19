import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Community from "./Community";
import CommunityTopic from "./CommunityTopic";
import PublishQuestionButton from "../components/PublishQuestionButton";
import { AuthContext, type AuthContextType } from "../contexts/authContextValue";

const api = vi.hoisted(() => ({
  listCommunityTopics: vi.fn(), getCommunityTopic: vi.fn(), createCommunityTopic: vi.fn(),
  listCommunityComments: vi.fn(), addCommunityComment: vi.fn(), deleteCommunityComment: vi.fn(),
  deleteCommunityTopic: vi.fn(), saveCommunityQuestion: vi.fn(), publishBankQuestion: vi.fn(),
}));
vi.mock("../services/api", () => api);
const question = { id: 7, content: "Tim có bao nhiêu ngăn?", type: "multiple_choice" as const,
  difficulty: "nhan_biet" as const, grade: 8, subject: "Khoa học tự nhiên", tags: [], usage_count: 0,
  options: { A: "Hai", B: "Bốn" }, answer: { correct_answer: "B", explanation: "Gồm hai tâm nhĩ và hai tâm thất." } };
const topic = { id: 7, title: "Cấu tạo tim", preview: question.content, type: question.type,
  difficulty: question.difficulty, grade: 8, author: { id: 1, name: "Lan" }, created_at: "2026-09-07T03:00:00Z",
  can_manage: false, comment_count: 1, question };
const comment = { id: 3, parent_id: null, body: "Tại sao?", deleted: false, author: { id: 2, name: "Minh" }, created_at: topic.created_at, can_manage: false };
function renderForum(path = "/community", role = "teacher") {
  return render(<AuthContext.Provider value={{ user: { id: 1, role } } as AuthContextType}>
    <MemoryRouter initialEntries={[path]}><Routes>
      <Route path="/community" element={<Community />} />
      <Route path="/community/:id" element={<CommunityTopic />} />
    </Routes></MemoryRouter></AuthContext.Provider>);
}
beforeEach(() => {
  Object.values(api).forEach(mock => mock.mockReset());
  api.listCommunityTopics.mockResolvedValue({ items: [topic], total: 1, page: 1, page_size: 20 });
  api.getCommunityTopic.mockResolvedValue(topic);
  api.listCommunityComments.mockResolvedValue({ items: [comment], total: 1, page: 1, page_size: 50 });
  api.addCommunityComment.mockResolvedValue({ id: 4 });
  api.saveCommunityQuestion.mockResolvedValue({ id: 77 });
  api.createCommunityTopic.mockResolvedValue(topic);
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

describe("Community forum", () => {
  it("searches and paginates topics with navigable discussion links", async () => {
    api.listCommunityTopics.mockResolvedValue({ items: [topic], total: 25, page: 1, page_size: 20 });
    renderForum();
    expect(await screen.findByRole("link", { name: "Cấu tạo tim" })).toHaveAttribute("href", "/community/7");
    fireEvent.click(screen.getByRole("button", { name: "Trang sau" }));
    await waitFor(() => expect(api.listCommunityTopics).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 }), expect.any(AbortSignal)));
    await screen.findByRole("link", { name: "Cấu tạo tim" });
    fireEvent.change(screen.getByLabelText("Tìm câu hỏi cộng đồng"), { target: { value: "tim" } });
    await waitFor(() => expect(api.listCommunityTopics).toHaveBeenLastCalledWith(expect.objectContaining({ search: "tim", page: 1 }), expect.any(AbortSignal)));
  });

  it("publishes a complete multiple choice question immediately and opens its topic", async () => {
    renderForum("/community", "viewer");
    fireEvent.click(screen.getByRole("button", { name: "Đăng câu hỏi" }));
    fireEvent.change(screen.getByLabelText("Tiêu đề chủ đề"), { target: { value: "Tìm hiểu tim" } });
    fireEvent.change(screen.getByLabelText("Nội dung câu hỏi"), { target: { value: "Tim có mấy ngăn?" } });
    ["A", "B", "C", "D"].forEach((key, i) => fireEvent.change(screen.getByLabelText(`Phương án ${key}`), { target: { value: String(i+1) } }));
    fireEvent.click(screen.getByRole("button", { name: "Đăng lên cộng đồng" }));
    await waitFor(() => expect(api.createCommunityTopic).toHaveBeenCalledWith("Tìm hiểu tim", expect.objectContaining({
      content: "Tim có mấy ngăn?", options: { A: "1", B: "2", C: "3", D: "4" }, type: "multiple_choice",
    })));
    expect(await screen.findByRole("heading", { name: "Cấu tạo tim" })).toBeInTheDocument();
  });

  it("lets viewers reply without private-bank or moderation rights", async () => {
    renderForum("/community/7", "viewer");
    await screen.findByText("Tại sao?");
    expect(screen.queryByRole("button", { name: "Lưu vào ngân hàng của tôi" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Gỡ chủ đề" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Gỡ bình luận" })).not.toBeInTheDocument();
    const answer = screen.getByText("Xem đáp án và giải thích").closest("details");
    expect(answer).not.toHaveAttribute("open");
    fireEvent.click(screen.getByRole("button", { name: "Trả lời" }));
    expect(screen.getByText("Đang trả lời Minh · #3")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Bình luận của bạn"), { target: { value: "Vì có hai tâm thất." } });
    fireEvent.click(screen.getByRole("button", { name: "Gửi bình luận" }));
    await waitFor(() => expect(api.addCommunityComment).toHaveBeenCalledWith(7, "Vì có hai tâm thất.", 3));
    await waitFor(() => expect(screen.getByLabelText("Bình luận của bạn")).toHaveValue(""));
  });

  it("retains a failed comment draft and saves a question to the personal bank", async () => {
    api.addCommunityComment.mockRejectedValue(new Error("Offline"));
    renderForum("/community/7");
    await screen.findByText("Tại sao?");
    fireEvent.change(screen.getByLabelText("Bình luận của bạn"), { target: { value: "Bản nháp cần giữ" } });
    fireEvent.click(screen.getByRole("button", { name: "Gửi bình luận" }));
    await screen.findByRole("alert");
    expect(screen.getByLabelText("Bình luận của bạn")).toHaveValue("Bản nháp cần giữ");
    fireEvent.click(screen.getByRole("button", { name: "Lưu vào ngân hàng của tôi" }));
    await waitFor(() => expect(api.saveCommunityQuestion).toHaveBeenCalledWith(7));
    expect(await screen.findByRole("button", { name: "Đã lưu vào ngân hàng" })).toBeDisabled();
  });

  it("shows removed-comment placeholders and lets authorized users remove content", async () => {
    api.getCommunityTopic.mockResolvedValue({ ...topic, can_manage: true });
    api.listCommunityComments.mockResolvedValue({ items: [
      { ...comment, body: null, deleted: true },
      { ...comment, id: 4, parent_id: 3, body: '<img src=x onerror="alert(1)">', can_manage: true },
    ], total: 2, page: 1, page_size: 50 });
    renderForum("/community/7");
    expect(await screen.findByText("Bình luận đã được gỡ.")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    const deleted = screen.getByText("Bình luận đã được gỡ.").closest("article")!;
    expect(within(deleted).queryByRole("button")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Gỡ bình luận" }));
    await waitFor(() => expect(api.deleteCommunityComment).toHaveBeenCalledWith(7, 4));
    await waitFor(() => expect(screen.getByRole("button", { name: "Gỡ chủ đề" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Gỡ chủ đề" }));
    await waitFor(() => expect(api.deleteCommunityTopic).toHaveBeenCalledWith(7));
    expect(await screen.findByRole("heading", { name: "Ngân hàng câu hỏi cộng đồng" })).toBeInTheDocument();
  });

  it("clears unavailable topic content and offers retry", async () => {
    api.getCommunityTopic.mockRejectedValue(new Error("Removed"));
    renderForum("/community/7");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByLabelText("Bình luận của bạn")).not.toBeInTheDocument();
    api.getCommunityTopic.mockResolvedValue(topic);
    fireEvent.click(screen.getByRole("button", { name: "Thử lại" }));
    expect(await screen.findByRole("heading", { name: "Cấu tạo tim" })).toBeInTheDocument();
  });

  it("publishes bank content only after the explicit sharing action", async () => {
    api.publishBankQuestion.mockResolvedValue(topic);
    render(<MemoryRouter initialEntries={["/bank"]}><Routes>
      <Route path="/bank" element={<PublishQuestionButton question={question} />} />
      <Route path="/community/:id" element={<p>Chủ đề đã đăng</p>} />
    </Routes></MemoryRouter>);
    expect(api.publishBankQuestion).not.toHaveBeenCalled();
    vi.mocked(window.confirm).mockReturnValueOnce(false);
    fireEvent.click(screen.getByRole("button", { name: "Chia sẻ lên cộng đồng" }));
    expect(api.publishBankQuestion).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Chia sẻ lên cộng đồng" }));
    await waitFor(() => expect(api.publishBankQuestion).toHaveBeenCalledWith(7, question.content));
    expect(await screen.findByText("Chủ đề đã đăng")).toBeInTheDocument();
  });

  it("shows the saved essay grading guide and scoring criteria in answer details", async () => {
    api.getCommunityTopic.mockResolvedValue({ ...topic, type: "essay", question: { ...question, type: "essay", options: null,
      answer: { model_answer: "Lời giải tham khảo", key_points: ["Giải thích nguyên nhân"],
        rubric: { total_score: 2, grading_guide: ["Chấp nhận cách giải tương đương"], criteria: [
          { id: "c1", name: "Lập luận khoa học", max_score: 2, levels: [{ score: 2, description: "Đầy đủ", criteria: "Nêu đúng hai nguyên nhân" }] },
        ] } },
    } });
    renderForum("/community/7");
    await screen.findByRole("heading", { name: "Cấu tạo tim" });
    const details = screen.getByText("Xem đáp án và giải thích").closest("details")!;
    fireEvent.click(within(details).getByText("Xem đáp án và giải thích"));
    expect(within(details).getByText("Chấp nhận cách giải tương đương")).toBeInTheDocument();
    expect(within(details).getByText("Lập luận khoa học")).toBeInTheDocument();
    expect(within(details).getByText(/Nêu đúng hai nguyên nhân/)).toBeInTheDocument();
    expect(within(details).getByText("Giải thích nguyên nhân")).toBeInTheDocument();
  });

  it("shows per-statement explanations in the matching statement order", async () => {
    api.getCommunityTopic.mockResolvedValue({ ...topic, type: "true_false", question: { ...question, type: "true_false", options: null,
      statements: [{ id: "s1", content: "Mệnh đề thứ nhất" }, { id: "s2", content: "Mệnh đề thứ hai" }],
      answer: { answers: [{ statement_id: "s2", is_true: false, explanation: "Vì điều kiện không thỏa mãn." }] },
    } });
    renderForum("/community/7");
    await screen.findByRole("heading", { name: "Cấu tạo tim" });
    const details = screen.getByText("Xem đáp án và giải thích").closest("details")!;
    fireEvent.click(within(details).getByText("Xem đáp án và giải thích"));
    expect(within(details).getByText(/Vì điều kiện không thỏa mãn/)).toHaveTextContent("b) Vì điều kiện không thỏa mãn.");
  });
});
