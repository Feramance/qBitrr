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

  useEffect(() => {
    loadIdRef.current += 1;
    setLoaded(false);
    setFailed(false);
  }, [src]);

  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          enqueuePosterReveal(() => setReleased(true));
          observer.disconnect();
        }
      },
      { rootMargin: "200px", threshold: 0.01 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const fallbackCls = ["arr-poster-fallback"];
  if (className) {
    fallbackCls.push(className);
  }

  const onImgLoad = (ev: SyntheticEvent<HTMLImageElement>) => {
    const token = loadIdRef.current;
    const img = ev.currentTarget;
    void finalizePosterDisplay(img).then(() => {
      if (token === loadIdRef.current) {
        setLoaded(true);
      }
    });
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
            onError={() => setFailed(true)}
          />
          {!loaded && (
            <div className={[...fallbackCls, "arr-poster-fallback--overlay"].join(" ")} aria-hidden />
          )}
        </>
      )}
    </div>
  );
}
