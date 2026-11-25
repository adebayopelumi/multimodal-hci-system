import { useId } from "react";

// Shared UI building blocks for the MHCI Assistant (see DESIGN.md).
// Dark by default (Cursor's dark look), with a cream light theme. Cards with
// hairlines and no shadows; colors come from the tokens in index.css.

export const MODE_LABELS = {
  both: "Voice + Gesture",
  voice: "Voice",
  gesture: "Gesture",
};

export const MODE_OPTIONS = [
  { value: "both", label: MODE_LABELS.both },
  { value: "voice", label: MODE_LABELS.voice },
  { value: "gesture", label: MODE_LABELS.gesture },
];

const cx = (...parts) => parts.filter(Boolean).join(" ");

/* ---------- Brand ---------- */

// The app mark (same drawing as the macOS icon, electron/make_icon.py):
// a near-black tile with an off-white sound wave that is also a raised hand.
export function AppMark({ className }) {
  const id = useId().replace(/:/g, "");
  const fingers = [
    [452, 352],
    [546, 304],
    [640, 346],
    [734, 432],
  ];
  return (
    <svg viewBox="100 100 824 824" className={className} role="img" aria-label="MHCI Assistant">
      <defs>
        <linearGradient id={`${id}-tile`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#2b2922" />
          <stop offset="1" stopColor="#12110a" />
        </linearGradient>
      </defs>
      <rect x="100" y="100" width="824" height="824" rx="186" fill={`url(#${id}-tile)`} />
      <rect x="101.5" y="101.5" width="821" height="821" rx="184.5" fill="none" stroke="#ffffff" strokeOpacity="0.1" strokeWidth="3" />
      <g fill="#edece6">
        {fingers.map(([x, top]) => (
          <rect key={x} x={x - 33} y={top} width="66" height={706 - top} rx="33" />
        ))}
        <rect x={338 - 33} y={600 - 104} width="66" height="208" rx="33" transform="rotate(-34 338 600)" />
      </g>
    </svg>
  );
}

/* ---------- Buttons ---------- */

// Pill-shaped, like cursor.com: light primary pill on dark, dark secondary pill.
const BUTTON_VARIANTS = {
  primary: "bg-primary text-on-primary hover:bg-primary-active active:bg-primary-active",
  ink: "bg-ink text-canvas hover:bg-ink/90",
  secondary:
    "bg-card text-ink border border-hairline-strong hover:bg-canvas-soft hover:border-muted-soft " +
    "dark:bg-strong dark:border-transparent dark:hover:bg-hairline-strong dark:hover:border-transparent",
  danger:
    "bg-card text-error border border-hairline-strong hover:border-error/50 hover:bg-error/5 " +
    "dark:bg-strong dark:border-transparent dark:hover:bg-error/15",
  ghost: "text-body hover:text-ink hover:bg-strong/60",
};

const BUTTON_SIZES = {
  sm: "h-8 px-3.5 text-caption gap-1.5",
  md: "h-9 px-[18px] text-ui gap-2",
};

export function Button({ variant = "secondary", size = "md", className, type = "button", ...props }) {
  return (
    <button
      type={type}
      className={cx(
        "inline-flex shrink-0 items-center justify-center rounded-full font-medium leading-none whitespace-nowrap select-none",
        "transition-colors duration-150 disabled:opacity-45 disabled:pointer-events-none",
        "[&_svg]:size-4 [&_svg]:shrink-0",
        BUTTON_VARIANTS[variant],
        BUTTON_SIZES[size],
        className,
      )}
      {...props}
    />
  );
}

/* ---------- Surfaces & type ---------- */

export function Card({ className, children, ...props }) {
  return (
    <section className={cx("rounded-lg border border-hairline bg-card", className)} {...props}>
      {children}
    </section>
  );
}

export function CardHeader({ icon: Icon, title, meta, actions, className }) {
  return (
    <div className={cx("flex items-center justify-between gap-3 px-5 h-13 border-b border-hairline-soft", className)}>
      <div className="flex min-w-0 items-center gap-2.5">
        {Icon && <Icon className="size-4 shrink-0 text-muted" aria-hidden="true" />}
        <h2 className="text-title font-semibold text-ink truncate">{title}</h2>
        {meta}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Eyebrow({ className, children }) {
  return (
    <p className={cx("text-eyebrow font-semibold uppercase text-muted", className)}>{children}</p>
  );
}

export function PageHeader({ eyebrow, title, description, actions }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
      <div className="min-w-0 max-w-2xl">
        {eyebrow && <Eyebrow className="mb-2">{eyebrow}</Eyebrow>}
        <h1 className="text-display-md font-normal text-ink">{title}</h1>
        {description && <p className="mt-1.5 text-ui text-body">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
    </header>
  );
}

export function Page({ children, className, narrow }) {
  return (
    <div className="h-full overflow-y-auto">
      <div className={cx("mx-auto w-full px-8 py-6", narrow ? "max-w-[860px]" : "max-w-[1200px]", className)}>
        {children}
      </div>
    </div>
  );
}

/* ---------- Status ---------- */

// Small uppercase pill with a dot: green and pulsing when live.
export function StatusPill({ live, liveLabel, idleLabel }) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-eyebrow font-semibold uppercase leading-none",
        live ? "bg-success/10 text-success" : "bg-strong text-muted",
      )}
    >
      <span className="relative flex size-1.5">
        {live && (
          <span className="absolute inline-flex size-full rounded-full bg-success opacity-60 motion-safe:animate-ping" />
        )}
        <span className={cx("relative inline-flex size-1.5 rounded-full", live ? "bg-success" : "bg-muted-soft")} />
      </span>
      {live ? liveLabel : idleLabel}
    </span>
  );
}

/* ---------- Controls ---------- */

// Segmented control (single choice), e.g. Voice + Gesture | Voice | Gesture.
export function Segmented({ options, value, onChange, disabled, label, size = "md" }) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      aria-disabled={disabled || undefined}
      className={cx(
        "inline-flex items-center rounded-full border border-hairline bg-strong/50 p-0.5 dark:bg-canvas-soft",
        disabled && "opacity-50",
      )}
    >
      {options.map((opt) => {
        const selected = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            onClick={() => onChange(opt.value)}
            className={cx(
              "rounded-full font-medium whitespace-nowrap transition-colors duration-150",
              size === "sm" ? "h-7 px-3 text-caption" : "h-8 px-3.5 text-caption",
              selected
                ? "bg-card text-ink ring-1 ring-hairline-strong dark:bg-strong dark:ring-0"
                : "text-muted hover:text-ink",
              disabled && "pointer-events-none",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

// Toggle switch. Ink when on (light on the dark theme), never an accent color.
export function Switch({ id, checked, onChange, label, disabled }) {
  return (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cx(
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors duration-150",
        checked ? "bg-ink" : "bg-hairline-strong",
        disabled && "opacity-50",
      )}
    >
      <span
        className={cx(
          "inline-block size-4 rounded-full bg-card transition-transform duration-150",
          checked ? "translate-x-[18px]" : "translate-x-0.5",
        )}
      />
    </button>
  );
}

/* ---------- Activity timeline ---------- */

// Timeline pastels mark the kind of event (DESIGN.md: pastels only in the timeline).
// Light theme: solid pastel with ink text. Dark theme: tinted pill with pastel text.
export const LOG_TYPES = {
  VOICE: { label: "Voice", dot: "bg-tl-read", pill: "bg-tl-read text-ink dark:bg-tl-read/15 dark:text-tl-read" },
  GESTURE: { label: "Gesture", dot: "bg-tl-edit", pill: "bg-tl-edit text-ink dark:bg-tl-edit/15 dark:text-tl-edit" },
  ACTION: { label: "Action", dot: "bg-tl-grep", pill: "bg-tl-grep text-ink dark:bg-tl-grep/15 dark:text-tl-grep" },
  SYSTEM: {
    label: "System",
    dot: "bg-tl-thinking",
    pill: "bg-tl-thinking text-ink dark:bg-tl-thinking/15 dark:text-tl-thinking",
  },
};

export function TypePill({ type }) {
  const t = LOG_TYPES[type] || { label: type, pill: "bg-strong text-ink" };
  return (
    <span
      className={cx(
        "inline-flex w-[68px] shrink-0 justify-center rounded-full py-[3px] text-[10px] font-semibold uppercase tracking-[0.08em] leading-none",
        t.pill,
      )}
    >
      {t.label}
    </span>
  );
}

export function LogRow({ log, compact }) {
  return (
    <li
      className={cx(
        "grid grid-cols-[64px_68px_minmax(0,1fr)_auto] items-center gap-3 border-b border-hairline-soft last:border-b-0",
        compact ? "px-4 py-1.5" : "px-5 py-2",
      )}
    >
      <span className="font-mono text-[11.5px] tabular-nums text-muted">{log.timestamp}</span>
      <TypePill type={log.type} />
      <span className="truncate font-mono text-code text-ink" title={log.command}>
        {log.command || "—"}
      </span>
      {log.intent ? (
        <span className="max-w-[220px] truncate font-mono text-[11.5px] text-muted" title={log.intent}>
          {log.intent}
        </span>
      ) : (
        <span />
      )}
    </li>
  );
}

export function EmptyState({ icon: Icon, title, children, className, compact }) {
  return (
    <div
      className={cx(
        "flex h-full flex-col items-center justify-center text-center",
        compact ? "gap-1.5 px-4 py-2" : "gap-2 px-6 py-6",
        className,
      )}
    >
      {Icon && (
        <span className="mb-1 grid size-9 place-items-center rounded-md border border-hairline bg-card text-muted">
          <Icon className="size-4" aria-hidden="true" />
        </span>
      )}
      <p className="text-ui font-medium text-ink">{title}</p>
      {children && <p className="max-w-sm text-caption text-muted">{children}</p>}
    </div>
  );
}
