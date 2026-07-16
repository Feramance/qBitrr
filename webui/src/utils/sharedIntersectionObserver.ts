/**
 * Single shared IntersectionObserver for Arr poster tiles.
 *
 * Avoids creating one observer per tile on dense Icon grids.
 */

type VisibleCallback = () => void;

const callbacks = new WeakMap<Element, VisibleCallback>();

let sharedObserver: IntersectionObserver | null = null;

function getObserver(): IntersectionObserver {
  if (!sharedObserver) {
    sharedObserver = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const cb = callbacks.get(entry.target);
          if (!cb) continue;
          // One-shot: unobserve before invoking so a remount can re-register cleanly.
          sharedObserver?.unobserve(entry.target);
          callbacks.delete(entry.target);
          cb();
        }
      },
      { rootMargin: "200px", threshold: 0.01 },
    );
  }
  return sharedObserver;
}

/**
 * Observe ``el`` until it intersects the viewport (with a 200px margin), then invoke
 * ``onVisible`` once. Returns an unobserve function for cleanup.
 */
export function observePosterVisibility(
  el: Element,
  onVisible: VisibleCallback,
): () => void {
  callbacks.set(el, onVisible);
  getObserver().observe(el);
  return () => {
    callbacks.delete(el);
    sharedObserver?.unobserve(el);
  };
}
