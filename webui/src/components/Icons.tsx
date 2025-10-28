import type { JSX } from "react";

export interface IconProps {
  className?: string;
  size?: number;
}

function iconClass(className?: string): string {
  return className ? `icon ${className}` : "icon";
}

function iconSize(size?: number): number {
  return size ?? 16;
}

export function IconRefresh({ className, size }: IconProps): JSX.Element {
  const dimension = iconSize(size);
  return (
    <svg
      className={iconClass(className)}
      width={dimension}
      height={dimension}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M12.667 3.333a6 6 0 1 0 1.166 6.334"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M10.667 3.667H13.5v2.834"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconRestart({ className, size }: IconProps): JSX.Element {
  const dimension = iconSize(size);
  return (
    <svg
      className={iconClass(className)}
      width={dimension}
      height={dimension}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M8 3.333a4.667 4.667 0 1 1-3.767 7.514"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M2.5 6.167V2.5h3.667"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M6.167 2.5 2.5 6.167"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconFilter({ className, size }: IconProps): JSX.Element {
  const dimension = iconSize(size);
  return (
    <svg
      className={iconClass(className)}
      width={dimension}
      height={dimension}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <circle
        cx="7"
        cy="7"
        r="3.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path
        d="m10.5 10.5 2 2"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function IconPulse({ className, size }: IconProps): JSX.Element {
  const dimension = iconSize(size);
  return (
    <svg
      className={iconClass(className)}
      width={dimension}
      height={dimension}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <circle
        cx="8"
        cy="8"
        r="5"
        stroke="currentColor"
        strokeWidth="1.5"
        opacity="0.35"
      />
      <circle cx="8" cy="8" r="2.3" fill="currentColor" />
    </svg>
  );
}

export function IconDownload({ className, size }: IconProps): JSX.Element {
  const dimension = iconSize(size);
  return (
    <svg
      className={iconClass(className)}
      width={dimension}
      height={dimension}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M8 2.5v7"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path
        d="m5.5 7.667 2.5 2.5 2.5-2.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M4 12.5h8"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function IconEye({ className, size }: IconProps): JSX.Element {
  const dimension = iconSize(size);
  return (
    <svg
      className={iconClass(className)}
      width={dimension}
      height={dimension}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M2 8s2.333-4 6-4 6 4 6 4-2.333 4-6 4-6-4-6-4Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="8" cy="8" r="1.833" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

export function IconEyeOff({ className, size }: IconProps): JSX.Element {
  const dimension = iconSize(size);
  return (
    <svg
      className={iconClass(className)}
      width={dimension}
      height={dimension}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="m3 13 10-10"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path
        d="M5.2 5.2C3.54 6.295 2.5 8 2.5 8s2.167 4 5.5 4c.702 0 1.343-.13 1.923-.35M12.91 10.014C13.49 9.185 13.833 8.42 13.833 8s-2.333-4-6-4a6.31 6.31 0 0 0-1.403.16"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconClose({ className, size }: IconProps): JSX.Element {
  const dimension = iconSize(size);
  return (
    <svg
      className={iconClass(className)}
      width={dimension}
      height={dimension}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="m4 4 8 8M12 4 4 12"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function IconCheck({ className, size }: IconProps): JSX.Element {
  const dimension = iconSize(size);
  return (
    <svg
      className={iconClass(className)}
      width={dimension}
      height={dimension}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="m3.5 8.5 2.667 2.667L12.5 4.833"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconHammer({ className, size }: IconProps): JSX.Element {
  const dimension = iconSize(size);
  return (
    <svg
      className={iconClass(className)}
      width={dimension}
      height={dimension}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M3.5 5.5 7 2l2.5 2.5L8 6 5.5 8.5 3.5 6.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="m5.5 8.5 4 4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path
        d="M11.5 12.5 10 11"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function IconPlus({ className, size }: IconProps): JSX.Element {
  const dimension = iconSize(size);
  return (
    <svg
      className={iconClass(className)}
      width={dimension}
      height={dimension}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M8 3v10M3 8h10"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function IconTrash({ className, size }: IconProps): JSX.Element {
  const dimension = iconSize(size);
  return (
    <svg
      className={iconClass(className)}
      width={dimension}
      height={dimension}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M3.5 5.5 4 13.5c0 .552.448 1 1 1h6c.552 0 1-.448 1-1l.5-8"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M6.5 7.5v4M9.5 7.5v4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path
        d="M2.5 4.5h11"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path
        d="M6 4.5V3.5c0-.552.448-1 1-1h2c.552 0 1 .448 1 1v1"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function IconCog({ className, size }: IconProps): JSX.Element {
  const dimension = iconSize(size);
  return (
    <svg
      className={iconClass(className)}
      width={dimension}
      height={dimension}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <circle
        cx="8"
        cy="8"
        r="2.5"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path
        d="M8 1.833v1.667M8 12.5v1.667M2.625 3.708l1.179.68M12.196 11.612l1.179.68M1.833 8H3.5M12.5 8h1.667M2.625 12.292l1.179-.68M12.196 4.388l1.179-.68"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function IconExternal({ className, size }: IconProps): JSX.Element {
  const dimension = iconSize(size);
  return (
    <svg
      className={iconClass(className)}
      width={dimension}
      height={dimension}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M6.5 3.5H3.667C2.747 3.5 2 4.247 2 5.167v6.166C2 12.253 2.747 13 3.667 13h6.166C10.753 13 11.5 12.253 11.5 11.333V8.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M9.5 2.5h4v4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M9.5 2.5 5.5 6.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function IconUpdate({ className, size }: IconProps): JSX.Element {
  const dimension = iconSize(size);
  return (
    <svg
      className={iconClass(className)}
      width={dimension}
      height={dimension}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M4.167 9.5c.7 1.467 2.17 2.5 3.833 2.5 2.07 0 3.833-1.679 3.833-3.75 0-2.07-1.763-3.75-3.833-3.75-1.035 0-1.971.414-2.65 1.086"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path
        d="M6.667 3.833H4.167v2.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
