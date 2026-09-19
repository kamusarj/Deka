import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AiSettings from "./AiSettings";

const {
  getAiModelsMock,
  getAiProvidersMock,
  setAiModelMock,
  testLlmMock,
} = vi.hoisted(() => ({
  getAiModelsMock: vi.fn(),
  getAiProvidersMock: vi.fn(),
  setAiModelMock: vi.fn(),
  testLlmMock: vi.fn(),
}));

vi.mock("../contexts/useAuth", () => ({
  useAuth: () => ({ user: { role: "super_admin" } }),
}));

vi.mock("../services/api", () => ({
  getAiModels: getAiModelsMock,
  getAiProviders: getAiProvidersMock,
  setAiModel: setAiModelMock,
  testLlm: testLlmMock,
}));

const providers = [
  {
    provider: "openai",
    model: "gpt-4.1",
    verify_model: "gpt-4.1",
    configured: false,
    key_exposed: false,
    priority: 1,
    role: "primary",
  },
  {
    provider: "gemini",
    model: "gemini-2.0-flash",
    verify_model: "gemini-2.0-flash",
    configured: true,
    key_exposed: false,
    priority: 2,
    role: "fallback",
  },
  {
    provider: "deepseek",
    model: "deepseek-chat",
    verify_model: "deepseek-chat",
    configured: true,
    key_exposed: false,
    priority: 3,
    role: "fallback",
  },
];

describe("fixed AI provider chain", () => {
  beforeEach(() => {
    getAiProvidersMock.mockReset();
    getAiModelsMock.mockReset();
    setAiModelMock.mockReset();
    testLlmMock.mockReset();
    getAiProvidersMock.mockResolvedValue({
      active_provider: "openai",
      providers,
    });
    getAiModelsMock.mockResolvedValue({
      openai: { suggested: ["gpt-4.1"], current: "gpt-4.1", current_verify: "gpt-4.1" },
      gemini: { suggested: ["gemini-2.0-flash"], current: "gemini-2.0-flash", current_verify: "gemini-2.0-flash" },
      deepseek: { suggested: ["deepseek-chat"], current: "deepseek-chat", current_verify: "deepseek-chat" },
    });
    testLlmMock.mockResolvedValue({
      provider: "gemini",
      model: "gemini-2.0-flash",
      text: "Sẵn sàng",
    });
  });

  it("shows exactly OpenAI primary then Gemini and DeepSeek fallbacks", async () => {
    render(<AiSettings />);

    expect(await screen.findByText("1. OpenAI")).toBeInTheDocument();
    expect(screen.getByText("2. Google Gemini")).toBeInTheDocument();
    expect(screen.getByText("3. DeepSeek")).toBeInTheDocument();
    expect(screen.getByText("API chính · Chưa có key")).toBeInTheDocument();
    expect(screen.getByText("Dự phòng 1 · Đã cấu hình")).toBeInTheDocument();
    expect(screen.getByText("Dự phòng 2 · Đã cấu hình")).toBeInTheDocument();
    expect(screen.queryByText(/Mistral/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/OpenRouter/i)).not.toBeInTheDocument();
  });

  it("reports the fallback provider that actually answered the connection test", async () => {
    render(<AiSettings />);

    fireEvent.click(await screen.findByRole("button", { name: "Kiểm tra kết nối" }));

    expect(await screen.findByText("Google Gemini · gemini-2.0-flash: Sẵn sàng"))
      .toBeInTheDocument();
  });
});
