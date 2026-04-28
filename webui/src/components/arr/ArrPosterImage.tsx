import { useEffect, useRef, useState, type JSX } from "react";
import { enqueuePosterReveal } from "../../utils/posterLoadQueue";

interface ArrPosterImageProps {
  src: string;
  alt: string;
  className?: string;
}

/**
 * Poster for icon browse: intersection-gated reveal + bounded global queue limits
 * parallel thumbnail loads; shows a fallback on error or before reveal.
 */
export function ArrPosterImage({
  src,
  alt,
  className,
}: ArrPosterImageProps): JSX.Element {
  const [failed, setFailed] = useState(false);
  const [released, setReleased] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

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

  if (failed) {
    return (
      <div
        className={className ? `arr-poster-fallback ${className}` : "arr-poster-fallback"}
        aria-hidden
      />
    );
  }

  return (
    <div ref={rootRef} className="arr-poster-image-wrap">
      {!released ? (
        <div
          className={className ? `arr-poster-fallback ${className}` : "arr-poster-fallback"}
          aria-hidden
        />
      ) : (
        <img
          src={src}
          alt={alt}
          className={className}
          loading="lazy"
          onError={() => setFailed(true)}
        />
      )}
    </div>
  );
}
