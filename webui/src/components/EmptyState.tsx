import type { JSX, ReactNode } from "react";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  message?: string;
  action?: ReactNode;
}

export function EmptyState({ icon, title, message, action }: EmptyStateProps): JSX.Element {
  return (
    <div className="empty-state">
      {icon && <div className="empty-state__icon">{icon}</div>}
      <div className="empty-state__content">
        <h3 className="empty-state__title">{title}</h3>
        {message && <p className="empty-state__message">{message}</p>}
        {action && <div className="empty-state__action">{action}</div>}
      </div>
    </div>
  );
}
