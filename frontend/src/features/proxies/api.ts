import { del, get, post, put } from "@/lib/api-client";

import {
  AccountProxiesResponseSchema,
  AccountProxyDeleteResponseSchema,
  AccountProxyDraftTestRequestSchema,
  AccountProxySchema,
  AccountProxyTestResponseSchema,
  AccountProxyUpsertRequestSchema,
} from "@/features/proxies/schemas";

const PROXIES_BASE_PATH = "/api/proxies";

export function listProxies() {
  return get(PROXIES_BASE_PATH, AccountProxiesResponseSchema);
}

export function createProxy(payload: unknown) {
  const validated = AccountProxyUpsertRequestSchema.parse(payload);
  return post(PROXIES_BASE_PATH, AccountProxySchema, { body: validated });
}

export function updateProxy(proxyId: string, payload: unknown) {
  const validated = AccountProxyUpsertRequestSchema.parse(payload);
  return put(`${PROXIES_BASE_PATH}/${encodeURIComponent(proxyId)}`, AccountProxySchema, {
    body: validated,
  });
}

export function deleteProxy(proxyId: string) {
  return del(`${PROXIES_BASE_PATH}/${encodeURIComponent(proxyId)}`, AccountProxyDeleteResponseSchema);
}

export function testDraftProxy(proxyUrl: string) {
  const validated = AccountProxyDraftTestRequestSchema.parse({ proxyUrl });
  return post(`${PROXIES_BASE_PATH}/test`, AccountProxyTestResponseSchema, { body: validated });
}

export function testSavedProxy(proxyId: string) {
  return post(`${PROXIES_BASE_PATH}/${encodeURIComponent(proxyId)}/test`, AccountProxySchema);
}
