import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import App from "@/App";
import { createAccountSummary } from "@/test/mocks/factories";
import { server } from "@/test/mocks/server";
import { renderWithProviders } from "@/test/utils";

describe("proxies flow", () => {
  it("lists proxies and opens the proxy workspace", async () => {
    window.history.pushState({}, "", "/proxies");
    renderWithProviders(<App />);

    expect(await screen.findByRole("heading", { name: "Proxies" })).toBeInTheDocument();
    expect(await screen.findByText("Primary proxy")).toBeInTheDocument();
  });

  it("shows an empty state when no proxies are saved", async () => {
    server.use(http.get("/api/proxies", () => HttpResponse.json({ proxies: [] })));
    window.history.pushState({}, "", "/proxies");
    renderWithProviders(<App />);

    expect(await screen.findByText("No proxies saved.")).toBeInTheDocument();
  });

  it("tests, creates, edits, and deletes a proxy", async () => {
    const user = userEvent.setup();
    server.use(
      http.post("/api/proxies/:proxyId/test", async () => {
        await new Promise((resolve) => setTimeout(resolve, 50));
        return HttpResponse.json({
          id: "proxy_primary",
          displayName: "Primary proxy",
          redactedProxyUrl: "https://user:***@proxy.example.com:8443",
          status: "working",
          lastTestedAt: "2026-05-26T12:00:00Z",
          lastTestError: null,
          lastTestLatencyMs: 38,
          createdAt: "2026-05-26T11:00:00Z",
          updatedAt: "2026-05-26T12:00:00Z",
        });
      }),
    );
    window.history.pushState({}, "", "/proxies");
    renderWithProviders(<App />);

    await screen.findByRole("heading", { name: "Proxies" });
    const primaryRow = await screen.findByRole("group", { name: "Primary proxy proxy" });
    await user.click(within(primaryRow).getByRole("button", { name: "Test" }));
    expect(within(primaryRow).getByRole("button", { name: "Testing..." })).toBeInTheDocument();
    await waitFor(() => {
      expect(within(screen.getByRole("group", { name: "Primary proxy proxy" })).getByRole("button", { name: "Test" })).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText("Display name"), "Temporary proxy");
    await user.type(screen.getByLabelText("Proxy URL"), "https://user:secret@temp.example.com:8443");
    await user.click(screen.getByRole("button", { name: "Test URL" }));
    expect(await screen.findByText("working in 38 ms")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Save proxy" }));
    let proxyRow = await screen.findByRole("group", { name: "Temporary proxy proxy" });
    expect(within(proxyRow).getByText("https://user:***@temp.example.com:8443")).toBeInTheDocument();

    await user.click(within(proxyRow).getByRole("button", { name: "Edit" }));
    await user.clear(screen.getByLabelText("Display name"));
    await user.type(screen.getByLabelText("Display name"), "Updated proxy");
    await user.type(screen.getByLabelText("Proxy URL"), "https://updated.example.com:8443");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    proxyRow = await screen.findByRole("group", { name: "Updated proxy proxy" });
    await user.click(within(proxyRow).getByRole("button", { name: "Delete" }));
    await waitFor(() => {
      expect(screen.queryByRole("group", { name: "Updated proxy proxy" })).not.toBeInTheDocument();
    });
  });

  it("shows a failed draft proxy test result", async () => {
    const user = userEvent.setup();
    server.use(
      http.post("/api/proxies/test", () =>
        HttpResponse.json({
          status: "failed",
          lastTestedAt: "2026-05-26T12:00:00Z",
          lastTestError: "Connection refused",
          lastTestLatencyMs: null,
        }),
      ),
    );
    window.history.pushState({}, "", "/proxies");
    renderWithProviders(<App />);

    await screen.findByRole("heading", { name: "Proxies" });
    await user.type(screen.getByLabelText("Proxy URL"), "https://failed.example.com:8443");
    await user.click(screen.getByRole("button", { name: "Test URL" }));

    expect(await screen.findByText("Connection refused")).toBeInTheDocument();
  });

  it("updates and clears an account proxy from account detail", async () => {
    const user = userEvent.setup();
    window.history.pushState({}, "", "/accounts");
    renderWithProviders(<App />);

    expect(await screen.findByRole("heading", { name: "Accounts" })).toBeInTheDocument();
    const proxySelect = await screen.findByRole("combobox", { name: "Account proxy" });
    await user.click(proxySelect);
    await user.click(await screen.findByRole("option", { name: "Primary proxy (working)" }));
    expect(await screen.findByText("Account proxy updated")).toBeInTheDocument();

    await user.click(proxySelect);
    await user.click(await screen.findByRole("option", { name: "Direct" }));
    await waitFor(() => {
      expect(proxySelect).toHaveTextContent("Direct");
    });
  });

  it("marks an unavailable assigned proxy as action-needed in account list", async () => {
    server.use(
      http.get("/api/accounts", () =>
        HttpResponse.json({
          accounts: [
            createAccountSummary({
              proxyId: "proxy_failed",
              proxyDisplayName: "Broken proxy",
              proxyStatus: "failed",
              proxyAvailability: "unavailable",
              proxyAvailabilityReason: "proxy_failed",
              proxyLastTestError: "Connection refused",
            }),
          ],
        }),
      ),
    );
    window.history.pushState({}, "", "/accounts");
    renderWithProviders(<App />);

    expect(await screen.findByText("Proxy issue")).toBeInTheDocument();
    expect(await screen.findByText("Proxy: Broken proxy (unavailable)")).toBeInTheDocument();
  });
});
