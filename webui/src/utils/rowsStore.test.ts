import { describe, expect, it } from "vitest";
import type { Hashable } from "./dataSync";
import {
  createEmptyRowsSnapshot,
  syncRowsSnapshot,
  type RowsStoreOptions,
} from "./rowsStore";

interface Row extends Hashable {
  id: string;
  title: string;
  score: number;
}

const opts: RowsStoreOptions<Row> = {
  getKey: (row) => row.id,
  hashFields: ["title", "score"],
};

describe("syncRowsSnapshot", () => {
  it("returns noop and same snapshot reference when nothing changed", () => {
    const prev = createEmptyRowsSnapshot<Row>();
    const first = syncRowsSnapshot(prev, [{ id: "1", title: "A", score: 1 }], opts);
    const second = syncRowsSnapshot(
      first.snapshot,
      [{ id: "1", title: "A", score: 1 }],
      opts,
    );
    expect(second.changeKind).toBe("noop");
    expect(second.snapshot).toBe(first.snapshot);
  });

  it("marks update-only when row content changes without add/remove", () => {
    const seeded = syncRowsSnapshot(
      createEmptyRowsSnapshot<Row>(),
      [{ id: "1", title: "A", score: 1 }],
      opts,
    );
    const updated = syncRowsSnapshot(
      seeded.snapshot,
      [{ id: "1", title: "A", score: 2 }],
      opts,
    );
    expect(updated.changeKind).toBe("update-only");
    expect(updated.snapshot.rowOrder).toBe(seeded.snapshot.rowOrder);
    expect(updated.updated).toHaveLength(1);
  });

  it("marks add-remove when membership changes", () => {
    const seeded = syncRowsSnapshot(
      createEmptyRowsSnapshot<Row>(),
      [{ id: "1", title: "A", score: 1 }],
      opts,
    );
    const next = syncRowsSnapshot(
      seeded.snapshot,
      [
        { id: "1", title: "A", score: 1 },
        { id: "2", title: "B", score: 3 },
      ],
      opts,
    );
    expect(next.changeKind).toBe("add-remove");
    expect(next.added).toHaveLength(1);
    expect(next.snapshot.rowOrder).not.toBe(seeded.snapshot.rowOrder);
  });
});
