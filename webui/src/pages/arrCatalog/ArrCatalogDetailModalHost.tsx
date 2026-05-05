import { memo, type JSX } from "react";
import { ArrModal } from "../../components/arr/ArrModal";
import { useRowSnapshot } from "../../hooks/useRowsStore";
import type { Hashable } from "../../utils/dataSync";
import type { RowsStore } from "../../utils/rowsStore";
import type {
  ArrCatalogDefinition,
  ArrCatalogModalSelection,
} from "./definition";

interface ArrCatalogDetailModalHostProps<
  TInstRow extends Hashable,
  TAggRow extends Hashable,
  TFilters extends Record<string, unknown>,
  TInstSeed,
  TAggSeed,
  TLiveRow,
  TAggResp,
  TRollup,
> {
  readonly definition: ArrCatalogDefinition<
    TInstRow,
    TAggRow,
    TFilters,
    TInstSeed,
    TAggSeed,
    TLiveRow,
    TAggResp,
    TRollup
  >;
  readonly selection: ArrCatalogModalSelection<TInstSeed | TAggSeed>;
  readonly instanceStore: RowsStore<TInstRow>;
  readonly aggregateStore: RowsStore<TAggRow>;
  readonly onClose: () => void;
}

/**
 * Detail modal host shared by Radarr / Sonarr / Lidarr.
 *
 * Subscribes to the relevant row store by id (`useRowSnapshot`) so update-only polls
 * bring fresh fields into the open modal without closing it or re-rendering siblings.
 * Both subscriptions are taken unconditionally (with one of them passing `null` as
 * the id) so hook order is stable.
 */
function ArrCatalogDetailModalHostInner<
  TInstRow extends Hashable,
  TAggRow extends Hashable,
  TFilters extends Record<string, unknown>,
  TInstSeed,
  TAggSeed,
  TLiveRow,
  TAggResp,
  TRollup,
>({
  definition,
  selection,
  instanceStore,
  aggregateStore,
  onClose,
}: ArrCatalogDetailModalHostProps<
  TInstRow,
  TAggRow,
  TFilters,
  TInstSeed,
  TAggSeed,
  TLiveRow,
  TAggResp,
  TRollup
>): JSX.Element {
  const instanceFresh = useRowSnapshot(
    instanceStore,
    selection.source === "instance" ? selection.id : null,
  );
  const aggregateFresh = useRowSnapshot(
    aggregateStore,
    selection.source === "aggregate" ? selection.id : null,
  );

  const liveRow = definition.getModalLiveRow({
    source: selection.source,
    instanceFresh: (instanceFresh ?? null) as TInstRow | null,
    aggregateFresh: (aggregateFresh ?? null) as TAggRow | null,
    instanceSeed:
      selection.source === "instance"
        ? (selection.seed as TInstSeed)
        : null,
    aggregateSeed:
      selection.source === "aggregate"
        ? (selection.seed as TAggSeed)
        : null,
  });

  const extras = selection.extras ?? {};

  return (
    <ArrModal
      title={definition.getModalTitle(liveRow, extras)}
      onClose={onClose}
      maxWidth={definition.getModalMaxWidth()}
    >
      {definition.renderModalBody({
        liveRow,
        seed: selection.seed,
        source: selection.source,
        extras,
        onClose,
      })}
    </ArrModal>
  );
}

export const ArrCatalogDetailModalHost = memo(
  ArrCatalogDetailModalHostInner,
) as <
  TInstRow extends Hashable,
  TAggRow extends Hashable,
  TFilters extends Record<string, unknown>,
  TInstSeed,
  TAggSeed,
  TLiveRow,
  TAggResp,
  TRollup,
>(
  props: ArrCatalogDetailModalHostProps<
    TInstRow,
    TAggRow,
    TFilters,
    TInstSeed,
    TAggSeed,
    TLiveRow,
    TAggResp,
    TRollup
  >,
) => JSX.Element;
