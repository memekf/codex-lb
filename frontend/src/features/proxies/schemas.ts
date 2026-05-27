import { z } from "zod";

export const AccountProxySchema = z.object({
  id: z.string(),
  displayName: z.string(),
  redactedProxyUrl: z.string(),
  status: z.enum(["untested", "testing", "working", "failed"]).or(z.string()),
  lastTestedAt: z.string().datetime({ offset: true }).nullable().optional(),
  lastTestError: z.string().nullable().optional(),
  lastTestLatencyMs: z.number().int().nullable().optional(),
  createdAt: z.string().datetime({ offset: true }),
  updatedAt: z.string().datetime({ offset: true }),
});

export const AccountProxiesResponseSchema = z.object({
  proxies: z.array(AccountProxySchema),
});

export const AccountProxyUpsertRequestSchema = z.object({
  displayName: z.string().min(1).max(255),
  proxyUrl: z.string().min(1),
});

export const AccountProxyDraftTestRequestSchema = z.object({
  proxyUrl: z.string().min(1),
});

export const AccountProxyTestResponseSchema = z.object({
  status: z.string(),
  lastTestedAt: z.string().datetime({ offset: true }),
  lastTestError: z.string().nullable().optional(),
  lastTestLatencyMs: z.number().int().nullable().optional(),
});

export const AccountProxyDeleteResponseSchema = z.object({
  status: z.string(),
});

export type AccountProxy = z.infer<typeof AccountProxySchema>;
export type AccountProxyUpsertRequest = z.infer<typeof AccountProxyUpsertRequestSchema>;
