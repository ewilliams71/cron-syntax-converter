import unittest

from cronconv.errors import CronFormatError
from cronconv.fields import (
    DAY_NAMES,
    MONTH_NAMES,
    QUARTZ_DAY_NAMES,
    QuartzDomSpecial,
    QuartzDowSpecial,
    Term,
    parse_field,
    parse_quartz_dom,
    parse_quartz_dow,
    render_field,
)


class TermRenderTests(unittest.TestCase):
    def test_wildcard(self):
        self.assertEqual(Term(kind="wildcard").render(), "*")

    def test_wildcard_with_step(self):
        self.assertEqual(Term(kind="wildcard", step=15).render(), "*/15")

    def test_value(self):
        self.assertEqual(Term(kind="value", start=5).render(), "5")

    def test_range(self):
        self.assertEqual(Term(kind="range", start=1, end=5).render(), "1-5")

    def test_range_with_step(self):
        self.assertEqual(Term(kind="range", start=1, end=10, step=2).render(), "1-10/2")


class ParseFieldTests(unittest.TestCase):
    def test_empty_spec_raises(self):
        with self.assertRaises(CronFormatError):
            parse_field("", 0, 59)

    def test_empty_item_raises(self):
        with self.assertRaises(CronFormatError):
            parse_field("5,,10", 0, 59)

    def test_wildcard(self):
        terms = parse_field("*", 0, 59)
        self.assertEqual(terms, [Term(kind="wildcard")])

    def test_single_value(self):
        terms = parse_field("5", 0, 59)
        self.assertEqual(terms, [Term(kind="value", start=5)])

    def test_range(self):
        terms = parse_field("1-5", 0, 59)
        self.assertEqual(terms, [Term(kind="range", start=1, end=5)])

    def test_step_on_wildcard(self):
        terms = parse_field("*/15", 0, 59)
        self.assertEqual(terms, [Term(kind="wildcard", step=15)])

    def test_step_on_range(self):
        terms = parse_field("1-10/2", 0, 59)
        self.assertEqual(terms, [Term(kind="range", start=1, end=10, step=2)])

    def test_comma_list(self):
        terms = parse_field("1,2,3-5", 0, 59)
        self.assertEqual(
            terms,
            [
                Term(kind="value", start=1),
                Term(kind="value", start=2),
                Term(kind="range", start=3, end=5),
            ],
        )

    def test_step_zero_raises(self):
        with self.assertRaises(CronFormatError):
            parse_field("*/0", 0, 59)

    def test_step_nondigit_raises(self):
        with self.assertRaises(CronFormatError):
            parse_field("*/x", 0, 59)

    def test_descending_range_strict_raises(self):
        with self.assertRaises(CronFormatError):
            parse_field("22-2", 0, 23, strict=True)

    def test_descending_range_lenient_allowed(self):
        terms = parse_field("22-2", 0, 23, strict=False)
        self.assertEqual(terms, [Term(kind="range", start=22, end=2)])

    def test_value_out_of_range_raises(self):
        with self.assertRaises(CronFormatError):
            parse_field("60", 0, 59)

    def test_value_below_minimum_raises(self):
        with self.assertRaises(CronFormatError):
            parse_field("-1", 0, 59)

    def test_non_numeric_value_raises(self):
        with self.assertRaises(CronFormatError):
            parse_field("foo", 0, 59)

    def test_names_lookup(self):
        terms = parse_field("MON-FRI", 0, 6, names=DAY_NAMES)
        self.assertEqual(terms, [Term(kind="range", start=1, end=5)])

    def test_names_are_case_insensitive(self):
        terms = parse_field("mon", 0, 6, names=DAY_NAMES)
        self.assertEqual(terms, [Term(kind="value", start=1)])

    def test_unrecognized_name_raises(self):
        with self.assertRaises(CronFormatError):
            parse_field("XYZ", 1, 12, names=MONTH_NAMES)

    def test_numbers_still_work_when_names_given(self):
        terms = parse_field("3", 1, 12, names=MONTH_NAMES)
        self.assertEqual(terms, [Term(kind="value", start=3)])


class RenderFieldTests(unittest.TestCase):
    def test_round_trip(self):
        spec = "1,2,3-5,*/15"
        self.assertEqual(render_field(parse_field(spec, 0, 59)), spec)


class ParseQuartzDomTests(unittest.TestCase):
    def test_last_day(self):
        self.assertEqual(parse_quartz_dom("L"), QuartzDomSpecial(kind="last"))

    def test_last_day_offset(self):
        self.assertEqual(parse_quartz_dom("L-3"), QuartzDomSpecial(kind="last_offset", offset=3))

    def test_last_day_offset_out_of_range_raises(self):
        with self.assertRaises(CronFormatError):
            parse_quartz_dom("L-31")

    def test_last_weekday(self):
        self.assertEqual(parse_quartz_dom("LW"), QuartzDomSpecial(kind="last_weekday"))

    def test_weekday_nearest(self):
        self.assertEqual(parse_quartz_dom("15W"), QuartzDomSpecial(kind="weekday_of", day=15))

    def test_weekday_nearest_out_of_range_raises(self):
        with self.assertRaises(CronFormatError):
            parse_quartz_dom("32W")

    def test_lowercase_accepted(self):
        self.assertEqual(parse_quartz_dom("lw"), QuartzDomSpecial(kind="last_weekday"))

    def test_ordinary_field_still_parses(self):
        self.assertEqual(parse_quartz_dom("1,15"), parse_field("1,15", 1, 31))

    def test_render(self):
        self.assertEqual(QuartzDomSpecial(kind="last").render(), "L")
        self.assertEqual(QuartzDomSpecial(kind="last_offset", offset=3).render(), "L-3")
        self.assertEqual(QuartzDomSpecial(kind="last_weekday").render(), "LW")
        self.assertEqual(QuartzDomSpecial(kind="weekday_of", day=15).render(), "15W")


class ParseQuartzDowTests(unittest.TestCase):
    def test_last_weekday_of_month_numeric(self):
        self.assertEqual(
            parse_quartz_dow("6L"), QuartzDowSpecial(kind="last_weekday_of_month", day=6)
        )

    def test_last_weekday_of_month_name(self):
        self.assertEqual(
            parse_quartz_dow("FRIL"), QuartzDowSpecial(kind="last_weekday_of_month", day=6)
        )

    def test_nth_weekday_of_month(self):
        self.assertEqual(
            parse_quartz_dow("6#3"), QuartzDowSpecial(kind="nth_weekday_of_month", day=6, nth=3)
        )

    def test_nth_weekday_of_month_name(self):
        self.assertEqual(
            parse_quartz_dow("FRI#3"),
            QuartzDowSpecial(kind="nth_weekday_of_month", day=6, nth=3),
        )

    def test_nth_out_of_range_raises(self):
        with self.assertRaises(CronFormatError):
            parse_quartz_dow("6#6")

    def test_ordinary_field_still_parses(self):
        self.assertEqual(
            parse_quartz_dow("MON-FRI"), parse_field("MON-FRI", 1, 7, names=QUARTZ_DAY_NAMES)
        )

    def test_render(self):
        self.assertEqual(
            QuartzDowSpecial(kind="last_weekday_of_month", day=6).render(), "6L"
        )
        self.assertEqual(
            QuartzDowSpecial(kind="nth_weekday_of_month", day=6, nth=3).render(), "6#3"
        )


if __name__ == "__main__":
    unittest.main()
