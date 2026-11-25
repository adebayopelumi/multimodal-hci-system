//history.jsx
import React, { useState } from "react";
import { Search, Trash2, History as HistoryIcon, SearchX } from "lucide-react";
import { useLogs } from "../contexts/LogsContext";
import { Button, Card, EmptyState, LogRow, LOG_TYPES, Page, PageHeader, Segmented, Eyebrow } from "../components/ui";

const FILTERS = [
  { value: "ALL", label: "All" },
  { value: "VOICE", label: "Voice" },
  { value: "GESTURE", label: "Gesture" },
  { value: "ACTION", label: "Action" },
  { value: "SYSTEM", label: "System" },
];

function Stat({ label, value, dot }) {
  return (
    <Card className="px-5 py-4">
      <div className="flex items-center gap-2">
        {dot && <span className={`size-2 rounded-full ${dot}`} aria-hidden="true" />}
        <Eyebrow>{label}</Eyebrow>
      </div>
      <p className="mt-2 text-stat font-normal tabular-nums text-ink">{value}</p>
    </Card>
  );
}

const History = () => {
  // Same live list as the Dashboard, so it's always up to date (no refresh needed)
  const { logs, clearLogs } = useLogs();
  const [filterType, setFilterType] = useState("ALL");
  const [search, setSearch] = useState("");

  const query = search.trim().toLowerCase();
  const filteredLogs = logs.filter((log) => {
    if (filterType !== "ALL" && log.type !== filterType) return false;
    if (!query) return true;
    return `${log.command || ""} ${log.intent || ""}`.toLowerCase().includes(query);
  });

  const count = (type) => logs.filter((l) => l.type === type).length;
  const isFiltered = filterType !== "ALL" || query;

  return (
    <Page className="flex h-full min-h-[600px] flex-col gap-5">
      <PageHeader
        title="History"
        description="Everything the assistant heard, saw and did since you opened the app. It starts empty each launch."
        actions={
          <Button variant="secondary" onClick={clearLogs} disabled={!logs.length}>
            <Trash2 aria-hidden="true" />
            Clear history
          </Button>
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Total events" value={logs.length} />
        <Stat label="Voice" value={count("VOICE")} dot={LOG_TYPES.VOICE.dot} />
        <Stat label="Gestures" value={count("GESTURE")} dot={LOG_TYPES.GESTURE.dot} />
        <Stat
          label="Actions & system"
          value={count("ACTION") + count("SYSTEM")}
          dot={LOG_TYPES.ACTION.dot}
        />
      </div>

      <Card className="flex min-h-0 flex-1 flex-col">
        {/* Toolbar */}
        <div className="flex flex-wrap items-center gap-3 border-b border-hairline-soft px-5 py-3">
          <Segmented label="Filter by type" options={FILTERS} value={filterType} onChange={setFilterType} size="sm" />

          <div className="relative min-w-[220px] flex-1">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted"
              aria-hidden="true"
            />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search commands and intents"
              aria-label="Search history"
              className="h-8 w-full rounded-md border border-hairline-strong bg-card pl-9 pr-3 text-caption text-ink placeholder:text-muted-soft focus:border-ink focus:outline-none"
            />
          </div>

          <span className="text-caption tabular-nums text-muted" aria-live="polite">
            {isFiltered ? `${filteredLogs.length} of ${logs.length}` : `${logs.length}`}{" "}
            {logs.length === 1 && !isFiltered ? "event" : "events"}
          </span>
        </div>

        {/* Timeline */}
        <div className="min-h-0 flex-1 overflow-y-auto rounded-b-lg bg-canvas-soft">
          {logs.length === 0 ? (
            <EmptyState icon={HistoryIcon} title="No activity yet">
              Start the assistant on the Dashboard. Voice commands, gestures and actions appear here as they happen.
            </EmptyState>
          ) : filteredLogs.length === 0 ? (
            <EmptyState icon={SearchX} title="No matching events">
              Try another type or search term.
            </EmptyState>
          ) : (
            <ul>
              {filteredLogs.map((log) => (
                <LogRow key={log.id} log={log} />
              ))}
            </ul>
          )}
        </div>
      </Card>
    </Page>
  );
};

export default History;
