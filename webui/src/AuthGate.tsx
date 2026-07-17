import React, { useCallback, useEffect, useState, type JSX } from "react";
import { getMeta, logout, fetchWebToken } from "./api/client";
import type { MetaResponse } from "./api/types";
import { LoginPage } from "./pages/LoginPage";

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2rem', textAlign: 'center' }}>
          <h2>Something went wrong</h2>
          <p style={{ color: '#888' }}>{this.state.error?.message}</p>
          <button
            onClick={() => window.location.reload()}
            style={{ marginTop: '1rem', padding: '0.5rem 1rem', cursor: 'pointer' }}
          >
            Reload Page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

type AuthState = "loading" | "authenticated" | "unauthenticated" | "error";

interface AuthInfo {
  authRequired: boolean;
  localAuthEnabled: boolean;
  oidcEnabled: boolean;
  setupRequired: boolean;
}

function readStoredToken(): string | null {
  return (
    localStorage.getItem("token") ||
    localStorage.getItem("webui-token") ||
    localStorage.getItem("webui_token") ||
    null
  );
}

function authInfoFromMeta(meta: MetaResponse): AuthInfo {
  return {
    authRequired: Boolean(meta.auth_required),
    localAuthEnabled: Boolean(meta.local_auth_enabled),
    oidcEnabled: Boolean(meta.oidc_enabled),
    setupRequired: Boolean(meta.setup_required),
  };
}

function AuthGate({
  children,
}: {
  children: (
    authRequired: boolean,
    onSignOut: () => void,
    initialMeta: MetaResponse | null
  ) => React.ReactNode;
}): JSX.Element {
  const [authState, setAuthState] = useState<AuthState>("loading");
  const [authInfo, setAuthInfo] = useState<AuthInfo>({
    authRequired: false,
    localAuthEnabled: false,
    oidcEnabled: false,
    setupRequired: false,
  });
  const [authBootstrapError, setAuthBootstrapError] = useState<string | null>(null);
  const [initialMeta, setInitialMeta] = useState<MetaResponse | null>(null);

  const checkAuth = useCallback(async () => {
    setAuthBootstrapError(null);
    setAuthState("loading");
    setInitialMeta(null);

    const existingToken = readStoredToken();

    try {
      if (existingToken) {
        // Token present: parallelize meta + session token refresh to shorten boot waterfall.
        const [metaResult, tokenResult] = await Promise.allSettled([
          getMeta(),
          fetchWebToken(),
        ]);

        if (metaResult.status === "rejected") {
          const error = metaResult.reason;
          const detail =
            error instanceof Error && error.message.trim().length > 0
              ? error.message
              : "Unable to reach qBitrr backend";
          setAuthBootstrapError(detail);
          setAuthState("error");
          return;
        }

        const meta = metaResult.value;
        setInitialMeta(meta);
        const info = authInfoFromMeta(meta);
        setAuthInfo(info);

        if (!info.authRequired) {
          setAuthState("authenticated");
          return;
        }

        const token =
          tokenResult.status === "fulfilled" ? tokenResult.value : null;
        if (token) {
          localStorage.setItem("token", token);
          setAuthState("authenticated");
        } else {
          setAuthState("unauthenticated");
        }
        return;
      }

      const meta = await getMeta();
      setInitialMeta(meta);
      const info = authInfoFromMeta(meta);
      setAuthInfo(info);

      if (!info.authRequired) {
        setAuthState("authenticated");
        return;
      }

      // Auth required but no stored token — try session cookie via /web/token.
      try {
        const token = await fetchWebToken();
        if (token) {
          localStorage.setItem("token", token);
          setAuthState("authenticated");
        } else {
          setAuthState("unauthenticated");
        }
      } catch {
        setAuthState("unauthenticated");
      }
    } catch (error) {
      const detail =
        error instanceof Error && error.message.trim().length > 0
          ? error.message
          : "Unable to reach qBitrr backend";
      setAuthBootstrapError(detail);
      setAuthState("error");
    }
  }, []);

  useEffect(() => {
    // Defer so the effect body does not synchronously trigger setState (react-hooks/set-state-in-effect).
    const id = window.setTimeout(() => {
      void checkAuth();
    }, 0);
    return () => window.clearTimeout(id);
  }, [checkAuth]);

  const handleSignOut = useCallback(async () => {
    await logout();
    setInitialMeta(null);
    setAuthState("unauthenticated");
  }, []);

  const handleLoginSuccess = useCallback(async () => {
    const token = await fetchWebToken().catch(() => null);
    if (token) {
      localStorage.setItem("token", token);
    }
    setAuthState("authenticated");
  }, []);

  if (authState === "loading") {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh" }}>
        <span className="spinner" aria-hidden="true" />
      </div>
    );
  }

  if (authState === "unauthenticated") {
    return (
      <LoginPage
        onSuccess={() => void handleLoginSuccess()}
        localAuthEnabled={authInfo.localAuthEnabled}
        oidcEnabled={authInfo.oidcEnabled}
        setupRequired={authInfo.setupRequired}
      />
    );
  }

  if (authState === "error") {
    return (
      <div className="login-page">
        <div className="login-card">
          <h1 className="login-title">qBitrr</h1>
          <p className="login-subtitle">Unable to reach backend</p>
          <p className="login-error">{authBootstrapError ?? "Failed to load authentication state."}</p>
          <button className="btn primary login-submit" type="button" onClick={() => void checkAuth()}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  return <>{children(authInfo.authRequired, handleSignOut, initialMeta)}</>;
}


export { AuthGate, ErrorBoundary };
