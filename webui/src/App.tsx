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
          <AuthGate>
            {(authRequired, onSignOut, initialMeta) => (
              <WebUIProvider>
                <AppShell
                  authRequired={authRequired}
                  onSignOut={onSignOut}
                  initialMeta={initialMeta}
                />
              </WebUIProvider>
            )}
          </AuthGate>
          <ToastViewport />
        </SearchProvider>
      </ToastProvider>
    </ErrorBoundary>
  );
}
