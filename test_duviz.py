
import unittest

import duviz


class BarTest(unittest.TestCase):

    def test_one(self):
        res = duviz.bar(1, 'x', one='y')
        self.assertEqual(res, 'y')

    def test_zero(self):
        res = duviz.bar(0, 'x')
        self.assertEqual(res, '')

    def test_default(self):
        res = duviz.bar(10, 'abcd')
        self.assertEqual(res, '[--abcd--]')

    def test_left_and_right(self):
        res = duviz.bar(12, 'abcd', left='<<', right='**')
        self.assertEqual(res, '<<--abcd--**')

    def test_fill(self):
        res = duviz.bar(10, 'abcd', fill='+')
        self.assertEqual(res, '[++abcd++]')


class HumanReadableSizeTest(unittest.TestCase):

    def test_human_readable_count(self):
        data = [
            (0, '0'),
            (10, '10'),
            (999, '999'),
            (1000, '1.00k'),
            (5432, '5.43k'),
            (5678, '5.68k'),
            (999990, '999.99k'),
            (999999, '1.00M'),
            (1000000, '1.00M'),
        ]
        for x, expected in data:
            self.assertEqual(expected, duviz.human_readable_count(x))

    def test_human_readable_byte_size(self):
        data = [
            (0, '0B'),
            (10, '10B'),
            (999, '999B'),
            (1000, '1.00KB'),
            (5432, '5.43KB'),
            (5678, '5.68KB'),
            (999990, '999.99KB'),
            (999999, '1.00MB'),
            (1000000, '1.00MB'),
        ]
        for x, expected in data:
            self.assertEqual(expected, duviz.human_readable_byte_size(x))

    def test_human_readable_byte_size_binary(self):
        data = [
            (0, '0B'),
            (10, '10B'),
            (999, '999B'),
            (1000, '1000B'),
            (1023, '1023B'),
            (1024, '1.00KiB'),
            (5432, '5.30KiB'),
            (1000000, '976.56KiB'),
            (1024 * 1024, '1.00MiB'),
        ]
        for x, expected in data:
            self.assertEqual(expected, duviz.human_readable_byte_size(x, True))


