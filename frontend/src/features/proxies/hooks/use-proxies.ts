import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  createProxy,
  deleteProxy,
  listProxies,
  testDraftProxy,
  testSavedProxy,
  updateProxy,
} from "@/features/proxies/api";
import type { AccountProxyUpsertRequest } from "@/features/proxies/schemas";

export function useProxies() {
  const queryClient = useQueryClient();
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["proxies", "list"] });
    void queryClient.invalidateQueries({ queryKey: ["accounts", "list"] });
    void queryClient.invalidateQueries({ queryKey: ["dashboard", "overview"] });
  };

  const proxiesQuery = useQuery({
    queryKey: ["proxies", "list"],
    queryFn: listProxies,
    select: (data) => data.proxies,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });

  const createMutation = useMutation({
    mutationFn: createProxy,
    onSuccess: () => {
      toast.success("Proxy saved");
      invalidate();
    },
    onError: (error: Error) => toast.error(error.message || "Proxy save failed"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ proxyId, payload }: { proxyId: string; payload: AccountProxyUpsertRequest }) =>
      updateProxy(proxyId, payload),
    onSuccess: () => {
      toast.success("Proxy updated");
      invalidate();
    },
    onError: (error: Error) => toast.error(error.message || "Proxy update failed"),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteProxy,
    onSuccess: () => {
      toast.success("Proxy deleted");
      invalidate();
    },
    onError: (error: Error) => toast.error(error.message || "Proxy delete failed"),
  });

  const testSavedMutation = useMutation({
    mutationFn: testSavedProxy,
    onSuccess: () => {
      toast.success("Proxy tested");
      invalidate();
    },
    onError: (error: Error) => toast.error(error.message || "Proxy test failed"),
  });

  const testDraftMutation = useMutation({
    mutationFn: testDraftProxy,
    onError: (error: Error) => toast.error(error.message || "Proxy test failed"),
  });

  return {
    proxiesQuery,
    createMutation,
    updateMutation,
    deleteMutation,
    testSavedMutation,
    testDraftMutation,
  };
}
