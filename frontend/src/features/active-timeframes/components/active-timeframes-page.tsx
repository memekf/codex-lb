import { CalendarClock, Plus, Save, Trash2 } from "lucide-react";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { StatusBadge } from "@/components/status-badge";
import { WeeklyCoverageSummary } from "@/features/active-timeframes/components/weekly-coverage-summary";
import { WeeklyCoverageTimetable } from "@/features/active-timeframes/components/weekly-coverage-timetable";
import { useActiveTimeframeCoverage, useActiveTimeframes } from "@/features/active-timeframes/hooks/use-active-timeframes";
import type { AccountActiveTimeframe, AccountActiveTimeframeUpsertRequest } from "@/features/active-timeframes/schemas";
import { WEEKDAYS, weekdayLabel } from "@/features/active-timeframes/utils";
import { formatDateTimeInline } from "@/utils/formatters";

type Mode = "fixed_weekdays" | "random_weekly_days";

const DEFAULT_FORM = {
  displayName: "",
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  startTime: "09:00",
  endTime: "17:00",
  mode: "fixed_weekdays" as Mode,
  weekdays: [0, 1, 2, 3, 4],
  randomDaysPerWeek: 3,
};

export function ActiveTimeframesPage() {
  const { timeframesQuery, createMutation, updateMutation, deleteMutation } = useActiveTimeframes();
  const timeframes = useMemo(() => timeframesQuery.data ?? [], [timeframesQuery.data]);
  const [editing, setEditing] = useState<AccountActiveTimeframe | null>(null);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [includeAlwaysActive, setIncludeAlwaysActive] = useState(true);
  const coverageQuery = useActiveTimeframeCoverage({ includeAlwaysActive });
  const busy = createMutation.isPending || updateMutation.isPending || deleteMutation.isPending;

  const resetForm = () => {
    setEditing(null);
    setForm(DEFAULT_FORM);
  };

  const payload = (): AccountActiveTimeframeUpsertRequest => ({
    displayName: form.displayName,
    timezone: form.timezone,
    startTime: form.startTime,
    endTime: form.endTime,
    mode: form.mode,
    weekdays: form.mode === "fixed_weekdays" ? form.weekdays : undefined,
    randomDaysPerWeek: form.mode === "random_weekly_days" ? form.randomDaysPerWeek : null,
  });

  return (
    <div className="animate-fade-in-up space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Timeframes</h1>
        <p className="mt-1 text-sm text-muted-foreground">Control when assigned accounts can start new upstream work.</p>
      </div>

      <section className="rounded-lg border bg-card p-4">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold">Coverage</h2>
            <p className="mt-1 text-xs text-muted-foreground">A schedule-only view of active account availability.</p>
          </div>
          <div className="flex items-center gap-2">
            <Switch
              id="include-always-active"
              checked={includeAlwaysActive}
              onCheckedChange={setIncludeAlwaysActive}
              size="sm"
            />
            <label htmlFor="include-always-active" className="text-xs font-medium text-muted-foreground">
              Include always-active accounts
            </label>
          </div>
        </div>
        {coverageQuery.isLoading ? (
          <div className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">Loading coverage...</div>
        ) : coverageQuery.isError ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            Coverage could not be loaded.
          </div>
        ) : coverageQuery.data ? (
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_16rem]">
            <WeeklyCoverageTimetable coverage={coverageQuery.data} />
            <WeeklyCoverageSummary summary={coverageQuery.data.summary} />
          </div>
        ) : null}
      </section>

      <div className="grid gap-4 lg:grid-cols-[24rem_minmax(0,1fr)]">
        <form
          className="rounded-xl border bg-card p-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (editing) {
              void updateMutation.mutateAsync({ timeframeId: editing.id, payload: payload() }).then(resetForm);
            } else {
              void createMutation.mutateAsync(payload()).then(resetForm);
            }
          }}
        >
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold">{editing ? "Edit timeframe" : "New timeframe"}</h2>
            {editing ? (
              <Button type="button" size="sm" variant="ghost" onClick={resetForm}>
                <Plus className="h-3.5 w-3.5" />
                New
              </Button>
            ) : null}
          </div>

          <div className="mt-4 space-y-3">
            <Field label="Display name" id="timeframe-display-name">
              <Input
                id="timeframe-display-name"
                value={form.displayName}
                onChange={(event) => setForm((current) => ({ ...current, displayName: event.target.value }))}
                disabled={busy}
              />
            </Field>
            <Field label="Timezone" id="timeframe-timezone">
              <Input
                id="timeframe-timezone"
                value={form.timezone}
                onChange={(event) => setForm((current) => ({ ...current, timezone: event.target.value }))}
                disabled={busy}
              />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Start" id="timeframe-start">
                <Input
                  id="timeframe-start"
                  type="time"
                  value={form.startTime}
                  onChange={(event) => setForm((current) => ({ ...current, startTime: event.target.value }))}
                  disabled={busy}
                />
              </Field>
              <Field label="End" id="timeframe-end">
                <Input
                  id="timeframe-end"
                  type="time"
                  value={form.endTime}
                  onChange={(event) => setForm((current) => ({ ...current, endTime: event.target.value }))}
                  disabled={busy}
                />
              </Field>
            </div>
            <div className="flex rounded-lg border bg-muted/20 p-1">
              {(["fixed_weekdays", "random_weekly_days"] as const).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  className={`h-8 flex-1 rounded-md px-2 text-xs font-medium transition ${
                    form.mode === mode ? "bg-background text-foreground shadow-sm" : "text-muted-foreground"
                  }`}
                  onClick={() => setForm((current) => ({ ...current, mode }))}
                  disabled={busy}
                >
                  {mode === "fixed_weekdays" ? "Fixed days" : "Random days"}
                </button>
              ))}
            </div>
            {form.mode === "fixed_weekdays" ? (
              <div className="grid grid-cols-7 gap-1">
                {WEEKDAYS.map((label, index) => {
                  const active = form.weekdays.includes(index);
                  return (
                    <button
                      key={label}
                      type="button"
                      className={`h-8 rounded-md border text-xs font-medium ${
                        active ? "border-primary bg-primary/10 text-primary" : "text-muted-foreground"
                      }`}
                      onClick={() =>
                        setForm((current) => ({
                          ...current,
                          weekdays: active
                            ? current.weekdays.filter((weekday) => weekday !== index)
                            : [...current.weekdays, index].sort(),
                        }))
                      }
                      disabled={busy}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            ) : (
              <Field label="Random days per week" id="random-days-per-week">
                <Input
                  id="random-days-per-week"
                  type="number"
                  min={1}
                  max={7}
                  value={form.randomDaysPerWeek}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, randomDaysPerWeek: Number(event.target.value) }))
                  }
                  disabled={busy}
                />
              </Field>
            )}
            <Button type="submit" size="sm" disabled={busy || !form.displayName || !form.timezone}>
              <Save className="h-3.5 w-3.5" />
              {editing ? "Save changes" : "Save timeframe"}
            </Button>
          </div>
        </form>

        <div className="rounded-xl border bg-card">
          <div className="border-b px-4 py-3">
            <h2 className="text-sm font-semibold">Saved timeframes</h2>
          </div>
          <div className="divide-y">
            {timeframes.length === 0 ? (
              <div className="p-6 text-sm text-muted-foreground">No timeframes saved.</div>
            ) : (
              timeframes.map((timeframe) => (
                <div key={timeframe.id} className="grid gap-3 p-4 md:grid-cols-[minmax(0,1fr)_auto]">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <CalendarClock className="h-4 w-4 text-muted-foreground" />
                      <p className="truncate text-sm font-medium">{timeframe.displayName}</p>
                      <StatusBadge status={timeframe.availability === "active" ? "active" : "limited"} />
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {timeframe.timezone} | {timeframe.startTime}-{timeframe.endTime} |{" "}
                      {timeframe.mode === "fixed_weekdays"
                        ? weekdayLabel(timeframe.weekdays)
                        : `${timeframe.randomDaysPerWeek ?? 0} random days`}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Current: {weekdayLabel(timeframe.currentWeekdays)}
                      {timeframe.nextChangeAt ? ` | Next change ${formatDateTimeInline(timeframe.nextChangeAt)}` : ""}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={busy}
                      onClick={() => {
                        setEditing(timeframe);
                        setForm({
                          displayName: timeframe.displayName,
                          timezone: timeframe.timezone,
                          startTime: timeframe.startTime,
                          endTime: timeframe.endTime,
                          mode: timeframe.mode,
                          weekdays: timeframe.weekdays,
                          randomDaysPerWeek: timeframe.randomDaysPerWeek ?? 3,
                        });
                      }}
                    >
                      Edit
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      disabled={busy}
                      onClick={() => void deleteMutation.mutateAsync(timeframe.id)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Delete
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, id, children }: { label: string; id: string; children: ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-xs font-medium text-muted-foreground">
        {label}
      </label>
      {children}
    </div>
  );
}
