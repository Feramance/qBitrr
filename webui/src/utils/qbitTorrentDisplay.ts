export type TorrentStateFamily =
  | "downloading"
  | "uploading"
  | "stalled"
  | "stopped"
  | "error"
  | "checking"
  | "unknown";

export function torrentStateFamily(state: string): TorrentStateFamily {
  switch (state) {
    case "downloading":
    case "forcedDL":
    case "metaDL":
    case "forcedMetaDL":
    case "queuedDL":
      return "downloading";
    case "uploading":
    case "forcedUP":
    case "queuedUP":
      return "uploading";
    case "stalledDL":
    case "stalledUP":
    case "allocating":
      return "stalled";
    case "pausedDL":
    case "pausedUP":
    case "stoppedDL":
    case "stoppedUP":
      return "stopped";
    case "error":
    case "missingFiles":
      return "error";
    case "checkingDL":
    case "checkingUP":
    case "checkingResumeData":
    case "moving":
      return "checking";
    default:
      return "unknown";
  }
}

export function formatTorrentStateLabel(state: string): string {
  const labels: Record<string, string> = {
    downloading: "Downloading",
    forcedDL: "Forced DL",
    metaDL: "Metadata",
    forcedMetaDL: "Forced metadata",
    stalledDL: "Stalled DL",
    queuedDL: "Queued DL",
    pausedDL: "Paused DL",
    stoppedDL: "Stopped DL",
    uploading: "Seeding",
    forcedUP: "Forced UP",
    stalledUP: "Stalled UP",
    queuedUP: "Queued UP",
    pausedUP: "Paused UP",
    stoppedUP: "Stopped UP",
    checkingDL: "Checking",
    checkingUP: "Checking",
    checkingResumeData: "Checking resume",
    moving: "Moving",
    allocating: "Allocating",
    missingFiles: "Missing files",
    error: "Error",
    unknown: "Unknown",
  };
  return labels[state] ?? state;
}
