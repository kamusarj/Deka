import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ExamList from "./ExamList";

const { searchExamsMock } = vi.hoisted(() => ({
  searchExamsMock: vi.fn(),
}));

vi.mock("../contexts/useAuth", () => ({
  useAuth: () => ({ user: { id: 13, role: "teacher" } }),
}));

vi.mock("../services/api", () => ({
  searchExams: searchExamsMock,
}));

describe("ExamList publication status", () => {
  beforeEach(() => {
    searchExamsMock.mockReset();
    searchExamsMock.mockResolvedValue({
      items: [
        {
          id: 77,
          exam_number: 2,
          school: "THCS Nguyễn Du",
          grade: 8,
          subject: "Khoa học tự nhiên",
          exam_type: "Giữa học kì I",
          duration_minutes: 45,
          school_year: "2026-2027",
          total_score: 10,
          owner_user_id: 13,
          owner_name: "Giáo viên",
          school_id: null,
          publication_status: "draft",
          created_at: "2026-09-04T05:00:00Z",
        },
      ],
      total: 1,
      page: 1,
      page_size: 10,
    });
  });

  it("shows an explicit unverified draft badge", async () => {
    render(
      <MemoryRouter>
        <ExamList />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Bản nháp · chưa kiểm định")).toBeInTheDocument();
    expect(screen.getByText("#2")).toBeInTheDocument();
    expect(screen.queryByText("#77")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /THCS Nguyễn Du/ })).toHaveAttribute(
      "href",
      "/exams/77",
    );
  });
});
