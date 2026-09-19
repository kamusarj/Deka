import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="panel error-boundary">
          <span className="empty-state-icon" aria-hidden="true" style={{ margin: "0 auto 0.5rem" }}>
            ⚠️
          </span>
          <h2>Đã xảy ra lỗi</h2>
          <p className="error" style={{ marginTop: "0.4rem" }}>
            {this.state.error?.message || "Có lỗi không xác định xảy ra."}
          </p>
          <button
            type="button"
            style={{ marginTop: "1rem" }}
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.reload();
            }}
          >
            Thử lại
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
