import type { ReactNode } from "react";
import type { JSX } from "react";
import { createPortal } from "react-dom";
import { IconImage } from "../IconImage";
import CloseIcon from "../../icons/close.svg";
import { safeClick, useSafeBackdropClose } from "../../utils/safeClick";

interface ArrModalProps {
  title: string;
  children: ReactNode;
  onClose: () => void;
  maxWidth?: number;
}

export function ArrModal({
  title,
  children,
  onClose,
  maxWidth = 560,
}: ArrModalProps): JSX.Element {
  const backdropHandlers = useSafeBackdropClose(onClose);

  return createPortal(
    <div
      className="modal-backdrop"
      role="presentation"
      onPointerDown={backdropHandlers.onPointerDown}
      onPointerUp={backdropHandlers.onPointerUp}
    >
      <div
        className="modal"
        style={{ maxWidth }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="arr-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="arr-modal-title">{title}</h2>
          <button
            type="button"
            className="btn ghost"
            onClick={safeClick(onClose)}
            aria-label="Close"
          >
            <IconImage src={CloseIcon} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>,
    document.body
  );
}
