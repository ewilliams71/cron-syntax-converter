import unittest

from cronconv.convert import parse_quartz, parse_standard, to_quartz, to_standard
from cronconv.errors import CronFormatError
from cronconv.fields import QuartzDomSpecial, QuartzDowSpecial


class ParseStandardTests(unittest.TestCase):
    def test_wrong_field_count_raises(self):
        with self.assertRaises(CronFormatError):
            parse_standard("* * * *")

    def test_basic_fields(self):
        standard = parse_standard("*/15 9-17 * * MON-FRI")
        self.assertEqual(standard.minute[0].kind, "wildcard")
        self.assertEqual(standard.minute[0].step, 15)
        self.assertEqual((standard.dow[0].start, standard.dow[0].end), (1, 5))

    def test_dow_seven_rejected_strict(self):
        with self.assertRaises(CronFormatError):
            parse_standard("0 0 * * 7")

    def test_dow_seven_normalized_to_zero_lenient(self):
        standard = parse_standard("0 0 * * 7", lenient=True)
        self.assertEqual(standard.dow[0].start, 0)

    def test_shorthand_daily(self):
        standard = parse_standard("@daily")
        self.assertEqual(to_quartz(standard), "0 0 0 * * ?")

    def test_shorthand_hourly(self):
        standard = parse_standard("@hourly")
        self.assertEqual(to_quartz(standard), "0 0 * * * ?")

    def test_shorthand_weekly(self):
        standard = parse_standard("@weekly")
        self.assertEqual(to_quartz(standard), "0 0 0 ? * 1")

    def test_shorthand_midnight_same_as_daily(self):
        self.assertEqual(parse_standard("@midnight"), parse_standard("@daily"))

    def test_shorthand_unrecognized_raises(self):
        with self.assertRaises(CronFormatError):
            parse_standard("@fortnightly")

    def test_shorthand_reboot_raises(self):
        with self.assertRaises(CronFormatError):
            parse_standard("@reboot")

    def test_shorthand_combined_with_other_fields_raises(self):
        with self.assertRaises(CronFormatError):
            parse_standard("@daily extra")


class ParseQuartzTests(unittest.TestCase):
    def test_wrong_field_count_raises(self):
        with self.assertRaises(CronFormatError):
            parse_quartz("0 0 12 * *")

    def test_neither_placeholder_strict_raises(self):
        with self.assertRaises(CronFormatError):
            parse_quartz("0 0 12 1 * MON")

    def test_both_placeholders_strict_raises(self):
        with self.assertRaises(CronFormatError):
            parse_quartz("0 0 12 ? * ?")

    def test_dom_placeholder_ok(self):
        quartz = parse_quartz("0 0 12 ? * MON-FRI")
        self.assertIsNone(quartz.dom)
        self.assertEqual((quartz.dow[0].start, quartz.dow[0].end), (2, 6))

    def test_optional_year_field(self):
        quartz = parse_quartz("0 0 12 ? * MON 2026")
        self.assertIsNotNone(quartz.year)
        self.assertEqual(quartz.year[0].start, 2026)

    def test_year_omitted_by_default(self):
        quartz = parse_quartz("0 0 12 ? * MON")
        self.assertIsNone(quartz.year)

    def test_dom_last_day(self):
        quartz = parse_quartz("0 0 12 L * ?")
        self.assertEqual(quartz.dom, QuartzDomSpecial(kind="last"))

    def test_dom_last_weekday(self):
        quartz = parse_quartz("0 0 12 LW * ?")
        self.assertEqual(quartz.dom, QuartzDomSpecial(kind="last_weekday"))

    def test_dom_nearest_weekday(self):
        quartz = parse_quartz("0 0 12 15W * ?")
        self.assertEqual(quartz.dom, QuartzDomSpecial(kind="weekday_of", day=15))

    def test_dow_last_occurrence(self):
        quartz = parse_quartz("0 0 12 ? * 6L")
        self.assertEqual(quartz.dow, QuartzDowSpecial(kind="last_weekday_of_month", day=6))

    def test_dow_nth_occurrence(self):
        quartz = parse_quartz("0 0 12 ? * 6#3")
        self.assertEqual(
            quartz.dow, QuartzDowSpecial(kind="nth_weekday_of_month", day=6, nth=3)
        )


class ToQuartzTests(unittest.TestCase):
    def test_dow_only_restricted(self):
        standard = parse_standard("*/15 9-17 * * MON-FRI")
        self.assertEqual(to_quartz(standard), "0 */15 9-17 ? * 2-6")

    def test_dom_only_restricted(self):
        standard = parse_standard("0 9 1 * *")
        self.assertEqual(to_quartz(standard), "0 0 9 1 * ?")

    def test_both_wildcard(self):
        standard = parse_standard("*/5 * * * *")
        self.assertEqual(to_quartz(standard), "0 */5 * * * ?")

    def test_both_restricted_strict_raises(self):
        standard = parse_standard("0 9 1 * 1")
        with self.assertRaises(CronFormatError):
            to_quartz(standard)

    def test_both_restricted_lenient_keeps_dom(self):
        standard = parse_standard("0 9 1 * 1")
        self.assertEqual(to_quartz(standard, lenient=True), "0 0 9 1 * ?")


class ToStandardTests(unittest.TestCase):
    def test_basic(self):
        quartz = parse_quartz("0 0 12 ? * MON-FRI")
        self.assertEqual(to_standard(quartz), "0 12 * * 1-5")

    def test_dom_placeholder_becomes_wildcard(self):
        quartz = parse_quartz("0 30 8 ? * MON")
        self.assertEqual(to_standard(quartz), "30 8 * * 1")

    def test_dow_placeholder_becomes_wildcard(self):
        quartz = parse_quartz("0 30 8 15 * ?")
        self.assertEqual(to_standard(quartz), "30 8 15 * *")

    def test_nonzero_seconds_strict_raises(self):
        quartz = parse_quartz("30 0 9 ? * MON")
        with self.assertRaises(CronFormatError):
            to_standard(quartz)

    def test_nonzero_seconds_lenient_dropped(self):
        quartz = parse_quartz("30 0 9 ? * MON", lenient=True)
        self.assertEqual(to_standard(quartz, lenient=True), "0 9 * * 1")

    def test_year_present_strict_raises(self):
        quartz = parse_quartz("0 0 9 * * ? 2026")
        with self.assertRaises(CronFormatError):
            to_standard(quartz)

    def test_year_present_lenient_dropped(self):
        quartz = parse_quartz("30 0 9 * * ? 2026", lenient=True)
        self.assertEqual(to_standard(quartz, lenient=True), "0 9 * * *")

    def test_dom_special_strict_raises(self):
        quartz = parse_quartz("0 0 9 L * ?")
        with self.assertRaises(CronFormatError):
            to_standard(quartz)

    def test_dom_special_lenient_dropped(self):
        quartz = parse_quartz("0 0 9 L * ?")
        self.assertEqual(to_standard(quartz, lenient=True), "0 9 * * *")

    def test_dow_special_strict_raises(self):
        quartz = parse_quartz("0 0 9 ? * 6#3")
        with self.assertRaises(CronFormatError):
            to_standard(quartz)

    def test_dow_special_lenient_dropped(self):
        quartz = parse_quartz("0 0 9 ? * 6#3")
        self.assertEqual(to_standard(quartz, lenient=True), "0 9 * * *")


if __name__ == "__main__":
    unittest.main()
