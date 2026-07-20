import {
  useEffect,
  useRef,
  useState,
  type JSX,
  type SyntheticEvent,
} from "react";
import { enqueuePosterReveal } from "../../utils/posterLoadQueue";
import {
  POSTER_MAX_RETRIES,
  posterRetryBackoffMs,
  withPosterRetryParam,
} from "../../utils/posterRetry";
import { observePosterVisibility } from "../../utils/sharedIntersectionObserver";

interface ArrPosterImageProps {
  src: string;
  alt: string;
  className?: string;
}

async function finalizePosterDisplay(img: HTMLImageElement): Promise<void> {
  try {
    await img.decode();
  } catch {
    // Still show the bitmap if decode rejects (unsupported or huge image).
  }
}

/**
 * Poster for icon browse: shared intersection gate + bounded global queue limits
 * parallel thumbnail loads; shows fallback until the image is ready to paint.
 *
 * Failed loads retry up to {@link POSTER_MAX_RETRIES} times (backoff + cache-bust) via the
 * poster queue. The queue slot is released when the network load settles (``onLoad`` /
 * ``onError``), before awaiting ``decode()``, so decode work does not starve the queue.
 */
export function ArrPosterImage({
  src,
  alt,
  className,
}: ArrPosterImageProps): JSX.Element {
  const [failed, setFailed] = useState(false);
  const [released, setReleased] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const loadIdRef = useRef(0);
  const attemptRef = useRef(0);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelledRef = useRef(false);
  // Held while the slot is checked out; called when the image network settles (load/error/
  // unmount) so we never pin the queue past the lifetime of this poster.
  const releaseSlotRef = useRef<(() => void) | null>(null);

  const clearRetryTimer = () => {
    if (retryTimerRef.current !== null) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
  };

  const releaseSlot = () => {
    if (releaseSlotRef.current) {
      releaseSlotRef.current();
      releaseSlotRef.current = null;
    }
  };

  const enqueueLoad = () => {
    return enqueuePosterReveal((release) => {
      releaseSlotRef.current = release;
      setReleased(true);
    });
  };

  useEffect(() => {
    cancelledRef.current = false;
    loadIdRef.current += 1;
    attemptRef.current = 0;
    clearRetryTimer();
    // Reset load state when the poster URL changes (new row / retry base src).
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional reset on src identity change
    setLoaded(false);
    setFailed(false);
    setReleased(false);
    setAttempt(0);
    if (releaseSlotRef.current) {
      releaseSlotRef.current();
      releaseSlotRef.current = null;
    }
    return () => {
      cancelledRef.current = true;
      clearRetryTimer();
    };
  }, [src]);

  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    let cancelEnqueue: (() => void) | null = null;
    const unobserve = observePosterVisibility(el, () => {
      cancelEnqueue = enqueueLoad();
    });
    return () => {
      unobserve();
      if (cancelEnqueue) cancelEnqueue();
    };
    // Only re-bind visibility when the base src changes; retries re-enqueue directly.
  }, [src]);

  useEffect(() => {
    return () => {
      cancelledRef.current = true;
      clearRetryTimer();
      if (releaseSlotRef.current) {
        releaseSlotRef.current();
        releaseSlotRef.current = null;
      }
    };
  }, []);

  const fallbackCls = ["arr-poster-fallback"];
  if (className) {
    fallbackCls.push(className);
  }

  const scheduleRetry = () => {
    const current = attemptRef.current;
    if (current >= POSTER_MAX_RETRIES) {
      setFailed(true);
      releaseSlot();
      return;
    }
    releaseSlot();
    setReleased(false);
    setLoaded(false);
    const delay = posterRetryBackoffMs(current);
    clearRetryTimer();
    retryTimerRef.current = setTimeout(() => {
      retryTimerRef.current = null;
      if (cancelledRef.current) return;
      const next = current + 1;
      attemptRef.current = next;
      setAttempt(next);
      enqueueLoad();
    }, delay);
  };

  const onImgLoad = (ev: SyntheticEvent<HTMLImageElement>) => {
    const token = loadIdRef.current;
    const img = ev.currentTarget;
    releaseSlot();
    void finalizePosterDisplay(img).then(() => {
      if (token === loadIdRef.current) {
        setLoaded(true);
      }
    });
  };

  const onImgError = () => {
    if (attemptRef.current >= POSTER_MAX_RETRIES) {
      setFailed(true);
      releaseSlot();
      return;
    }
    scheduleRetry();
  };

  const displaySrc = withPosterRetryParam(src, attempt);

  if (failed) {
    return (
      <div
        className={className ? `arr-poster-fallback ${className}` : "arr-poster-fallback"}
        aria-hidden
      />
    );
  }

  return (
    <div
      ref={rootRef}
      className={loaded ? "arr-poster-image-wrap arr-poster-image-wrap--ready" : "arr-poster-image-wrap"}
    >
      {!released ? (
        <div className={fallbackCls.join(" ")} aria-hidden />
      ) : (
        <>
          <img
            key={`${src}-${attempt}`}
            src={displaySrc}
            alt={alt}
            className={[className, "arr-poster-layer"].filter(Boolean).join(" ")}
            decoding="async"
            onLoad={onImgLoad}
            onError={onImgError}
          />
          {!loaded && (
            <div className={[...fallbackCls, "arr-poster-fallback--overlay"].join(" ")} aria-hidden />
          )}
        </>
      )}
    </div>
  );
}
