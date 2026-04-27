import { useState, type JSX } from "react";

interface ArrPosterImageProps {
  src: string;
  alt: string;
  className?: string;
}

/**
 * Lazy poster for icon browse; shows a minimal placeholder on error.
 */
export function ArrPosterImage({
  src,
  alt,
  className,
}: ArrPosterImageProps): JSX.Element {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <div
        className={className ? `arr-poster-fallback ${className}` : "arr-poster-fallback"}
        aria-hidden
      />
    );
  }
  return (
    <img
      src={src}
      alt={alt}
      className={className}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}
