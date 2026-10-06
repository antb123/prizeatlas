#!/usr/bin/env python3
"""Render website/calendar/<year>/index.html from website/calendar/events.toml.

    uv run scripts/build_calendar.py
"""
import calendar
from html import escape
from pathlib import Path

import tomllib

CAL_DIR = Path(__file__).resolve().parent.parent / "website" / "calendar"
BASE_URL = "https://prizeatlas.org/awards/calendar/"
KINDS = {"announced": "Announced", "ceremony": "Ceremony", "both": "Announced + ceremony"}
WEEKDAYS = "MTWTFSS"


def day_cell(year: int, month: int, day: int, on_day: list[dict]) -> str:
    classes = ["d"]
    if on_day:
        kinds = {e["kind"] for e in on_day}
        classes.append("mix" if len(kinds) > 1 or "both" in kinds else next(iter(kinds)))
        if all(e["status"] == "projected" for e in on_day):
            classes.append("projected")
    style = ""
    if day == 1:
        style = f' style="grid-column-start:{calendar.monthrange(year, month)[0] + 1}"'
    title = escape("; ".join(f"{e['prize']} {e['kind']}" for e in on_day), quote=True)
    title_attr = f' title="{title}"' if on_day else ""
    return f'<li class="{" ".join(classes)}"{style}{title_attr}>{day}</li>'


def event_row(e: dict, prizes: dict) -> str:
    date = e["date"]
    day = f'<time datetime="{date}">{date[8:10]}</time>' if len(date) == 10 else "TBC"
    tag = ' <span class="tag">projected</span>' if e["status"] == "projected" else ""
    url = escape(prizes[e["prize"]]["url"], quote=True)
    kind = e["kind"]
    return (
        f'<li class="{kind}{" projected" if e["status"] == "projected" else ""}">'
        f'<span class="day">{day}</span>'
        f'<span class="what"><a href="{url}">{escape(e["prize"])}</a> <span class="kind">{KINDS[kind]}</span>{tag}'
        f'<small>{escape(e["note"])}</small></span></li>'
    )


def month_section(year: int, month: int, events: list[dict], prizes: dict) -> str:
    prefix = f"{year}-{month:02d}"
    here = sorted((e for e in events if e["date"].startswith(prefix)), key=lambda e: (len(e["date"]) == 7, e["date"]))
    by_day: dict[int, list[dict]] = {}
    for e in here:
        if len(e["date"]) == 10:
            by_day.setdefault(int(e["date"][8:10]), []).append(e)
    days = calendar.monthrange(year, month)[1]
    heads = "".join(f'<li class="dow">{c}</li>' for c in WEEKDAYS)
    cells = "".join(day_cell(year, month, d, by_day.get(d, [])) for d in range(1, days + 1))
    rows = "".join(event_row(e, prizes) for e in here) or '<li class="none">No events</li>'
    return (
        f'<section class="month" id="{calendar.month_abbr[month].lower()}">'
        f'<h2>{calendar.month_name[month]}</h2>'
        f'<ol class="grid">{heads}{cells}</ol>'
        f'<ul class="events">{rows}</ul></section>'
    )


def page(year: str, years: list[str], meta: dict, events: list[dict], prizes: dict) -> str:
    current = ' aria-current="page"'
    nav = " ".join(f'<a href="../{y}/"{current if y == year else ""}>{y}{" draft" if y > min(years) else ""}</a>' for y in years)
    months = "".join(month_section(int(year), m, events, prizes) for m in range(1, 13))
    url = f"{BASE_URL}{year}/"
    title = escape(f"{meta['title']} | PrizeAtlas", quote=True)
    description = escape(meta["description"], quote=True)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{url}">
<link rel="stylesheet" href="../calendar.css">
</head>
<body>
<header>
<p class="crumbs"><a href="../../../">Home</a> / <a href="../../">Awards</a> / Calendar</p>
<h1>{escape(meta["heading"])}</h1>
<p class="tagline">Calendar of all major science prizes in {year}: announcements and ceremonies.</p>
<nav>{nav}</nav>
<p class="legend"><span class="key announced"></span>Announced <span class="key ceremony"></span>Ceremony
<span class="key mix"></span>Both <span class="key projected"></span>Projected</p>
</header>
<main>{months}</main>
<footer><p>Dates change each year; the month and week are the stable part. TBC means the month is known but not the day.</p></footer>
</body>
</html>
"""


def main() -> None:
    with open(CAL_DIR / "events.toml", "rb") as f:
        data = tomllib.load(f)
    events, prizes = data["event"], data["prize"]
    unknown = {e["prize"] for e in events} - prizes.keys()
    if unknown:
        raise SystemExit(f"events.toml: events name unknown prizes {sorted(unknown)}")
    years = sorted(data["year"])
    for year in years:
        in_year = [e for e in events if e["date"].startswith(year)]
        path = CAL_DIR / year / "index.html"
        path.parent.mkdir(exist_ok=True)
        path.write_text(page(year, years, data["year"][year], in_year, prizes))
        print(f"wrote {path} events={len(in_year)}")


if __name__ == "__main__":
    main()
