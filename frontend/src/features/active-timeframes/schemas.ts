import { z } from "zod";

export const ActiveTimeframeModeSchema = z.enum(["fixed_weekdays", "random_weekly_days"]);

export const AccountActiveTimeframeSchema = z.object({
  id: z.string(),
  displayName: z.string(),
  timezone: z.string(),
  startTime: z.string(),
  endTime: z.string(),
  startMinute: z.number().int(),
  endMinute: z.number().int(),
  mode: ActiveTimeframeModeSchema,
  weekdays: z.array(z.number().int()).default([]),
  randomDaysPerWeek: z.number().int().nullable().optional(),
  currentWeekdays: z.array(z.number().int()).default([]),
  availability: z.enum(["always", "active", "inactive", "missing", "invalid"]).or(z.string()),
  availabilityReason: z.string(),
  nextChangeAt: z.string().datetime({ offset: true }).nullable().optional(),
  createdAt: z.string().datetime({ offset: true }),
  updatedAt: z.string().datetime({ offset: true }),
});

export const AccountActiveTimeframesResponseSchema = z.object({
  timeframes: z.array(AccountActiveTimeframeSchema),
});

export const AccountActiveTimeframeUpsertRequestSchema = z.object({
  displayName: z.string().min(1),
  timezone: z.string().min(1),
  startTime: z.string().min(1),
  endTime: z.string().min(1),
  mode: ActiveTimeframeModeSchema,
  weekdays: z.array(z.number().int()).optional(),
  randomDaysPerWeek: z.number().int().nullable().optional(),
});

export const AccountActiveTimeframeDeleteResponseSchema = z.object({
  status: z.string(),
});

export const AccountActiveTimeframeCoverageAccountSchema = z.object({
  accountId: z.string(),
  label: z.string(),
});

export const AccountActiveTimeframeCoverageSegmentSchema = z.object({
  start: z.string().datetime({ offset: true }),
  end: z.string().datetime({ offset: true }),
  activeAccountCount: z.number().int(),
  accounts: z.array(AccountActiveTimeframeCoverageAccountSchema).default([]),
});

export const AccountActiveTimeframeCoverageSummarySchema = z.object({
  minimumCoverage: z.number().int(),
  uncoveredMinutes: z.number().int(),
  peakCoverage: z.number().int(),
  averageCoverage: z.number(),
  nextGapStart: z.string().datetime({ offset: true }).nullable(),
  nextGapEnd: z.string().datetime({ offset: true }).nullable(),
});

export const AccountActiveTimeframeCoverageSchema = z.object({
  weekStart: z.string().datetime({ offset: true }),
  weekEnd: z.string().datetime({ offset: true }),
  segments: z.array(AccountActiveTimeframeCoverageSegmentSchema),
  summary: AccountActiveTimeframeCoverageSummarySchema,
});

export type AccountActiveTimeframe = z.infer<typeof AccountActiveTimeframeSchema>;
export type AccountActiveTimeframeUpsertRequest = z.infer<typeof AccountActiveTimeframeUpsertRequestSchema>;
export type AccountActiveTimeframeCoverage = z.infer<typeof AccountActiveTimeframeCoverageSchema>;
export type AccountActiveTimeframeCoverageSegment = z.infer<typeof AccountActiveTimeframeCoverageSegmentSchema>;
export type AccountActiveTimeframeCoverageSummary = z.infer<typeof AccountActiveTimeframeCoverageSummarySchema>;
