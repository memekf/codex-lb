import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  createActiveTimeframe,
  deleteActiveTimeframe,
  getActiveTimeframeCoverage,
  listActiveTimeframes,
  updateActiveTimeframe,
} from "@/features/active-timeframes/api";
import type { AccountActiveTimeframeUpsertRequest } from "@/features/active-timeframes/schemas";

export function useActiveTimeframes() {
  const queryClient = useQueryClient();
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["active-timeframes", "list"] });
    void queryClient.invalidateQueries({ queryKey: ["active-timeframes", "coverage"] });
    void queryClient.invalidateQueries({ queryKey: ["accounts", "list"] });
    void queryClient.invalidateQueries({ queryKey: ["dashboard", "overview"] });
  };

  const timeframesQuery = useQuery({
    queryKey: ["active-timeframes", "list"],
    queryFn: listActiveTimeframes,
    select: (data) => data.timeframes,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });

  const createMutation = useMutation({
    mutationFn: createActiveTimeframe,
    onSuccess: () => {
      toast.success("Timeframe saved");
      invalidate();
    },
    onError: (error: Error) => toast.error(error.message || "Timeframe save failed"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ timeframeId, payload }: { timeframeId: string; payload: AccountActiveTimeframeUpsertRequest }) =>
      updateActiveTimeframe(timeframeId, payload),
    onSuccess: () => {
      toast.success("Timeframe updated");
      invalidate();
    },
    onError: (error: Error) => toast.error(error.message || "Timeframe update failed"),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteActiveTimeframe,
    onSuccess: () => {
      toast.success("Timeframe deleted");
      invalidate();
    },
    onError: (error: Error) => toast.error(error.message || "Timeframe delete failed"),
  });

  return { timeframesQuery, createMutation, updateMutation, deleteMutation };
}

export function useActiveTimeframeCoverage(params: {
  weekStart?: string;
  includeAlwaysActive: boolean;
}) {
  return useQuery({
    queryKey: ["active-timeframes", "coverage", params.weekStart ?? null, params.includeAlwaysActive],
    queryFn: () => getActiveTimeframeCoverage(params),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
}
