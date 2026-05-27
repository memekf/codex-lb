const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

export function weekdayLabel(days: number[] | undefined) {
  return days?.length ? days.map((day) => WEEKDAYS[day] ?? String(day)).join(", ") : "None";
}

export { WEEKDAYS };
