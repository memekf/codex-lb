import type { AccountActiveTimeframeCoverageSummary } from "@/features/active-timeframes/schemas";

type WeeklyCoverageSummaryProps = {
  summary: AccountActiveTimeframeCoverageSummary;
};

export function WeeklyCoverageSummary({ summary }: WeeklyCoverageSummaryProps) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <h2 className="text-sm font-semibold">Coverage summary</h2>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <Metric label="Minimum" value={summary.minimumCoverage.toString()} />
        <Metric label="Uncovered" value={formatMinutes(summary.uncoveredMinutes)} />
        <Metric label="Peak" value={summary.peakCoverage.toString()} />
        <Metric label="Average" value={summary.averageCoverage.toFixed(1)} />
      </dl>
      <div className="mt-4 border-t pt-3">
        <p className="text-xs font-medium text-muted-foreground">Next gap</p>
        <p className="mt-1 text-sm font-medium">
          {summary.nextGapStart && summary.nextGapEnd
            ? formatGap(summary.nextGapStart, summary.nextGapEnd)
            : "No uncovered gaps"}
        </p>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-lg font-semibold leading-none">{value}</dd>
    </div>
  );
}

function formatMinutes(value: number): string {
  const hours = Math.floor(value / 60);
  const minutes = value % 60;
  if (hours === 0) {
    return `${minutes}m`;
  }
  if (minutes === 0) {
    return `${hours}h`;
  }
  return `${hours}h ${minutes}m`;
}

function formatGap(start: string, end: string): string {
  const startDate = new Date(start);
  const endDate = new Date(end);
  return `${weekday(startDate)} ${time(startDate)}-${time(endDate)}`;
}

function weekday(value: Date): string {
  return ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][value.getUTCDay()] ?? "UTC";
}

function time(value: Date): string {
  return `${String(value.getUTCHours()).padStart(2, "0")}:${String(value.getUTCMinutes()).padStart(2, "0")}`;
}
