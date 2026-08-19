/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
  type JSX,
} from "react";

export type ToastKind = "info" | "success" | "warning" | "error";

export interface Toast {
  id: number;
  message: string;
  kind: ToastKind;
}

interface ToastContextValue {
  toasts: Toast[];
  push: (message: string, kind?: ToastKind) => void;
  dismiss: (id: number) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

/** Skip identical message+kind pushes within this window (and while still visible). */
export const TOAST_DEDUPE_MS = 4000;

let toastCounter = 0;
let lastPushKey: string | null = null;
let lastPushAt = 0;

function toastDedupeKey(message: string, kind: ToastKind): string {
  return `${kind}\0${message}`;
}

/** Reset module-level dedupe state (tests only). */
export function resetToastDedupeForTests(): void {
  lastPushKey = null;
  lastPushAt = 0;
  toastCounter = 0;
}

export function ToastProvider({ children }: PropsWithChildren): JSX.Element {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastsRef = useRef(toasts);

  useEffect(() => {
    toastsRef.current = toasts;
  }, [toasts]);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (message: string, kind: ToastKind = "info") => {
      const key = toastDedupeKey(message, kind);
      const now = Date.now();
      if (lastPushKey === key && now - lastPushAt < TOAST_DEDUPE_MS) {
        return;
      }
      if (toastsRef.current.some((t) => t.message === message && t.kind === kind)) {
        return;
      }
      const id = ++toastCounter;
      lastPushKey = key;
      lastPushAt = now;
      setToasts((prev) => [...prev, { id, message, kind }]);
      const duration = kind === "error" ? 8000 : 3500;
      window.setTimeout(() => dismiss(id), duration);
    },
    [dismiss]
  );

  const value = useMemo(
    () => ({
      toasts,
      push,
      dismiss,
    }),
    [toasts, push, dismiss]
  );

  return (
    <ToastContext.Provider value={value}>{children}</ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}

export function ToastViewport(): JSX.Element | null {
  const { toasts, dismiss } = useToast();
  if (!toasts.length) return null;
  return (
    <div className="toasts">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`toast ${toast.kind !== "info" ? toast.kind : ""}`}
          role="alert"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === 'Escape') dismiss(toast.id); }}
          onClick={() => dismiss(toast.id)}
        >
          {toast.message}
        </div>
      ))}
    </div>
  );
}
