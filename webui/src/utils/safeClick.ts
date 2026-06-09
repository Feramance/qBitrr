import { useCallback, useRef, type MouseEvent, type PointerEvent } from "react";

const MOVE_THRESHOLD_PX = 5;

let trackingInstalled = false;
let pointerDownTarget: EventTarget | null = null;
let pointerDownPoint: { x: number; y: number } | null = null;
let pointerDragged = false;

function hasActiveTextSelection(): boolean {
  const selection = window.getSelection()?.toString().trim();
  return Boolean(selection);
}

function movedBeyondThreshold(
  startX: number,
  startY: number,
  endX: number,
  endY: number
): boolean {
  return (
    Math.abs(endX - startX) > MOVE_THRESHOLD_PX ||
    Math.abs(endY - startY) > MOVE_THRESHOLD_PX
  );
}

function resetPointerSession(): void {
  pointerDownTarget = null;
  pointerDownPoint = null;
  pointerDragged = false;
}

/** Install document-level pointer tracking for safe click detection. Idempotent. */
export function installSafeClickTracking(): void {
  if (trackingInstalled || typeof document === "undefined") {
    return;
  }
  trackingInstalled = true;

  document.addEventListener(
    "pointerdown",
    (event) => {
      pointerDownTarget = event.target;
      pointerDownPoint = { x: event.clientX, y: event.clientY };
      pointerDragged = false;
    },
    true
  );

  document.addEventListener(
    "pointermove",
    (event) => {
      if (!pointerDownPoint) {
        return;
      }
      if (
        movedBeyondThreshold(
          pointerDownPoint.x,
          pointerDownPoint.y,
          event.clientX,
          event.clientY
        )
      ) {
        pointerDragged = true;
      }
    },
    true
  );

  document.addEventListener(
    "click",
    () => {
      resetPointerSession();
    },
    true
  );
}

/** Ignore clicks that follow text selection or pointer drag. */
export function shouldIgnoreClick(event: MouseEvent | PointerEvent): boolean {
  if (hasActiveTextSelection()) {
    return true;
  }
  if (pointerDragged) {
    return true;
  }
  if (pointerDownPoint) {
    if (
      movedBeyondThreshold(
        pointerDownPoint.x,
        pointerDownPoint.y,
        event.clientX,
        event.clientY
      )
    ) {
      return true;
    }
  }
  if (
    pointerDownTarget instanceof Node &&
    event.currentTarget instanceof Node &&
    pointerDownTarget !== event.currentTarget &&
    !event.currentTarget.contains(pointerDownTarget)
  ) {
    return true;
  }
  return false;
}

/** Wrap a click handler so selection/drag-induced clicks are ignored. */
export function createSafeClickHandler(
  handler: (event: MouseEvent<HTMLElement>) => void
): (event: MouseEvent<HTMLElement>) => void {
  installSafeClickTracking();
  return (event) => {
    if (shouldIgnoreClick(event)) {
      return;
    }
    handler(event);
  };
}

/** Wrap a zero-arg click handler (modal close, tab switch, etc.). */
export function safeClick(handler: () => void): (event: MouseEvent<HTMLElement>) => void {
  return createSafeClickHandler(() => {
    handler();
  });
}

/** Backdrop dismiss that only fires when pointer down+up both hit the backdrop. */
export function useSafeBackdropClose(onClose: () => void): {
  onPointerDown: (event: PointerEvent<HTMLDivElement>) => void;
  onPointerUp: (event: PointerEvent<HTMLDivElement>) => void;
} {
  installSafeClickTracking();
  const pointerDownOnBackdrop = useRef(false);
  const startPoint = useRef<{ x: number; y: number } | null>(null);

  const onPointerDown = useCallback((event: PointerEvent<HTMLDivElement>) => {
    pointerDownOnBackdrop.current = event.target === event.currentTarget;
    startPoint.current = pointerDownOnBackdrop.current
      ? { x: event.clientX, y: event.clientY }
      : null;
  }, []);

  const onPointerUp = useCallback(
    (event: PointerEvent<HTMLDivElement>) => {
      const onBackdrop =
        pointerDownOnBackdrop.current && event.target === event.currentTarget;
      pointerDownOnBackdrop.current = false;
      if (!onBackdrop) {
        startPoint.current = null;
        return;
      }
      if (shouldIgnoreClick(event)) {
        startPoint.current = null;
        return;
      }
      if (startPoint.current) {
        if (
          movedBeyondThreshold(
            startPoint.current.x,
            startPoint.current.y,
            event.clientX,
            event.clientY
          )
        ) {
          startPoint.current = null;
          return;
        }
      }
      startPoint.current = null;
      onClose();
    },
    [onClose]
  );

  return { onPointerDown, onPointerUp };
}

installSafeClickTracking();
