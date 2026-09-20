from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULT_SECRET_KEY = "smart-exam-secret-key-change-in-production-2026"


class Settings(BaseSettings):
    APP_NAME: str = "Deka"
    ENV: str = "development"

    # Auth / JWT
    SECRET_KEY: str = INSECURE_DEFAULT_SECRET_KEY
    MFA_ENCRYPTION_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    ACCOUNT_TOKEN_EXPIRE_MINUTES: int = Field(default=60, ge=5, le=60 * 24)

    DATABASE_URL: str = "postgresql://smart_exam:REDACTED_OLD_POSTGRES_PASSWORD@localhost:5432/smart_exam_db"
    USE_POSTGRES: bool = False
    DB_CONNECT_TIMEOUT_SECONDS: int = Field(default=5, ge=1, le=30)

    # Local in-process protection. Deployments with multiple workers should
    # enforce equivalent shared limits at the gateway/Redis layer.
    LOGIN_RATE_LIMIT_ATTEMPTS: int = Field(default=5, ge=1)
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, ge=1)
    AI_RATE_LIMIT_REQUESTS: int = Field(default=30, ge=1)
    AI_RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, ge=1)
    AI_MAX_CONCURRENT: int = Field(default=4, ge=1, le=64)
    AI_MAX_CONCURRENT_PER_USER: int = Field(default=1, ge=1, le=8)
    AI_OPERATION_TIMEOUT_SECONDS: int = Field(default=1200, ge=1, le=3600)
    AI_DAILY_REQUEST_LIMIT: int = Field(default=500, ge=1)
    AI_DAILY_COST_LIMIT_USD: float = Field(default=20, gt=0)
    AI_ACCEPT_NEW_REQUESTS: bool = True
    AI_ALLOWED_PROVIDERS: list[Literal["openai", "gemini", "deepseek"]] = ["openai", "gemini", "deepseek"]
    AI_LEASE_SECONDS: int = Field(default=120, ge=10, le=600)
    MAX_REQUEST_BODY_BYTES: int = Field(default=22 * 1024 * 1024, ge=1024)
    MAX_DOCUMENTS_PER_USER: int = Field(default=100, ge=1)
    MAX_DOCUMENT_BYTES_PER_USER: int = Field(default=512 * 1024 * 1024, ge=1024)
    PUBLIC_REGISTRATION_ENABLED: bool = True
    TRUSTED_HOSTS: list[str] = ['*']

    # Deprecated compatibility field. Runtime order is fixed by
    # ai_provider_chain.PROVIDER_ORDER and cannot be changed from the UI.
    AI_PROVIDER: str = "openai"
    # Blank routing overrides retain the established provider/model policy.
    AI_DEFAULT_PROVIDER: Literal["", "openai", "gemini", "deepseek"] = ""
    AI_MODEL_FAST: str = ""
    AI_MODEL_BALANCED: str = ""
    AI_MODEL_PREMIUM: str = ""
    ENABLE_CREDIT_SYSTEM: bool = True
    # JSON mapping provider:model -> USD per million tokens; unknown = null.
    AI_MODEL_PRICING: dict[str, dict[str, str]] = Field(default_factory=dict)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1"
    OPENAI_VERIFY_MODEL: str = ""
    # Primary-only full exam runs use OpenAI's price/performance model for
    # cost-sensitive, high-volume workloads. Keep reasoning and verbosity low:
    # deterministic scientific gates still reject weak output and retry only
    # the affected questions.
    OPENAI_PRIMARY_ONLY_MODEL: str = "gpt-5.6-luna"
    OPENAI_PRIMARY_ONLY_REASONING_EFFORT: Literal[
        "none", "low", "medium", "high", "xhigh", "max"
    ] = "low"
    OPENAI_PRIMARY_ONLY_VERBOSITY: Literal["low", "medium", "high"] = "low"
    # Accepted only so older .env files still boot. These values are not read
    # by the generation runtime or exposed by the provider API.
    OPENAI_BASE_URL: str = ""
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = ""
    OPENROUTER_VERIFY_MODEL: str = ""
    OPENAI_COMPATIBLE_API_KEY: str = ""
    OPENAI_COMPATIBLE_BASE_URL: str = ""
    OPENAI_COMPATIBLE_MODEL: str = ""
    OPENAI_COMPATIBLE_VERIFY_MODEL: str = ""
    MISTRAL_API_KEY: str = ""
    MISTRAL_MODEL: str = ""
    MISTRAL_VERIFY_MODEL: str = ""
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_VERIFY_MODEL: str = "deepseek-v4-pro"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.7-flash"
    # Có thể đặt model reasoning mạnh hơn cho bước kiểm tra nội dung câu hỏi.
    # Để trống sẽ dùng GEMINI_MODEL.
    GEMINI_VERIFY_MODEL: str = "gemini-3.7-flash"
    # Application-level ceiling: bounds the awaited task so the event loop is
    # never blocked. It cannot cancel an SDK request that already started.
    AI_REQUEST_TIMEOUT_SECONDS: int = 30
    # Full sequential OpenAI -> Gemini -> DeepSeek budget. Each provider keeps
    # the transport timeout above; the chain needs enough time to try all three.
    AI_FAILOVER_TIMEOUT_SECONDS: int = 90
    AI_PRIMARY_ONLY_TIMEOUT_SECONDS: int = Field(default=180, ge=90, le=300)
    # Reasoning reviewers need more time than small generation/fallback calls.
    # They run concurrently, so this is latency headroom rather than a doubled
    # sequential budget.
    AI_DUAL_REVIEW_TIMEOUT_SECONDS: int = Field(default=90, ge=60, le=180)
    # Dual review remains the safe default. Operators may explicitly select a
    # temporary DeepSeek-only mode when Gemini capacity is unavailable.
    AI_INTERACTIVE_REVIEW_MODE: Literal["dual", "deepseek_only"] = "dual"
    # Transport-level timeouts handed to each provider SDK. These *do* abort a
    # started request, which is what actually frees the worker thread.
    AI_CONNECT_TIMEOUT_SECONDS: int = 10
    # How long to wait for the provider's response bytes. Kept just under the
    # application ceiling so the SDK gives up first and reports a real error
    # instead of the task being cancelled out from under it.
    AI_READ_TIMEOUT_SECONDS: int = 25
    # Retries performed inside the SDK. Every retry consumes the same budget,
    # so keep this small.
    AI_MAX_RETRIES: int = 1
    # Primary-only full-exam requests retry OpenAI rate limits instead of
    # advancing to a fallback provider. Two waits (20s, 40s) fit inside the
    # 90-second application failover ceiling.
    AI_PRIMARY_RATE_LIMIT_RETRIES: int = Field(default=2, ge=0, le=3)
    AI_PRIMARY_RETRY_BASE_SECONDS: float = Field(default=20.0, ge=0, le=30)
    AI_PRIMARY_TIMEOUT_RETRY_BASE_SECONDS: float = Field(default=2.0, ge=0, le=10)
    # Keep structured question requests small enough to fit provider transport
    # budgets. Batches are homogeneous by public question type.
    AI_GENERATION_BATCH_SIZE: int = Field(default=2, ge=1, le=8)
    # Quality retries are application retries with explicit semantic failure
    # codes, separate from transport retries inside provider SDKs.
    # Retries are scoped to rejected question IDs, so a second retry costs one
    # small corrective call instead of regenerating an already-valid batch.
    AI_GENERATION_QUALITY_RETRIES: int = Field(default=2, ge=0, le=2)
    # Emit one structured log line per provider call (latency, tokens, outcome).
    AI_LOG_TELEMETRY: bool = True

    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001
    # "http" talks to the Compose chromadb service; anything else uses an
    # embedded persistent client at CHROMA_PERSIST_DIR.
    RAG_CHROMA_MODE: str = "embedded"
    CHROMA_PERSIST_DIR: str = "app/data/chroma"

    # Phase 2: uploads & RAG
    UPLOAD_DIR: str = "app/data/uploads"
    # Bound memory and extraction work before accepting a teacher document.
    MAX_UPLOAD_SIZE_BYTES: int = Field(default=20 * 1024 * 1024, gt=0)
    OCR_PROVIDER: Literal["auto", "none", "gemini", "tesseract"] = "auto"
    OCR_MODEL: str = ""
    OCR_TESSERACT_COMMAND: str = "tesseract"
    OCR_LANGUAGES: str = "vie+eng"
    OCR_PAGE_TIMEOUT_SECONDS: int = Field(default=30, ge=1, le=120)
    OCR_DOCUMENT_TIMEOUT_SECONDS: int = Field(default=120, ge=1, le=600)
    OCR_MAX_PAGES: int = Field(default=12, ge=1, le=100)
    OCR_MAX_OUTPUT_TOKENS: int = Field(default=8192, ge=256, le=32000)
    OCR_NATIVE_MIN_CHARS: int = Field(default=40, ge=0, le=500)
    OCR_NATIVE_MIN_ALNUM_RATIO: float = Field(default=0.4, ge=0, le=1)
    OCR_RENDER_DPI: int = Field(default=180, ge=72, le=300)
    OCR_RENDER_MAX_SIDE: int = Field(default=2400, ge=600, le=4000)
    OCR_MAX_IMAGE_PIXELS: int = Field(default=16000000, ge=1000000, le=32000000)
    DOCUMENT_MAX_PAGES: int = Field(default=300, ge=1, le=1000)
    RAG_TOP_K: int = 5
    RAG_CHUNK_SIZE: int = 600
    # "auto" uses embeddings when a key is configured and BM25 otherwise.
    # "bm25" and "embedding" force one path.
    RAG_RETRIEVER: str = "auto"
    RAG_EMBEDDING_MODEL: str = "gemini-embedding-001"
    # Cache chunk vectors in ChromaDB so re-querying the same documents does
    # not re-embed them. Off by default: BM25 needs no vector store.
    RAG_USE_CHROMA: bool = False

    HYBRID_RETRIEVAL_ENABLED: bool = True
    LEXICAL_RETRIEVAL_ENABLED: bool = True
    VECTOR_RETRIEVAL_ENABLED: bool = True
    RERANKER_ENABLED: bool = True
    RAG_EMBEDDING_BATCH_SIZE: int = Field(default=64, ge=1, le=100)
    RAG_CANDIDATE_LIMIT: int = Field(default=30, ge=1, le=200)
    RAG_RRF_K: int = Field(default=60, ge=1)
    RAG_MEMORY_CACHE_SIZE: int = Field(default=4096, ge=0, le=100000)
    RAG_CONTEXT_TOKEN_BUDGET: int = Field(default=2400, ge=64, le=32000)
    RAG_RERANK_LEXICAL_WEIGHT: float = Field(default=0.65, ge=0, le=1)
    DUPLICATE_DETECTION_ENABLED: bool = True
    DUPLICATE_FUZZY_THRESHOLD: float = Field(default=0.94, ge=0, le=1)
    DUPLICATE_SEMANTIC_THRESHOLD: float = Field(default=0.94, ge=0, le=1)
    DUPLICATE_WARNING_THRESHOLD: float = Field(default=0.86, ge=0, le=1)
    DUPLICATE_CANDIDATE_LIMIT: int = Field(default=30, ge=1, le=200)

    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # OAuth - Google
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # OAuth - Facebook
    FACEBOOK_CLIENT_ID: str = ""
    FACEBOOK_CLIENT_SECRET: str = ""

    # Frontend URL for OAuth redirect
    FRONTEND_URL: str = "http://localhost:8080"

    # Transactional account email. In local/test mode a missing SMTP host logs
    # the action link; deployed environments fail closed instead.
    SMTP_HOST: str = ""
    SMTP_PORT: int = Field(default=587, ge=1, le=65535)
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "no-reply@deka.local"
    SMTP_USE_TLS: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @model_validator(mode="after")
    def duplicate_threshold_order(self):
        if self.DUPLICATE_WARNING_THRESHOLD > self.DUPLICATE_SEMANTIC_THRESHOLD:
            raise ValueError("DUPLICATE_WARNING_THRESHOLD must not exceed DUPLICATE_SEMANTIC_THRESHOLD")
        return self

    @model_validator(mode="after")
    def validate_production_secrets(self):
        local_modes = {"development", "dev", "test", "testing"}
        if self.ENV.strip().lower() not in local_modes and self.SECRET_KEY == INSECURE_DEFAULT_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY mặc định chỉ được phép trong development/test; "
                "mọi môi trường triển khai phải cấu hình secret ngẫu nhiên"
            )
        return self

    @property
    def deployed(self):
        return self.ENV.strip().lower() not in {'dev', 'development', 'test', 'testing'}

    def check_deployment(self):
        """Explicit startup/readiness gate; values and secrets never enter errors."""
        if not self.deployed:
            return
        from urllib.parse import urlsplit
        if len(self.SECRET_KEY) < 32 or self.JWT_ALGORITHM != 'HS256':
            raise ValueError('Configure a strong SECRET_KEY and HS256')
        if len(self.MFA_ENCRYPTION_KEY) < 32 or self.MFA_ENCRYPTION_KEY == self.SECRET_KEY:
            raise ValueError('Configure a separate MFA_ENCRYPTION_KEY of at least 32 characters')
        origin = urlsplit(self.FRONTEND_URL)
        if origin.scheme != 'https' or not origin.hostname or origin.hostname in {'localhost', '127.0.0.1'}:
            raise ValueError('FRONTEND_URL must be the public HTTPS origin')
        if '*' in self.CORS_ORIGINS or any(urlsplit(x).scheme != 'https' for x in self.CORS_ORIGINS):
            raise ValueError('CORS_ORIGINS must contain explicit HTTPS origins')
        if '*' in self.TRUSTED_HOSTS:
            raise ValueError('Configure explicit TRUSTED_HOSTS')
        if self.PUBLIC_REGISTRATION_ENABLED and (not self.SMTP_HOST or self.SMTP_FROM_EMAIL.endswith('.local')):
            raise ValueError('Public registration requires SMTP_HOST and SMTP_FROM_EMAIL')


settings = Settings()
