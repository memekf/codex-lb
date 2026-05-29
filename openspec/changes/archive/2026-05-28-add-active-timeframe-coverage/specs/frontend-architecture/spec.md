## ADDED Requirements

### Requirement: Timeframes page renders weekly coverage timetable

The Timeframes page SHALL render a weekly active-account coverage timetable from backend-provided coverage segments. The UI SHALL render seven day rows, a 24-hour horizontal scale, proportional coverage blocks, and a coverage summary beside the timetable on desktop or below it on narrow screens.

#### Scenario: Timetable renders day coverage
- **WHEN** coverage data is available
- **THEN** the Timeframes page renders one row per weekday with proportional segments for that day's coverage
- **AND** each segment exposes a tooltip/title containing the day/time range, active account count, and account labels

#### Scenario: Visual scale communicates coverage health
- **WHEN** a segment has zero active accounts
- **THEN** the timetable renders it as a visible zero-coverage gap
- **AND** higher active-account counts are rendered with healthier colors than lower counts

#### Scenario: Include always-active toggle refetches coverage
- **WHEN** an operator toggles `Include always-active accounts`
- **THEN** the frontend refetches coverage with the selected `includeAlwaysActive` value
- **AND** existing active timeframe CRUD behavior remains unchanged
