import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import App from "@/App";
import { renderWithProviders } from "@/test/utils";

describe("active timeframes flow", () => {
  it("lists and creates active timeframes", async () => {
    const user = userEvent.setup();
    window.history.pushState({}, "", "/timeframes");

    renderWithProviders(<App />);

    expect(await screen.findByRole("heading", { name: "Timeframes" })).toBeInTheDocument();
    expect(await screen.findByText("Weekly coverage")).toBeInTheDocument();
    expect(screen.getByLabelText("Include always-active accounts")).toBeChecked();
    expect(screen.getByText("Minimum")).toBeInTheDocument();
    expect(screen.getByTitle("Mon 09:00-13:00 | 2 active | primary@example.com, secondary@example.com")).toBeInTheDocument();

    await user.click(screen.getByLabelText("Include always-active accounts"));
    expect(await screen.findByTitle("Mon 09:00-13:00 | 1 active | primary@example.com")).toBeInTheDocument();
    expect(await screen.findByText("Office hours")).toBeInTheDocument();

    await user.clear(screen.getByLabelText("Display name"));
    await user.type(screen.getByLabelText("Display name"), "Night shift");
    await user.clear(screen.getByLabelText("Timezone"));
    await user.type(screen.getByLabelText("Timezone"), "UTC");
    await user.click(screen.getByRole("button", { name: "Random days" }));
    await user.clear(screen.getByLabelText("Random days per week"));
    await user.type(screen.getByLabelText("Random days per week"), "2");
    await user.click(screen.getByRole("button", { name: "Save timeframe" }));

    expect(await screen.findByText("Night shift")).toBeInTheDocument();
    expect(await screen.findByText(/2 random days/)).toBeInTheDocument();
  });

  it("assigns an active timeframe from account details", async () => {
    const user = userEvent.setup();
    window.history.pushState({}, "", "/accounts");

    renderWithProviders(<App />);

    expect(await screen.findByRole("heading", { name: "Accounts" })).toBeInTheDocument();
    await screen.findByText("Active timeframe");
    await user.click(await screen.findByLabelText("Account active timeframe"));
    await user.click(await screen.findByText("Office hours"));

    expect(await screen.findByText(/Office hours \| active/)).toBeInTheDocument();
  });
});
