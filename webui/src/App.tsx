import React, { type JSX } from "react";
import { ToastProvider, ToastViewport } from "./context/ToastContext";
import { SearchProvider } from "./context/SearchContext";
import { WebUIProvider } from "./context/WebUIContext";
import { AuthGate, ErrorBoundary } from "./AuthGate";
import { AppShell } from "./AppShell";

export default function App(): JSX.Element {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <SearchProvider>
          <WebUIProvider>
            <AuthGate>
              {(authRequired, onSignOut) => (
                <AppShell authRequired={authRequired} onSignOut={onSignOut} />
              )}
            </AuthGate>
            <ToastViewport />
          </WebUIProvider>
        </SearchProvider>
      </ToastProvider>
    </ErrorBoundary>
  );
}
