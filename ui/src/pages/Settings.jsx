import React, { useEffect, useState } from "react";
import { Trash2, Check } from "lucide-react";
import { useSettings } from "../contexts/SettingsContext";
import { useLogs } from "../contexts/LogsContext";
import { Button, Card, Eyebrow, Page, PageHeader, Segmented, Switch, MODE_OPTIONS } from "../components/ui";

const SETTINGS_KEY = "capstone-settings";

// Save a setting right away too (not only on the next render), so it survives
// quitting the app straight after changing it.
function persistNow(patch) {
  try {
    const prev = JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}");
    localStorage.setItem(SETTINGS_KEY, JSON.stringify({ ...prev, ...patch }));
  } catch {
    // storage unavailable: the settings context still saves on the next render
  }
}

function Section({ title, children }) {
  return (
    <section className="space-y-3">
      <Eyebrow>{title}</Eyebrow>
      <Card className="divide-y divide-hairline-soft">{children}</Card>
    </section>
  );
}

function Row({ label, description, htmlFor, children }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-8 gap-y-3 px-5 py-4">
      <div className="min-w-[220px] flex-1">
        {htmlFor ? (
          <label htmlFor={htmlFor} className="cursor-pointer text-ui font-medium text-ink">
            {label}
          </label>
        ) : (
          <p className="text-ui font-medium text-ink">{label}</p>
        )}
        {description && <p className="mt-0.5 text-caption text-muted">{description}</p>}
      </div>
      <div className="flex shrink-0 items-center gap-3">{children}</div>
    </div>
  );
}

export default function Settings() {
  const { autoStart, setAutoStart, startMode, setStartMode, theme, setTheme } = useSettings();

  const { logs, clearLogs } = useLogs();
  const [justCleared, setJustCleared] = useState(false);

  useEffect(() => {
    if (!justCleared) return;
    const t = setTimeout(() => setJustCleared(false), 2000);
    return () => clearTimeout(t);
  }, [justCleared]);

  useEffect(() => {
    if (!window.api?.saveSettings) return;
    window.api.saveSettings({ autoStart, startMode });
  }, [autoStart, startMode]);

  useEffect(() => {
    if (!window.api?.setAutoStart) return;
    window.api.setAutoStart(autoStart);
  }, [autoStart]);

  const handleAutoStart = (value) => {
    setAutoStart(value);
    persistNow({ autoStart: value });
  };

  const handleStartMode = (value) => {
    setStartMode(value);
    persistNow({ startMode: value });
  };

  const handleTheme = (value) => {
    setTheme(value);
    persistNow({ theme: value });
  };

  const handleClearLogs = () => {
    clearLogs();
    setJustCleared(true);
  };

  return (
    <Page narrow className="space-y-8">
      <PageHeader
        title="Settings"
        description="Choose how the app looks and how the assistant starts, and manage this session's activity log."
      />

      <Section title="Appearance">
        <Row label="Theme" description="Dark matches Cursor's look. Light uses the warm cream version.">
          <Segmented
            label="Theme"
            options={[
              { value: "dark", label: "Dark" },
              { value: "light", label: "Light" },
            ]}
            value={theme === "light" ? "light" : "dark"}
            onChange={handleTheme}
          />
        </Row>
      </Section>

      <Section title="Startup">
        <Row
          label="Start assistant on launch"
          description="Start listening and tracking as soon as the app opens."
          htmlFor="setting-autostart"
        >
          <Switch id="setting-autostart" checked={autoStart} onChange={handleAutoStart} />
        </Row>
        <Row
          label="Start with"
          description={autoStart ? "Which inputs to turn on at launch." : "Turn on “Start assistant on launch” to choose."}
        >
          <Segmented
            label="Start with"
            options={MODE_OPTIONS}
            value={startMode}
            onChange={handleStartMode}
            disabled={!autoStart}
          />
        </Row>
      </Section>

      <Section title="Activity log">
        <Row
          label="Clear activity log"
          description="The log starts empty each time you open the app and is never saved to disk."
        >
          <span className="text-caption tabular-nums text-muted" aria-live="polite">
            {justCleared ? (
              <span className="inline-flex items-center gap-1 text-success">
                <Check className="size-3.5" aria-hidden="true" />
                Logs cleared
              </span>
            ) : (
              `${logs.length} ${logs.length === 1 ? "entry" : "entries"} this session`
            )}
          </span>
          <Button variant="danger" onClick={handleClearLogs} disabled={!logs.length}>
            <Trash2 aria-hidden="true" />
            Clear log
          </Button>
        </Row>
      </Section>
    </Page>
  );
}
