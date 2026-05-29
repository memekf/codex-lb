import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WeeklyCoverageSummary } from "@/features/active-timeframes/components/weekly-coverage-summary";
import type { AccountActiveTimeframeCoverageSummary } from "@/features/active-timeframes/schemas";

describe("WeeklyCoverageSummary", () => {
	it("renders coverage metrics and the next gap", () => {
		const summary: AccountActiveTimeframeCoverageSummary = {
			minimumCoverage: 0,
			uncoveredMinutes: 95,
			peakCoverage: 6,
			averageCoverage: 3.14,
			nextGapStart: "2026-05-25T02:00:00Z",
			nextGapEnd: "2026-05-25T03:35:00Z",
		};

		render(<WeeklyCoverageSummary summary={summary} />);

		expect(screen.getByText("Minimum")).toBeInTheDocument();
		expect(screen.getByText("0")).toBeInTheDocument();
		expect(screen.getByText("Uncovered")).toBeInTheDocument();
		expect(screen.getByText("1h 35m")).toBeInTheDocument();
		expect(screen.getByText("Peak")).toBeInTheDocument();
		expect(screen.getByText("6")).toBeInTheDocument();
		expect(screen.getByText("Average")).toBeInTheDocument();
		expect(screen.getByText("3.1")).toBeInTheDocument();
		expect(screen.getByText("Mon 02:00-03:35")).toBeInTheDocument();
	});

	it("renders a no-gap state", () => {
		const summary: AccountActiveTimeframeCoverageSummary = {
			minimumCoverage: 1,
			uncoveredMinutes: 0,
			peakCoverage: 4,
			averageCoverage: 2.5,
			nextGapStart: null,
			nextGapEnd: null,
		};

		render(<WeeklyCoverageSummary summary={summary} />);

		expect(screen.getByText("No uncovered gaps")).toBeInTheDocument();
	});
});
