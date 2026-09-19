import { afterEach, describe, expect, it, vi } from "vitest";
import { AxiosError } from "axios";
import { api, authChangePassword, authGetMe, authLogout, exportDocx, exportPdf, generateFullExamStream } from "./api";
import { getToken, removeToken, setToken } from "../contexts/authStorage";
import type { ExamPayload } from "../types";

describe("separate exam document exports", () => {
  it.each([
    ["docx", exportDocx], ["pdf", exportPdf],
  ] as const)("forwards the document and selected code to the %s endpoint", async (format, exportFile) => {
    const adapter = api.defaults.adapter;
    const file = new Blob(["document"]);
    try {
      api.defaults.adapter = async (config) => {
        expect(config.url).toBe(`/api/exams/20/export-${format}`);
        expect(config.params).toEqual({ audience: "teacher", document: "matrix", variant_code: "102" });
        expect(config.responseType).toBe("blob");
        return { status: 200, statusText: "OK", data: file, headers: {}, config };
      };
      expect(await exportFile(20, "teacher", { document: "matrix", variant_code: "102" })).toBe(file);
    } finally {
      api.defaults.adapter = adapter;
    }
  });
});

describe("authentication transport", () => {
  it("sends password changes with the initiating session even if a new login arrives before dispatch", async () => {
    setToken("old-token", true);
    const adapter = api.defaults.adapter;
    try {
      api.defaults.adapter = async (config) => {
        expect(config.url).toBe("/api/auth/change-password");
        expect(config.headers.Authorization).toBe("Bearer old-token");
        return { status: 200, statusText: "OK", data: { access_token: "rotated-token" }, headers: {}, config };
      };
      const pending = authChangePassword("old-password", "new-password");
      setToken("new-token", true);
      await pending;
      expect(getToken()).toBe("new-token");
    } finally {
      api.defaults.adapter = adapter;
    }
  });

  it("bounds logout and revokes the token captured before a new login", async () => {
    setToken("old-token", true);
    const adapter = api.defaults.adapter;
    try {
      api.defaults.adapter = async (config) => {
        expect(config.url).toBe("/api/auth/logout");
        expect(config.headers.Authorization).toBe("Bearer old-token");
        expect(config.timeout).toBe(10000);
        return { status: 200, statusText: "OK", data: {}, headers: {}, config };
      };
      const pending = authLogout();
      setToken("new-token", true);
      await pending;
      expect(getToken()).toBe("new-token");
    } finally {
      api.defaults.adapter = adapter;
    }
  });

  afterEach(() => {
    removeToken();
    window.location.hash = "";
  });

  it.each(["current", "replaced", "anonymous"])("only invalidates the matching session on a %s request's 401", async (session) => {
    if (session !== "anonymous") setToken("original-token", true);
    window.location.hash = "#/dashboard";
    let rejectRequest!: () => void;
    let started!: () => void;
    const ready = new Promise<void>((resolve) => { started = resolve; });
    const request = api.get("/api/auth/me", {
      adapter: (config) => new Promise((_resolve, reject) => {
        rejectRequest = () => reject(new AxiosError("Unauthorized", "ERR_BAD_REQUEST", config, undefined, {
          status: 401, statusText: "Unauthorized", data: {}, headers: {}, config,
        }));
        started();
      }),
    });
    const rejected = expect(request).rejects.toMatchObject({ response: { status: 401 } });
    await ready;
    if (session !== "current") setToken("new-token", true);
    rejectRequest();
    await rejected;
    expect(getToken()).toBe(session === "current" ? null : "new-token");
    expect(window.location.hash).toBe(session === "current" ? "#/login" : "#/dashboard");
  });

  it("bounds the startup identity request and sends its saved token", async () => {
    setToken("saved-token", true);
    const adapter = api.defaults.adapter;
    try {
      api.defaults.adapter = async (config) => {
        expect(config.url).toBe("/api/auth/me");
        expect(config.timeout).toBe(10000);
        expect(config.headers.Authorization).toBe("Bearer saved-token");
        return { status: 200, statusText: "OK", data: { id: 1 }, headers: {}, config };
      };
      expect(await authGetMe()).toEqual({ id: 1 });
    } finally {
      api.defaults.adapter = adapter;
    }
  });
});

const payload = {
  school: "THCS Nguyễn Du",
  grade: 8,
  subject: "Khoa học tự nhiên",
  exam_type: "Giữa học kì I",
  duration_minutes: 45,
  school_year: "2026-2027",
  total_score: 10,
  curriculum: [],
  difficulty_ratio: { nhan_biet: 30, thong_hieu: 40, van_dung: 30 },
  question_types: {
    multiple_choice: { enabled: true, count: 8, score_per_question: 0.25 },
    true_false: { enabled: true, count: 4, score_per_question: 0.5 },
    short_answer: { enabled: true, count: 2, score_per_question: 0.5 },
    essay: { enabled: true, count: 2, score_per_question: 2.5 },
  },
  calculation_requirement: {
    count: 2,
    score_per_question: 0.5,
    difficulties: ["thong_hieu", "van_dung"],
  },
  auto_distribute_scores: true,
  allow_provider_fallback: false,
  variant_count: 1,
} satisfies ExamPayload;

describe("generateFullExamStream", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    removeToken();
    window.location.hash = "";
  });

  it.each(["current", "replaced", "anonymous"])("only invalidates the matching session on a %s stream's 401", async (session) => {
    if (session !== "anonymous") setToken("old-token", true);
    window.location.hash = "#/dashboard";
    let finish!: (response: Response) => void;
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise<Response>((resolve) => { finish = resolve; })));
    const pending = generateFullExamStream(payload, vi.fn());
    const rejected = expect(pending).rejects.toThrow("Expired");
    if (session !== "current") setToken("new-token", true);
    finish(new Response(JSON.stringify({ detail: "Expired" }), { status: 401 }));
    await rejected;
    expect(getToken()).toBe(session === "current" ? null : "new-token");
    expect(window.location.hash).toBe(session === "current" ? "#/login" : "#/dashboard");
  });

  it("shows the message in a structured generation rejection", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: { message: "Một số câu hỏi chưa hợp lệ", question_failures: [{ question_id: "q1" }] },
    }), { status: 422 })));
    await expect(generateFullExamStream(payload, vi.fn())).rejects.toThrow("Một số câu hỏi chưa hợp lệ");
  });

  it("surfaces an SSE error and always releases the reader lock", async () => {
    const releaseLock = vi.fn();
    const cancel = vi.fn().mockResolvedValue(undefined);
    const read = vi
      .fn()
      .mockResolvedValueOnce({
        done: false,
        value: new TextEncoder().encode(
          'data: {"stage":"error","status":"error","message":"Không thể tạo đề kiểm tra"}\n\n',
        ),
      })
      .mockResolvedValueOnce({ done: true, value: undefined });
    const body = { getReader: () => ({ read, cancel, releaseLock }) };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, body }),
    );

    await expect(generateFullExamStream(payload, vi.fn())).rejects.toThrow(
      "Không thể tạo đề kiểm tra",
    );
    expect(cancel).toHaveBeenCalledOnce();
    expect(releaseLock).toHaveBeenCalledOnce();
  });

  it("passes the caller abort signal to fetch", async () => {
    const controller = new AbortController();
    const fetchMock = vi.fn().mockRejectedValue(new DOMException("aborted", "AbortError"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      generateFullExamStream(payload, vi.fn(), controller.signal),
    ).rejects.toMatchObject({ name: "AbortError" });
    expect(fetchMock.mock.calls[0][1].signal).toBe(controller.signal);
  });
});
