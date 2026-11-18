#!/usr/bin/env node
// Curates per-event playing times from the organiser's own write-up.
//
// The flat startTime/endTime pair in events.json came from the listing and is wrong
// for events that run in two blocks a day ("08:00-12:00 và 13:30-17:30"), open at
// different hours on different days, or have several one-off sessions. This script
// adds a `slots` array ([{date, start, end}]) for those events, keeps startTime and
// endTime as the overall envelope for older readers, and widens `days` when the
// write-up names dates the listing missed.
//
// Usage: node tools/apply-time-slots.mjs [--check]
//   --check  exit 1 when events.json differs from the curated result

import { readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const checkOnly = process.argv.includes("--check");

const datesBetween = (from, to) => {
  const out = [];
  const cursor = new Date(`${from}T12:00:00Z`);
  const last = new Date(`${to}T12:00:00Z`);
  while (cursor <= last) {
    out.push(cursor.toISOString().slice(0, 10));
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return out;
};

const slots = (list) => list.flatMap(([dates, ranges]) =>
  dates.flatMap((date) => ranges.map(([start, end]) => ({ date, start, end }))));

const daily = (from, to, ranges) => slots([[datesBetween(from, to), ranges]]);

// Friday, Saturday and Sunday evenings inside a range, as stated by the organiser
// ("19:00 - 22:00 tối thứ 6, thứ 7, Chủ nhật").
const weekendEvenings = (from, to, range) =>
  datesBetween(from, to)
    .filter((date) => [5, 6, 0].includes(new Date(`${date}T12:00:00Z`).getUTCDay()))
    .map((date) => ({ date, start: range[0], end: range[1] }));

const overrides = {
  // 13/11 15:00–21:00, 14/11 09:30–21:00, 15/11 09:30–20:00
  e04: { slots: slots([
    [["2026-11-13"], [["15:00", "21:00"]]],
    [["2026-11-14"], [["09:30", "21:00"]]],
    [["2026-11-15"], [["09:30", "20:00"]]]
  ]) },
  // Listing said 15:29; the write-up says 09:00–19:00 daily.
  e05: { startTime: "09:00", endTime: "19:00" },
  // Listing said all day; the write-up says 09:00–17:00 daily.
  e08: { startTime: "09:00", endTime: "17:00" },
  // Two blocks a day plus Friday/Saturday/Sunday evenings.
  e10: { slots: [...daily("2026-11-14", "2026-11-28", [["08:00", "12:00"], ["13:30", "17:30"]])
    .filter((slot) => ["2026-11-14", "2026-11-15", "2026-11-20", "2026-11-21", "2026-11-22", "2026-11-27", "2026-11-28"].includes(slot.date)),
  ...weekendEvenings("2026-11-14", "2026-11-28", ["19:00", "22:00"])
    .filter((slot) => ["2026-11-14", "2026-11-15", "2026-11-20", "2026-11-21", "2026-11-22", "2026-11-27", "2026-11-28"].includes(slot.date))] },
  // A different window on each of the three days.
  e11: { slots: slots([
    [["2026-11-14"], [["08:00", "10:00"]]],
    [["2026-11-21"], [["06:00", "08:00"]]],
    [["2026-11-27"], [["15:00", "17:00"]]]
  ]) },
  // Daily 08:00–12:00 and 13:30–17:30, plus weekend evenings.
  e19: { slots: [...daily("2026-11-14", "2026-11-28", [["08:00", "12:00"], ["13:30", "17:30"]]),
    ...weekendEvenings("2026-11-14", "2026-11-28", ["19:00", "22:00"])] },
  // Opening ceremony morning at Hoàn Kiếm, award session afternoon on Mai Hắc Đế.
  e21: { slots: slots([[["2026-11-14"], [["08:30", "10:30"], ["13:30", "16:00"]]]]) },
  // Two blocks a day, not one continuous 09:00–22:00 window.
  e31: { slots: daily("2026-11-14", "2026-11-25", [["09:00", "12:00"], ["14:00", "22:00"]]) },
  // 14–15/11 to 22:00, but only to 21:00 from 17/11; closed on 16/11.
  e49: {
    days: ["2026-11-14", "2026-11-15", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20", "2026-11-21", "2026-11-22"],
    slots: slots([
      [["2026-11-14", "2026-11-15"], [["09:00", "22:00"]]],
      [datesBetween("2026-11-17", "2026-11-22"), [["09:00", "21:00"]]]
    ])
  },
  // Parade around the lake, then the stage programme.
  e68: {
    startTime: "15:00",
    endTime: "18:30",
    slots: slots([[["2026-11-14"], [["15:00", "17:00"], ["17:00", "18:30"]]]])
  },
  // Limited preview on the evening of 15/11, then 08:00–20:00 daily.
  e70: { slots: [...slots([[["2026-11-15"], [["17:00", "20:00"]]]]),
    ...daily("2026-11-16", "2026-11-28", [["08:00", "20:00"]])] },
  // Two blocks a day plus weekend evenings.
  e71: { slots: [...daily("2026-11-15", "2026-11-28", [["08:00", "12:00"], ["13:30", "17:30"]]),
    ...weekendEvenings("2026-11-15", "2026-11-28", ["19:00", "22:00"])] },
  // Four separate workshops across three days.
  e73: { slots: slots([
    [["2026-11-15"], [["09:00", "11:00"], ["16:00", "17:45"]]],
    [["2026-11-21"], [["09:00", "11:00"]]],
    [["2026-11-22"], [["08:00", "09:45"]]]
  ]) },
  // Workshop days follow the venue hours, evening slot included.
  e74: { slots: slots([
    [["2026-11-15", "2026-11-21"], [["08:00", "12:00"], ["13:30", "17:30"], ["19:00", "22:00"]]]
  ]) },
  // Two talks on 22/11, one on 15/11.
  e78: { slots: slots([
    [["2026-11-15"], [["14:00", "16:00"]]],
    [["2026-11-22"], [["10:00", "12:00"], ["14:00", "16:00"]]]
  ]) },
  // Gallery hours are split by a lunch break, not 09:00–18:00 continuous.
  e90: { slots: daily("2026-11-17", "2026-12-13", [["09:00", "12:00"], ["14:00", "17:00"]]) },
  // Listing said 14:00–17:00; the write-up says 14:00–15:00.
  e91: { startTime: "14:00", endTime: "15:00" },
  // Listing put the performance on 19/11 07:00–20:30; the write-up says 19:30 on 18/11.
  e100: { date: "2026-11-18", dateEnd: "2026-11-18", days: null, startTime: "19:30", endTime: "20:00" },
  // 09:00–22:00 on 21/11, 08:00–10:00 on 22/11.
  e113: { slots: slots([
    [["2026-11-21"], [["09:00", "22:00"]]],
    [["2026-11-22"], [["08:00", "10:00"]]]
  ]) },
  // Morning and afternoon workshop on 21/11, morning only on 22/11.
  e115: { slots: slots([
    [["2026-11-21"], [["09:00", "11:30"], ["14:00", "16:30"]]],
    [["2026-11-22"], [["09:00", "11:30"]]]
  ]) },
  // 10:00–20:00 on the three festival days, 14:00–20:00 on 24–27/11.
  e119: {
    days: ["2026-11-21", "2026-11-22", "2026-11-24", "2026-11-25", "2026-11-26", "2026-11-27", "2026-11-28"],
    slots: slots([
      [["2026-11-21", "2026-11-22", "2026-11-28"], [["10:00", "20:00"]]],
      [datesBetween("2026-11-24", "2026-11-27"), [["14:00", "20:00"]]]
    ])
  },
  // Afternoon screenings, two evening screenings, and a 27/11 date the listing missed.
  e125: {
    dateEnd: "2026-11-27",
    days: ["2026-11-21", "2026-11-22", "2026-11-24", "2026-11-26", "2026-11-27"],
    slots: slots([
      [["2026-11-21", "2026-11-22"], [["15:00", "17:00"]]],
      [["2026-11-24", "2026-11-26"], [["19:00", "21:00"]]],
      [["2026-11-27"], [["19:30", "21:30"]]]
    ])
  },
  // Morning and afternoon performance on 22/11.
  e133: { slots: slots([[["2026-11-22"], [["11:00", "12:00"], ["14:00", "16:00"]]]]) },
  // A different late slot on each night.
  e137: { slots: slots([
    [["2026-11-22"], [["20:00", "21:00"]]],
    [["2026-11-28"], [["22:00", "23:00"]]]
  ]) },
  // Listing said 19:00–21:00; the write-up says 19:30–21:30.
  e154: { startTime: "19:30", endTime: "21:30" }
};

const data = JSON.parse(await readFile(join(root, "events.json"), "utf8"));
let touched = 0;

for (const [id, patch] of Object.entries(overrides)) {
  const event = data.events.find((item) => item.id === id);
  if (!event) throw new Error(`events.json has no ${id}`);
  const next = { ...event, ...patch };
  if (patch.slots) {
    const seen = new Set();
    next.slots = patch.slots
      .filter((slot) => {
        const key = `${slot.date}|${slot.start}|${slot.end}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .sort((a, b) => a.date.localeCompare(b.date) || a.start.localeCompare(b.start));
    const starts = next.slots.map((slot) => slot.start).sort();
    const ends = next.slots.map((slot) => (slot.end === "00:00" ? "23:59" : slot.end)).sort();
    next.startTime = starts[0];
    next.endTime = ends[ends.length - 1] === "23:59" ? "00:00" : ends[ends.length - 1];
    if (!patch.days) {
      // Keep the plain "date – dateEnd" display when the slots cover every day in the
      // range; only list explicit days when the event skips some.
      const slotDates = [...new Set(next.slots.map((slot) => slot.date))].sort();
      const rangeDates = datesBetween(next.date, next.dateEnd);
      const contiguous = slotDates.length === rangeDates.length &&
        slotDates.every((date, index) => date === rangeDates[index]);
      next.days = contiguous ? null : slotDates;
    }
  }
  if (JSON.stringify(next) !== JSON.stringify(event)) touched += 1;
  Object.assign(event, next);
}

const output = `${JSON.stringify(data, null, 2)}\n`;
const current = await readFile(join(root, "events.json"), "utf8");

if (checkOnly) {
  if (current !== output) {
    console.error("events.json time slots are stale; run node tools/apply-time-slots.mjs");
    process.exit(1);
  }
  console.log("events.json time slots are current");
} else {
  await writeFile(join(root, "events.json"), output, "utf8");
  console.log(`events.json updated (${touched} events with curated times)`);
}
