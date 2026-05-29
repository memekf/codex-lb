import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WeeklyCoverageTimetable } from "@/features/active-timeframes/components/weekly-coverage-timetable";
import type { AccountActiveTimeframeCoverage } from "@/features/active-timeframes/schemas";

const COVERAGE: AccountActiveTimeframeCoverage = {
	weekStart: "2026-05-25T00:00:00Z",
	weekEnd: "2026-06-01T00:00:00Z",
	segments: [
		{
			start: "2026-05-25T00:00:00Z",
			end: "2026-05-25T09:00:00Z",
			activeAccountCount: 0,
			accounts: [],
		},
		{
			start: "2026-05-25T09:00:00Z",
			end: "2026-05-25T13:00:00Z",
			activeAccountCount: 1,
			accounts: [{ accountId: "acc-alpha", label: "Alpha" }],
		},
		{
			start: "2026-05-25T13:00:00Z",
			end: "2026-05-25T17:00:00Z",
			activeAccountCount: 3,
			accounts: [
				{ accountId: "acc-alpha", label: "Alpha" },
				{ accountId: "acc-beta", label: "Beta" },
				{ accountId: "acc-gamma", label: "Gamma" },
			],
		},
		{
			start: "2026-05-26T00:00:00Z",
			end: "2026-05-27T00:00:00Z",
			activeAccountCount: 5,
			accounts: [{ accountId: "acc-night", label: "Night pool" }],
		},
	],
	summary: {
		minimumCoverage: 0,
		uncoveredMinutes: 540,
		peakCoverage: 5,
		averageCoverage: 1.4,
		nextGapStart: "2026-05-25T00:00:00Z",
		nextGapEnd: "2026-05-25T09:00:00Z",
	},
};

describe("WeeklyCoverageTimetable", () => {
	it("renders weekday rows and timeline ticks", () => {
		render(<WeeklyCoverageTimetable coverage={COVERAGE} />);

		for (const weekday of ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]) {
			expect(screen.getByText(weekday)).toBeInTheDocument();
		}
		for (const tick of ["00", "03", "06", "09", "12", "15", "18", "21", "24"]) {
			expect(screen.getByText(tick)).toBeInTheDocument();
		}
	});

	it("renders coverage blocks with counts, gap styling, and account labels in titles", () => {
		render(<WeeklyCoverageTimetable coverage={COVERAGE} />);

		expect(screen.getByText("0")).toHaveAttribute("data-coverage-level", "0");
		expect(screen.getByText("0")).toHaveClass("border-dashed");
		expect(screen.getByText("1")).toHaveAttribute("title", "Mon 09:00-13:00 | 1 active | Alpha");
		expect(screen.getByText("3")).toHaveAttribute("data-coverage-level", "3");
		expect(screen.getByText("5")).toHaveAttribute("data-coverage-level", "5");
		expect(screen.getByText("3")).toHaveClass("bg-lime-500");
		expect(screen.getByText("5")).toHaveClass("bg-green-600");
	});
});
