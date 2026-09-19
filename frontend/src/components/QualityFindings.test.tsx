import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import QualityFindings from "./QualityFindings";
import type { VerificationReport } from "../types";

const baseReport: VerificationReport = {
  overall_score: 56,
  overall_status: "passed_with_warnings",
  summary: { total_questions: 12, auto_approved: 7, needs_review: 5, auto_rejected: 0 },
  question_reports: [
    {
      question_id: "q_9",
      question_number: 9,
      verification_score: 72,
      status: "needs_review",
      issues: [],
    },
  ],
  action_required: [
    {
      priority: "medium",
      question_id: "q_9",
      message: "[DeepSeek V4 Pro] Phát biểu s_9_2 dùng từ mơ hồ 'có thể'.",
      fix: "[Gemini 3.7 Flash] Viết lại bằng điều kiện rõ ràng.",
    },
  ],
};

describe("QualityFindings", () => {
  it("renders nothing when no question needs an edit", () => {
    const { container } = render(
      <QualityFindings report={{ ...baseReport, action_required: [] }} />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("uses the display number and hides technical ids and summary scores", () => {
    render(<QualityFindings report={baseReport} />);

    expect(screen.getByRole("heading", { name: "Cần xem lại" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Câu 9" })).toHaveAttribute("href", "#question-q_9");
    expect(screen.getByText("Phát biểu b) dùng từ mơ hồ 'có thể'.")).toBeInTheDocument();
    expect(screen.getByText("Gợi ý: Viết lại bằng điều kiện rõ ràng.")).toBeInTheDocument();
    expect(screen.queryByText(/q_9|s_9_2|56|AI|không có cờ|DeepSeek|Gemini/i)).not.toBeInTheDocument();
  });

  it("shows comparison counts without provider branding even with no findings", () => {
    render(
      <QualityFindings
        report={{
          ...baseReport,
          action_required: [],
          reviewer_summary: {
            mode: "dual_mandatory",
            reviewers: [
              { label: "DeepSeek V4 Pro", provider: "deepseek", model: "deepseek-v4-pro" },
              { label: "Gemini 3.7 Flash", provider: "gemini", model: "gemini-3.7-flash" },
            ],
            consensus_questions: 12,
            reviewed_questions: 12,
            disagreement_questions: 0,
            unavailable_questions: 0,
            total_questions: 12,
          },
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Đối chiếu 2 trợ lý kiểm định" })).toBeInTheDocument();
    expect(screen.queryByText(/DeepSeek|Gemini|V4 Pro|3.7 Flash/i)).not.toBeInTheDocument();
    expect(screen.getByText("12/12 câu đồng thuận")).toBeInTheDocument();
    expect(screen.queryByText("Cần xem lại")).not.toBeInTheDocument();
  });

  it("labels a single review assistant without provider branding or consensus", () => {
    render(
      <QualityFindings
        report={{
          ...baseReport,
          action_required: [],
          reviewer_summary: {
            mode: "deepseek_only",
            reviewers: [
              { label: "DeepSeek V4 Pro", provider: "deepseek", model: "deepseek-v4-pro" },
            ],
            consensus_questions: 0,
            reviewed_questions: 12,
            disagreement_questions: 0,
            unavailable_questions: 0,
            total_questions: 12,
          },
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Trợ lý kiểm định" })).toBeInTheDocument();
    expect(screen.queryByText(/DeepSeek|V4 Pro/i)).not.toBeInTheDocument();
    expect(screen.getByText("12/12 câu đã kiểm định")).toBeInTheDocument();
    expect(screen.queryByText(/đồng thuận|Gemini|Đối chiếu 2/i)).not.toBeInTheDocument();
  });
});
