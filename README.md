# cronconv

Converts cron expressions between standard 5-field cron (crontab, most Unix
schedulers) and Quartz 6/7-field cron (Java schedulers, Spring, Jenkins).

The two formats look similar but aren't the same language:

| | standard cron | Quartz cron |
|---|---|---|
| fields | minute hour dom month dow | second minute hour dom month dow [year] |
| Sunday | `0` | `1` |
| "don't care" for dom/dow | not needed, both are always active | must write `?` on exactly one of them |
| seconds | not representable | required |

That last row is the part people get wrong by hand: a standard cron entry
like `0 9 1 * *` (9am on the 1st of the month) and `0 9 * * 1` (9am every
Monday) both use `*` for the field they don't care about, but Quartz needs
you to say which one you *actually* don't care about with `?`, because its
fields are ANDed once `?` is off the table. A standard cron expression that
restricts *both* day-of-month and day-of-week has no exact Quartz
equivalent, since standard cron ORs those two fields together and Quartz
can't.

By default this tool is strict: it validates field ranges, rejects
ambiguous day-of-month/day-of-week combinations it can't losslessly
translate, and refuses to guess. Pass `--lenient` to get a best-effort
conversion instead of an error in those ambiguous cases.

## Usage

```
$ python -m cronconv to-quartz "*/15 9-17 * * MON-FRI"
0 */15 9-17 ? * 2-6

$ python -m cronconv to-standard "0 0 12 ? * MON-FRI"
0 12 * * 1-5

$ python -m cronconv to-quartz "0 9 1 * 1"
cronconv: cannot convert: both day-of-month and day-of-week are restricted, which
quartz cannot express with AND semantics (pass --lenient to keep day-of-month and
drop day-of-week)

$ python -m cronconv to-quartz --lenient "0 9 1 * 1"
0 0 9 1 * ?

$ python -m cronconv to-standard --lenient "30 0 9 * * ? 2026"
0 9 * * *

$ python -m cronconv to-standard "0 0 9 L * ?"
cronconv: cannot convert: day-of-month value 'L' has no standard cron equivalent
(pass --lenient to drop it)

$ python -m cronconv to-standard --lenient "0 0 9 L * ?"
0 9 * * *

$ python -m cronconv to-quartz "@daily"
0 0 0 * * ?
```

Standard cron's `@yearly`/`@annually`, `@monthly`, `@weekly`, `@daily`/`@midnight`,
and `@hourly` shorthands are accepted as input to `to-quartz` and expanded to
their field equivalent before conversion; `@reboot` has no fixed schedule and
is always rejected, lenient or not.

Quartz's day-of-month and day-of-week fields also accept a handful of special
values standard cron has no notion of: `L` (last day of month), `L-n` (n days
before the last day), `LW` (last weekday of the month), `nW` (weekday nearest
day n), `nL` (last occurrence of weekday n in the month), and `n#k` (the kth
occurrence of weekday n in the month). These parse on `to-standard` input
and, like seconds and year, have no standard cron equivalent: strict mode
rejects them, `--lenient` drops them to `*`. Standard cron has nothing
equivalent to convert *into* Quartz, so `to-quartz` never produces them.

Or install it (`pip install -e .`) to get the `cronconv` command directly:

```
$ cronconv to-quartz "*/5 * * * *"
0 */5 * * * ?
```

## What --lenient actually relaxes

- Accepts `7` as an alias for Sunday in standard cron's day-of-week field.
- Accepts descending ranges (e.g. `22-2`) instead of rejecting them.
- When converting to Quartz, if both day-of-month and day-of-week are
  restricted, keeps day-of-month and drops day-of-week instead of raising.
- When converting to standard cron, drops a non-zero seconds field, a
  year field, or a Quartz `L`/`W`/`#` special value instead of raising,
  since standard cron has nowhere to put them.

Everything else still has to be a structurally valid cron field; `--lenient`
widens a few specific, documented rules, not general error tolerance.

## Known limitations

This first pass covers the field grammar that's common to both formats:
`*`, single values, ranges, steps, comma lists, and month/day names. Names
are accepted on input (`MON`, `JAN`, ...) but always normalized to numbers
on output, since the two formats number weekdays differently and there's no
lossless way to round-trip the name through that shift. Quartz's `L`, `W`,
and `#` day-of-month/day-of-week special values are accepted on
`to-standard` input (see above). Standard cron's `@`-shorthands are accepted
on `to-quartz` input (see above); Quartz has no equivalent shorthand of its
own, so `to-standard` never produces them.

## License

MIT, see [LICENSE](LICENSE).
