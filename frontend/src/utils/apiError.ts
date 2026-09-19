type ApiErrorShape = {
  response?: {
    data?: {
      detail?: string | Array<{ msg?: string }> | { message?: string };
      message?: string;
    };
  };
};

export function getApiErrorMessage(error: unknown, fallback: string): string {
  const data = (error as ApiErrorShape | null)?.response?.data;
  if (typeof data?.detail === "string" && data.detail.trim()) return data.detail;
  if (Array.isArray(data?.detail)) {
    const messages = data.detail.flatMap((item) =>
      typeof item?.msg === "string" && item.msg.trim() ? [item.msg] : [],
    );
    if (messages.length) return messages.join("; ");
  }
  if (data?.detail && !Array.isArray(data.detail) && typeof data.detail === "object"
    && typeof data.detail.message === "string" && data.detail.message.trim()) return data.detail.message;
  if (typeof data?.message === "string" && data.message.trim()) return data.message;
  if (error instanceof Error && error.message.trim()) return error.message;
  return fallback;
}
