import type {
  AccountActiveTimeframeCoverage,
  AccountActiveTimeframeCoverageSegment,
} from "@/features/active-timeframes/schemas";
import { WEEKDAYS } from "@/features/active-timeframes/utils";
import { cn } from "@/lib/utils";

const DAY_MS = 24 * 60 * 60 * 1000;
const TICKS = ["00", "03", "06", "09", "12", "15", "18", "21", "24"] as const;

type DaySegment = {
  segment: AccountActiveTimeframeCoverageSegment;
  dayIndex: number;
  start: Date;
  end: Date;
  dayEnd: Date;
  leftPercent: number;
  widthPercent: number;
};

type WeeklyCoverageTimetableProps = {
  coverage: AccountActiveTimeframeCoverage;
};

export function WeeklyCoverageTimetable({ coverage }: WeeklyCoverageTimetableProps) {
  const daySegments = splitSegmentsByDay(coverage);

  return (
    <div className="min-w-0">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">Weekly coverage</h2>
          <p className="mt-1 text-xs text-muted-foreground">Scheduled active accounts by UTC day.</p>
        </div>
      </div>
      <div className="overflow-x-auto">
        <div className="min-w-[48rem]">
          <div className="ml-12 grid grid-cols-9 text-[11px] text-muted-foreground">
            {TICKS.map((tick) => (
              <span key={tick}>{tick}</span>
            ))}
          </div>
          <div className="mt-2 space-y-2">
            {WEEKDAYS.map((weekday, dayIndex) => (
              <div key={weekday} className="grid grid-cols-[3rem_minmax(0,1fr)] items-center gap-3">
                <div className="text-xs font-medium text-muted-foreground">{weekday}</div>
                <div className="relative h-8 overflow-hidden rounded-md border bg-muted/30">
                  {daySegments
                    .filter((segment) => segment.dayIndex === dayIndex)
                    .map((segment) => (
                      <span
                        key={`${segment.segment.start}-${segment.segment.end}-${segment.leftPercent}`}
                        className={cn(
                          "absolute top-0 flex h-full min-w-6 items-center justify-center overflow-hidden border text-[11px] font-semibold transition-colors",
                          coverageClass(segment.segment.activeAccountCount),
                        )}
                        data-coverage-level={String(Math.min(segment.segment.activeAccountCount, 5))}
                        style={{
                          left: `${segment.leftPercent}%`,
                          width: `${segment.widthPercent}%`,
                        }}
                        title={segmentTitle(segment, weekday)}
                      >
                        {segment.segment.activeAccountCount}
                      </span>
                    ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function splitSegmentsByDay(coverage: AccountActiveTimeframeCoverage): DaySegment[] {
  const weekStart = new Date(coverage.weekStart);
  return coverage.segments.flatMap((segment) => {
    const segmentStart = new Date(segment.start);
    const segmentEnd = new Date(segment.end);
    return WEEKDAYS.flatMap((_weekday, dayIndex) => {
      const dayStart = new Date(weekStart.getTime() + dayIndex * DAY_MS);
      const dayEnd = new Date(dayStart.getTime() + DAY_MS);
      const start = new Date(Math.max(segmentStart.getTime(), dayStart.getTime()));
      const end = new Date(Math.min(segmentEnd.getTime(), dayEnd.getTime()));
      if (start >= end) {
        return [];
      }
      const leftPercent = ((start.getTime() - dayStart.getTime()) / DAY_MS) * 100;
      const widthPercent = ((end.getTime() - start.getTime()) / DAY_MS) * 100;
      return [{ segment, dayIndex, start, end, dayEnd, leftPercent, widthPercent }];
    });
  });
}

function coverageClass(count: number): string {
  if (count === 0) {
    return "border-dashed border-red-300 bg-red-50 text-red-700 dark:bg-red-950/30";
  }
  if (count === 1) {
    return "border-red-500 bg-red-500 text-white";
  }
  if (count === 2) {
    return "border-amber-500 bg-amber-500 text-white";
  }
  if (count === 3) {
    return "border-lime-500 bg-lime-500 text-lime-950";
  }
  if (count === 4) {
    return "border-emerald-500 bg-emerald-500 text-white";
  }
  return "border-green-600 bg-green-600 text-white";
}

function segmentTitle(segment: DaySegment, weekday: string): string {
  const labels = segment.segment.accounts.map((account) => account.label).join(", ") || "No accounts";
  return `${weekday} ${formatUtcTime(segment.start)}-${formatUtcTime(segment.end, segment.dayEnd)} | ${segment.segment.activeAccountCount} active | ${labels}`;
}

function formatUtcTime(value: Date, dayEnd?: Date): string {
  if (dayEnd && value.getTime() === dayEnd.getTime()) {
    return "24:00";
  }
  return `${String(value.getUTCHours()).padStart(2, "0")}:${String(value.getUTCMinutes()).padStart(2, "0")}`;
}
