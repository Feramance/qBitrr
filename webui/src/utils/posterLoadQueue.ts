/**
 * Bounds how many posters are actively fetching at once when scrolled into view.
 *
 * The previous implementation released the slot in a microtask immediately after the
 * subscriber's setState ran, which means the queue throttled `setState` rather than the
 * actual `<img>` request. The fix (H-5): the subscriber receives a `release` callback and is
 * expected to invoke it when the network request truly finishes — wired up in
 * `ArrPosterImage` from the image's `onLoad`/`onError`/abort, plus a watchdog timeout so a
 * stuck request cannot starve the queue forever.
 */

const POSTER_QUEUE_MAX_CONCURRENT = 4;
// Watchdog: if the subscriber never reports completion within this window we forcibly free
// the slot. Picked a generous default so slow Arr instances are still allowed to finish.
const POSTER_QUEUE_WATCHDOG_MS = 10_000;

type Subscriber = (release: () => void) => void;

let posterQueueActive = 0;
const posterQueueWaiting: Subscriber[] = [];

function pumpPosterQueue(): void {
  while (posterQueueActive < POSTER_QUEUE_MAX_CONCURRENT && posterQueueWaiting.length > 0) {
    posterQueueActive += 1;
    const subscriber = posterQueueWaiting.shift();
    if (!subscriber) {
      // Defensive: shift() returned undefined despite the length check above.
      posterQueueActive -= 1;
      continue;
    }
    let released = false;
    let watchdog: ReturnType<typeof setTimeout> | null = null;
    const release = () => {
      if (released) return;
      released = true;
      if (watchdog !== null) {
        clearTimeout(watchdog);
        watchdog = null;
      }
      posterQueueActive -= 1;
      pumpPosterQueue();
    };
    watchdog = setTimeout(release, POSTER_QUEUE_WATCHDOG_MS);
    queueMicrotask(() => {
      try {
        subscriber(release);
      } catch (err) {
        // Synchronous throw must still free the slot, otherwise the queue stalls.
        if (!released) release();
        throw err;
      }
    });
  }
}

/**
 * Enqueue a subscriber that wants to start loading a poster image.
 *
 * The callback is invoked with a `release` function. The subscriber MUST call it when the
 * underlying image load finishes (success or failure) so the slot is freed for the next
 * waiter. A watchdog will release the slot automatically after a long enough delay if the
 * subscriber misbehaves.
 *
 * Returns a function the caller can invoke if it cancels before its slot opens.
 */
export function enqueuePosterReveal(subscriber: Subscriber): () => void {
  posterQueueWaiting.push(subscriber);
  pumpPosterQueue();
  return () => {
    const idx = posterQueueWaiting.indexOf(subscriber);
    if (idx >= 0) {
      posterQueueWaiting.splice(idx, 1);
    }
  };
}
