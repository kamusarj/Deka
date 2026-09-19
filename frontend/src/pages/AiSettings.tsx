import axios from "axios";
import { useEffect, useState } from "react";
import { SelectControl } from "../components";
import { isSuperAdminRole } from "../auth/rolePolicy";
import { useAuth } from "../contexts/useAuth";
import { getAiProviders, getAiModels, setAiModel, testLlm } from "../services/api";
import type { AiProvider, AiProviderStatus, AiModelsResponse, AiProvidersResponse } from "../types";

const providerNames: Record<AiProvider, string> = {
  openai: "OpenAI",
  gemini: "Google Gemini",
  deepseek: "DeepSeek",
};

const providerRoles: Record<AiProvider, string> = {
  openai: "API chính",
  gemini: "Dự phòng 1",
  deepseek: "Dự phòng 2",
};

function getApiErrorMessage(error: unknown, fallback: string): string {
  if (!axios.isAxiosError(error)) return fallback;

  if (error.response?.status === 403) {
    return "Bạn không có quyền thực hiện thao tác AI này.";
  }
  if (error.response?.status === 401) {
    return "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.";
  }

  const detail = error.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

export default function AiSettings() {
  const { user } = useAuth();
  const canConfigureModel = isSuperAdminRole(user?.role);
  const [effective, setEffective] = useState<AiProvidersResponse["effective_config"]>();
  const [environmentOwned, setEnvironmentOwned] = useState(false);
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [testing, setTesting] = useState(false);
  const [providers, setProviders] = useState<AiProviderStatus[]>([]);
  const [modelsInfo, setModelsInfo] = useState<AiModelsResponse>({});
  const [editingProvider, setEditingProvider] = useState<string | null>(null);
  const [customModel, setCustomModel] = useState("");
  const [switchingModel, setSwitchingModel] = useState(false);
  const [modelNotice, setModelNotice] = useState("");

  useEffect(() => {
    getAiProviders().then((data) => { setProviders(data.providers); setEffective(data.effective_config); setEnvironmentOwned(data.configuration_source === "environment"); }).catch(() => setError("Không tải được trạng thái AI."));
    if (canConfigureModel) getAiModels().then(setModelsInfo).catch(() => undefined);
  }, [canConfigureModel]);

  async function changeModel(provider: string, model: string) {
    if (!model.trim()) return;
    setSwitchingModel(true); setModelNotice(""); setError("");
    try {
      const res = await setAiModel(provider as AiProvider, model.trim());
      setModelNotice(res.message);
      // Refresh data
      const modelsData = await getAiModels();
      setModelsInfo(modelsData);
      setEditingProvider(null);
      setCustomModel("");
    } catch (err) {
      setError(getApiErrorMessage(err, "Không đổi được model."));
    } finally { setSwitchingModel(false); }
  }

  async function runTest() {
    setTesting(true); setError(""); setResult("");
    try {
      const response = await testLlm("Trả lời đúng một từ: Sẵn sàng");
      setResult(`${providerNames[response.provider as AiProvider] ?? response.provider ?? "AI"} · ${response.model}: ${response.text}`);
    } catch (err) {
      setError(getApiErrorMessage(err, "Không kết nối được provider. Kiểm tra cấu hình backend/.env và khởi động lại Docker."));
    } finally { setTesting(false); }
  }

  return (
    <section className="settings-page">
      <div className="page-intro">
        <h1>Chuỗi API AI</h1>
        <p>Tạo đề tương tác dùng model chính; reviewer tuân theo cấu hình kiểm chứng. Các luồng cho phép dự phòng dùng OpenAI → Gemini → DeepSeek.</p>
        {environmentOwned && <p>Model được quản lý bằng environment. Cập nhật cấu hình và khởi động lại để áp dụng.</p>}
      </div>

      {canConfigureModel && effective && <section className="settings-section">
        <h2>Cấu hình đang có hiệu lực</h2>
        <dl>
          <dt>Model tạo đề tương tác</dt><dd>{effective.primary_only_model}</dd>
          <dt>Kiểm chứng</dt><dd>{effective.review_mode}</dd>
          <dt>Embedding tài liệu</dt><dd>{effective.embedding_model}</dd>
          <dt>Provider ưu tiên</dt><dd>{effective.default_provider_override || "Theo luồng xử lý"}</dd>
          {Object.entries(effective.tier_overrides).map(([tier, model]) => <div key={tier}><dt>{tier}</dt><dd>{model || "Mặc định"}</dd></div>)}
        </dl>
      </section>}
      <div className="ai-settings-card">
        <div className={`ai-status-dot ${providers.some((provider) => provider.configured) ? "online" : "offline"}`} />
        <strong>{providers.some((provider) => provider.configured) ? "Chuỗi AI đã có cấu hình" : "Chưa cấu hình API nào"}</strong>
        {canConfigureModel && (
          <button type="button" onClick={runTest} disabled={testing || !providers.some((provider) => provider.configured)}>
            {testing ? "Đang kiểm tra…" : "Kiểm tra kết nối"}
          </button>
        )}
      </div>

      <section className="settings-section">
        <div className="panel-header">
          <h2>Thứ tự sử dụng cố định</h2>
        </div>
        <div className="ai-provider-grid">
          {providers.map((provider) => {
            const providerName = provider.provider as AiProvider;
            const isPrimary = provider.role === "primary";
            return (
              <div key={provider.provider} className={`ai-provider-option fixed ${isPrimary ? "current" : ""}`}>
                <span>
                  <strong>{provider.priority}. {providerNames[providerName] ?? provider.provider}</strong>
                  <small>{provider.model || "Chưa có model"}</small>
                </span>
                <em>{providerRoles[providerName]} · {provider.configured ? "Đã cấu hình" : "Chưa có key"}</em>
              </div>
            );
          })}
        </div>
      </section>

      {canConfigureModel && <section className="settings-section">
        <div className="panel-header">
          <h2>Chọn model AI</h2>
        </div>

        {modelNotice && <p className="pass" style={{ marginBottom: "1rem" }}>{modelNotice}</p>}

        <div className="ai-model-list">
          {providers.map((provider) => {
            const info = modelsInfo[provider.provider];
            const isEditing = editingProvider === provider.provider;
            const isActive = provider.role === "primary";

            return (
              <div key={provider.provider} className={`ai-model-item ${isActive ? "ai-model-item-active" : ""}`}>
                <div className="ai-model-item-header">
                  <div>
                    <strong>{providerNames[provider.provider as AiProvider] ?? provider.provider}</strong>
                    <span className="badge badge-primary" style={{ marginLeft: "0.5rem" }}>
                      {providerRoles[provider.provider as AiProvider]}
                    </span>
                  </div>
                  {info && (
                    <span className="muted" style={{ fontSize: "0.82rem" }}>
                      {info.current}
                      {info.current_verify && info.current_verify !== info.current && (
                        <> · verify: {info.current_verify}</>
                      )}
                    </span>
                  )}
                </div>

                {environmentOwned ? <p className="muted">Cấu hình từ environment</p> : !isEditing ? (
                  <button
                    type="button"
                    className="secondary compact"
                    onClick={() => {
                      setEditingProvider(provider.provider);
                      setCustomModel(info?.current || "");
                    }}
                  >
                    Đổi model
                  </button>
                ) : (
                  <div className="ai-model-edit">
                    <SelectControl
                      ariaLabel={`Chọn model cho ${providerNames[provider.provider as AiProvider] ?? provider.provider}`}
                      value={customModel || info?.current || ""}
                      disabled={switchingModel}
                      onChange={(value) => {
                        if (value === "__custom") {
                          setCustomModel("");
                        } else {
                          changeModel(provider.provider, value);
                        }
                      }}
                      options={[
                        ...(info?.suggested || []).map((model) => ({ value: model, label: model })),
                        ...(info && !info.suggested.includes(info.current)
                          ? [{ value: info.current, label: `${info.current} (hiện tại)` }]
                          : []),
                        { value: "__custom", label: "Nhập model khác..." },
                      ]}
                    />
                    <div className="ai-model-custom-row">
                      <input
                        value={customModel}
                        onChange={(e) => setCustomModel(e.target.value)}
                        placeholder="Tên model tùy chỉnh"
                        onKeyDown={(e) => {
                          if (e.key === "Enter") { e.preventDefault(); changeModel(provider.provider, customModel); }
                        }}
                      />
                      <button
                        type="button"
                        className="compact"
                        onClick={() => changeModel(provider.provider, customModel)}
                        disabled={!customModel.trim() || switchingModel}
                      >
                        {switchingModel ? "..." : "Áp dụng"}
                      </button>
                      <button
                        type="button"
                        className="ghost-btn compact"
                        onClick={() => { setEditingProvider(null); setCustomModel(""); }}
                      >
                        Hủy
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>}

      {/* Test result & errors */}
      {result && <pre className="ai-test-result">{result}</pre>}
      {error && <p className="error">{error}</p>}

      <p className="settings-note">
        {canConfigureModel
          ? <>API key được giữ trong <code>backend/.env</code>. Không thể đổi thứ tự hoặc chọn provider ngoài chuỗi này.</>
          : "Liên hệ Super Admin nếu chuỗi API chưa sẵn sàng."}
      </p>
    </section>
  );
}
