import React, { useState } from "react";
import { login, setPassword, AuthError } from "../api/client";

interface LoginPageProps {
  onSuccess: () => void;
  localAuthEnabled: boolean;
  oidcEnabled: boolean;
  setupRequired?: boolean;
}

type View = "login" | "setup";

export function LoginPage({ onSuccess, localAuthEnabled, oidcEnabled, setupRequired = false }: LoginPageProps) {
  const [view, setView] = useState<View>(setupRequired ? "setup" : "login");

  // Login form state
  const [username, setUsername] = useState("");
  const [password, setPassword_] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Setup form state
  const [setupUsername, setSetupUsername] = useState("");
  const [setupPassword, setSetupPassword] = useState("");
  const [setupConfirm, setSetupConfirm] = useState("");
  const [setupError, setSetupError] = useState<string | null>(null);
  const [setupSubmitting, setSetupSubmitting] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login({ username, password });
      onSuccess();
    } catch (err) {
      if (err instanceof AuthError && err.code === "SETUP_REQUIRED") {
        setSetupUsername(username);
        setView("setup");
        setError(null);
      } else {
        setError(err instanceof Error ? err.message : "Login failed.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleSetup = async (e: React.FormEvent) => {
    e.preventDefault();
    setSetupError(null);
    if (!setupUsername.trim()) {
      setSetupError("Username is required.");
      return;
    }
    if (setupPassword.length < 8) {
      setSetupError("Password must be at least 8 characters.");
      return;
    }
    if (setupPassword !== setupConfirm) {
      setSetupError("Passwords do not match.");
      return;
    }
    setSetupSubmitting(true);
    try {
      await setPassword({ username: setupUsername.trim(), password: setupPassword });
      // After setting password, log in automatically
      await login({ username: setupUsername.trim(), password: setupPassword });
      onSuccess();
    } catch (err) {
      setSetupError(err instanceof Error ? err.message : "Failed to set password.");
    } finally {
      setSetupSubmitting(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h1 className="login-title">qBitrr</h1>
        {view === "login" ? (
          <>
            <p className="login-subtitle">Sign in to continue</p>
            {localAuthEnabled && (
              <form onSubmit={handleLogin} className="login-form">
                <div className="login-field">
                  <label htmlFor="login-username">Username</label>
                  <input
                    id="login-username"
                    type="text"
                    autoComplete="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                    disabled={submitting}
                  />
                </div>
                <div className="login-field">
                  <label htmlFor="login-password">Password</label>
                  <input
                    id="login-password"
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword_(e.target.value)}
                    required
                    disabled={submitting}
                  />
                </div>
                {error && <div className="login-error">{error}</div>}
                <button className="btn primary login-submit" type="submit" disabled={submitting}>
                  {submitting ? "Signing in…" : "Sign In"}
                </button>
              </form>
            )}
            {oidcEnabled && (
              <div className="oidc-section">
                {localAuthEnabled && <div className="login-divider">or</div>}
                <a
                  href="/web/auth/oidc/challenge"
                  className="btn ghost login-oidc-btn"
                >
                  Sign in with SSO
                </a>
              </div>
            )}
            {!localAuthEnabled && !oidcEnabled && (
              <p className="login-error">
                No login method is configured. Enable Local Auth or OIDC in Web Settings.
              </p>
            )}
          </>
        ) : (
          <>
            <p className="login-subtitle">
              {setupRequired
                ? "Create your username and password to secure qBitrr"
                : "Set up your password to continue"}
            </p>
            <form onSubmit={handleSetup} className="login-form">
              <div className="login-field">
                <label htmlFor="setup-username">Username</label>
                <input
                  id="setup-username"
                  type="text"
                  autoComplete="username"
                  value={setupUsername}
                  onChange={(e) => setSetupUsername(e.target.value)}
                  required
                  disabled={setupSubmitting}
                />
              </div>
              <div className="login-field">
                <label htmlFor="setup-password">New Password</label>
                <input
                  id="setup-password"
                  type="password"
                  autoComplete="new-password"
                  value={setupPassword}
                  onChange={(e) => setSetupPassword(e.target.value)}
                  minLength={8}
                  required
                  disabled={setupSubmitting}
                />
                <span className="field-description">Minimum 8 characters.</span>
              </div>
              <div className="login-field">
                <label htmlFor="setup-confirm">Confirm Password</label>
                <input
                  id="setup-confirm"
                  type="password"
                  autoComplete="new-password"
                  value={setupConfirm}
                  onChange={(e) => setSetupConfirm(e.target.value)}
                  required
                  disabled={setupSubmitting}
                />
              </div>
              {setupError && <div className="login-error">{setupError}</div>}
              <button className="btn primary login-submit" type="submit" disabled={setupSubmitting}>
                {setupSubmitting ? "Setting up…" : "Set Password & Sign In"}
              </button>
              {!setupRequired && (
                <button
                  className="btn ghost"
                  type="button"
                  onClick={() => setView("login")}
                  disabled={setupSubmitting}
                  style={{ marginTop: "0.5rem" }}
                >
                  Back to Sign In
                </button>
              )}
            </form>
          </>
        )}
      </div>
    </div>
  );
}
