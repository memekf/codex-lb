import { CheckCircle2, Plus, Save, Trash2, Zap } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/status-badge";
import { useProxies } from "@/features/proxies/hooks/use-proxies";
import type { AccountProxy } from "@/features/proxies/schemas";
import { formatDateTimeInline } from "@/utils/formatters";

export function ProxiesPage() {
  const { proxiesQuery, createMutation, updateMutation, deleteMutation, testSavedMutation, testDraftMutation } =
    useProxies();
  const proxies = useMemo(() => proxiesQuery.data ?? [], [proxiesQuery.data]);
  const [editing, setEditing] = useState<AccountProxy | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [proxyUrl, setProxyUrl] = useState("");
  const [draftResult, setDraftResult] = useState<string | null>(null);

  const resetForm = () => {
    setEditing(null);
    setDisplayName("");
    setProxyUrl("");
    setDraftResult(null);
  };

  const busy =
    createMutation.isPending ||
    updateMutation.isPending ||
    deleteMutation.isPending ||
    testSavedMutation.isPending ||
    testDraftMutation.isPending;

  return (
    <div className="animate-fade-in-up space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Proxies</h1>
        <p className="mt-1 text-sm text-muted-foreground">Manage account egress proxies and health checks.</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[24rem_minmax(0,1fr)]">
        <form
          className="rounded-xl border bg-card p-4"
          onSubmit={(event) => {
            event.preventDefault();
            const payload = { displayName, proxyUrl };
            if (editing) {
              void updateMutation.mutateAsync({ proxyId: editing.id, payload }).then(resetForm);
            } else {
              void createMutation.mutateAsync(payload).then(resetForm);
            }
          }}
        >
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold">{editing ? "Edit proxy" : "New proxy"}</h2>
            {editing ? (
              <Button type="button" size="sm" variant="ghost" onClick={resetForm}>
                <Plus className="h-3.5 w-3.5" />
                New
              </Button>
            ) : null}
          </div>
          <div className="mt-4 space-y-3">
            <label htmlFor="proxy-display-name" className="block text-xs font-medium text-muted-foreground">
              Display name
            </label>
            <Input
              id="proxy-display-name"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="Display name"
              disabled={busy}
            />
            <label htmlFor="proxy-url" className="block text-xs font-medium text-muted-foreground">
              Proxy URL
            </label>
            <Input
              id="proxy-url"
              value={proxyUrl}
              onChange={(event) => setProxyUrl(event.target.value)}
              placeholder="https://user:pass@example.com:8443"
              disabled={busy}
            />
            {draftResult ? <p className="text-xs text-muted-foreground">{draftResult}</p> : null}
            <div className="flex flex-wrap gap-2">
              <Button type="submit" size="sm" disabled={busy || !displayName || !proxyUrl}>
                <Save className="h-3.5 w-3.5" />
                {editing ? "Save changes" : "Save proxy"}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={busy || !proxyUrl}
                onClick={() => {
                  setDraftResult("Testing...");
                  void testDraftMutation.mutateAsync(proxyUrl).then((result) => {
                    setDraftResult(
                      result.lastTestLatencyMs
                        ? `${result.status} in ${result.lastTestLatencyMs} ms`
                        : result.lastTestError || result.status,
                    );
                  });
                }}
              >
                <Zap className="h-3.5 w-3.5" />
                {testDraftMutation.isPending ? "Testing..." : "Test URL"}
              </Button>
            </div>
          </div>
        </form>

        <div className="rounded-xl border bg-card">
          <div className="border-b px-4 py-3">
            <h2 className="text-sm font-semibold">Saved proxies</h2>
          </div>
          <div className="divide-y">
            {proxies.length === 0 ? (
              <div className="p-6 text-sm text-muted-foreground">No proxies saved.</div>
            ) : (
              proxies.map((proxy) => (
                <div
                  key={proxy.id}
                  role="group"
                  aria-label={`${proxy.displayName} proxy`}
                  className="grid gap-3 p-4 md:grid-cols-[minmax(0,1fr)_auto]"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="truncate text-sm font-medium">{proxy.displayName}</p>
                      <StatusBadge status={proxy.status === "working" ? "active" : proxy.status === "failed" ? "exceeded" : "limited"} />
                    </div>
                    <p className="mt-1 truncate font-mono text-xs text-muted-foreground">{proxy.redactedProxyUrl}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {proxy.lastTestedAt
                        ? `Last tested ${formatDateTimeInline(proxy.lastTestedAt)}`
                        : "Not tested"}
                      {proxy.lastTestLatencyMs ? ` | ${proxy.lastTestLatencyMs} ms` : ""}
                      {proxy.lastTestError ? ` | ${proxy.lastTestError}` : ""}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={busy}
                      onClick={() => void testSavedMutation.mutateAsync(proxy.id)}
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      {testSavedMutation.isPending && testSavedMutation.variables === proxy.id ? "Testing..." : "Test"}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={busy}
                      onClick={() => {
                        setEditing(proxy);
                        setDisplayName(proxy.displayName);
                        setProxyUrl("");
                        setDraftResult("Enter the full proxy URL to update this proxy.");
                      }}
                    >
                      Edit
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      disabled={busy}
                      onClick={() => void deleteMutation.mutateAsync(proxy.id)}
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
