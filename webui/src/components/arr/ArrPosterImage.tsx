import {
  useEffect,
  useRef,
  useState,
  type JSX,
  type SyntheticEvent,
} from "react";
import { enqueuePosterReveal } from "../../utils/posterLoadQueue";

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
 * Poster for icon browse: intersection-gated reveal + bounded global queue limits
 * parallel thumbnail loads; shows fallback until decoded image displays (no half-painted frame).
 *
 * The poster queue slot is held until the underlying `<img>` actually finishes (load, error,
 * or component unmount) — see H-5 in the WebUI plan. The previous implementation released
 * the slot immediately after the React state update, which throttled `setState` calls
 * rather than network requests.
 */
export function ArrPosterImage({
  src,
  alt,
  className,
}: ArrPosterImageProps): JSX.Element {
  const [failed, setFailed] = useState(false);
  const [released, setReleased] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const loadIdRef = useRef(0);
  // Held while the slot is checked out; called when the image truly finishes (load/error/
  // unmount) so we never pin the queue past the lifetime of this poster.
  const releaseSlotRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    loadIdRef.current += 1;
    const id = window.setTimeout(() => {
      setLoaded(false);
      setFailed(false);
      setReleased(false);
    }, 0);
    // A new src means the previous slot (if any) is no longer the one rendering — drop it.
    if (releaseSlotRef.current) {
      releaseSlotRef.current();
      releaseSlotRef.current = null;
    }
    return () => window.clearTimeout(id);
  }, [src]);

  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    let cancelEnqueue: (() => void) | null = null;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          cancelEnqueue = enqueuePosterReveal((release) => {
            // Slot is now ours; render the <img>.  Release runs from onLoad/onError below
            // (or the watchdog inside the queue).
            releaseSlotRef.current = release;
            setReleased(true);
          });
          observer.disconnect();
        }
      },
      { rootMargin: "200px", threshold: 0.01 },
    );
    observer.observe(el);
    return () => {
      observer.disconnect();
      // If we were waiting for a slot, drop the wait.
      if (cancelEnqueue) cancelEnqueue();
    };
  }, [src]);

  // On unmount, release the slot if we still hold it (no point waiting for a network load
  // that nobody will see).
  useEffect(() => {
    return () => {
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

  const releaseSlot = () => {
    if (releaseSlotRef.current) {
      releaseSlotRef.current();
      releaseSlotRef.current = null;
    }
  };

  const onImgLoad = (ev: SyntheticEvent<HTMLImageElement>) => {
    const token = loadIdRef.current;
    const img = ev.currentTarget;
    void finalizePosterDisplay(img).then(() => {
      if (token === loadIdRef.current) {
        setLoaded(true);
      }
      releaseSlot();
    });
  };

  const onImgError = () => {
    setFailed(true);
    releaseSlot();
  };

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
            src={src}
            alt={alt}
            className={[className, "arr-poster-layer"].filter(Boolean).join(" ")}
            loading="lazy"
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
