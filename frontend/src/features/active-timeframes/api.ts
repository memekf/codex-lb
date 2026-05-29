import { del, get, post, put } from "@/lib/api-client";

import {
  AccountActiveTimeframeCoverageSchema,
  AccountActiveTimeframeDeleteResponseSchema,
  AccountActiveTimeframesResponseSchema,
  AccountActiveTimeframeSchema,
  AccountActiveTimeframeUpsertRequestSchema,
} from "@/features/active-timeframes/schemas";

const ACTIVE_TIMEFRAMES_BASE_PATH = "/api/active-timeframes";

export function listActiveTimeframes() {
  return get(ACTIVE_TIMEFRAMES_BASE_PATH, AccountActiveTimeframesResponseSchema);
}

export function getActiveTimeframeCoverage(params: {
  weekStart?: string;
  includeAlwaysActive?: boolean;
}) {
  const search = new URLSearchParams();
  if (params.weekStart) {
    search.set("weekStart", params.weekStart);
  }
  if (params.includeAlwaysActive !== undefined) {
    search.set("includeAlwaysActive", String(params.includeAlwaysActive));
  }
  const suffix = search.size > 0 ? `?${search.toString()}` : "";
  return get(`${ACTIVE_TIMEFRAMES_BASE_PATH}/coverage${suffix}`, AccountActiveTimeframeCoverageSchema);
}

export function createActiveTimeframe(payload: unknown) {
  const validated = AccountActiveTimeframeUpsertRequestSchema.parse(payload);
  return post(ACTIVE_TIMEFRAMES_BASE_PATH, AccountActiveTimeframeSchema, { body: validated });
}

export function updateActiveTimeframe(timeframeId: string, payload: unknown) {
  const validated = AccountActiveTimeframeUpsertRequestSchema.parse(payload);
  return put(`${ACTIVE_TIMEFRAMES_BASE_PATH}/${encodeURIComponent(timeframeId)}`, AccountActiveTimeframeSchema, {
    body: validated,
  });
}

export function deleteActiveTimeframe(timeframeId: string) {
  return del(
    `${ACTIVE_TIMEFRAMES_BASE_PATH}/${encodeURIComponent(timeframeId)}`,
    AccountActiveTimeframeDeleteResponseSchema,
  );
}
