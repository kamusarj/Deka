const DEFAULT_MAX_UPLOAD_BYTES = 20 * 1024 * 1024;
const SUPPORTED_EXTENSIONS = new Set(["pdf", "docx", "xlsx", "png", "jpg", "jpeg"]);

export function parseMaxUploadBytes(configuredValue?: string): number {
  const parsed = Number(configuredValue);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : DEFAULT_MAX_UPLOAD_BYTES;
}

export const MAX_UPLOAD_BYTES = parseMaxUploadBytes(
  import.meta.env.VITE_MAX_UPLOAD_SIZE_BYTES,
);

function formatMegabytes(bytes: number): string {
  return `${Math.round((bytes / (1024 * 1024)) * 10) / 10} MB`;
}

export function validateDocumentFile(file: File): string | null {
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (!SUPPORTED_EXTENSIONS.has(extension)) return "Chỉ hỗ trợ file PDF, DOCX, XLSX hoặc ảnh PNG/JPEG.";
  if (file.size > MAX_UPLOAD_BYTES) {
    return `File vượt quá giới hạn ${formatMegabytes(MAX_UPLOAD_BYTES)}.`;
  }
  if (file.size === 0) return "File tải lên đang trống.";
  return null;
}
