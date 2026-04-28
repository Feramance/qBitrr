/**
 * Bounds how many posters start loading at once when entering the viewport,
 * avoiding a burst of parallel thumbnail requests against the Arr API.
 */

const POSTER_QUEUE_MAX_CONCURRENT = 4;

let posterQueueActive = 0;
const posterQueueWaiting: Array<() => void> = [];

function pumpPosterQueue(): void {
  while (posterQueueActive < POSTER_QUEUE_MAX_CONCURRENT && posterQueueWaiting.length > 0) {
    posterQueueActive += 1;
    const fn = posterQueueWaiting.shift();
    queueMicrotask(() => {
      try {
        fn?.();
      } finally {
        posterQueueActive -= 1;
        pumpPosterQueue();
      }
    });
  }
}

export function enqueuePosterReveal(callback: () => void): void {
  posterQueueWaiting.push(callback);
  pumpPosterQueue();
}
