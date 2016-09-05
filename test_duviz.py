# coding=utf-8
import unittest

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
import textwrap

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
            (1000000000, '1.00G'),
            (1000000000000, '1.00T'),
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
            (1024 * 1024 * 1024, '1.00GiB'),
            (1024 * 1024 * 1024 * 1024, '1.00TiB'),
        ]
        for x, expected in data:
            self.assertEqual(expected, duviz.human_readable_byte_size(x, True))


class PathSplitTest(unittest.TestCase):
    def test_path_split(self):
        data = [
            ('aa', ['aa']),
            ('aa/', ['aa']),
            ('aa/bB', ['aa', 'bB']),
            ('/aA/bB/c_c', ['/', 'aA', 'bB', 'c_c']),
            ('/aA/bB/c_c/', ['/', 'aA', 'bB', 'c_c']),
        ]
        for input_, expected in data:
            self.assertEqual(expected, duviz.path_split(input_))

    def test_path_split_with_base(self):
        data = [
            ('aa', 'a', ['aa']),
            ('aa/', '', ['aa']),
            ('a/b/c/d/', 'a', ['a', 'b', 'c', 'd']),
            ('a/b/c/d/', 'a/b', ['a/b', 'c', 'd']),
            ('a/b/c/d/', 'a/b/', ['a/b', 'c', 'd']),
            ('a/b/c/d/', 'a/b/c', ['a/b/c', 'd']),
            ('a/b/c/d/', 'a/b/c/d', ['a/b/c/d']),
            ('a/b/c/d', 'a/b/c/d/', ['a/b/c/d']),
            ('a/b/c/d', 'a/B', ['a', 'b', 'c', 'd']),
        ]
        for input_, base, expected in data:
            self.assertEqual(expected, duviz.path_split(input_, base))


class BuildDuTreeTest(unittest.TestCase):
    def test_build_du_tree1(self):
        dir_ = 'path/to'
        du_pipe = StringIO(textwrap.dedent('''\
            120     path/to/foo
            10      path/to/bar/a
            163     path/to/bar/b
            360     path/to/bar/c
            612     path/to/bar
            2       path/to/s p a c e s
            800     path/to
        '''))
        tree = duviz._build_du_tree(dir_, du_pipe, feedback=None)
        result = tree.block_display(width=40)
        expected = textwrap.dedent('''\
            ________________________________________
            [               path/to                ]
            [_______________819.20KB_______________]
            [            bar             ][foo ]
            [__________626.69KB__________][122.]
            [       c       ][  b   ]|
            [____368.64KB___][166.91]|
        ''')
        print(result)
        self.assertEqual(expected.split(), result.split())

    def test_build_du_tree2(self):
        dir_ = 'path/to'
        du_pipe = StringIO(textwrap.dedent('''\
            1       path/to/A
            1       path/to/b
            2       path/to/C
            4       path/to
        '''))
        tree = duviz._build_du_tree(dir_, du_pipe, feedback=None)
        result = tree.block_display(width=40)
        expected = textwrap.dedent('''\
            ________________________________________
            [               path/to                ]
            [________________4.10KB________________]
            [        C         ][   A    ][   b    ]
            [______2.05KB______][_1.02KB_][_1.02KB_]
        ''')
        self.assertEqual(expected.split(), result.split())


class BuildInodeCountTreeBsdLsTest(unittest.TestCase):
    """
    For BSD version of ls
    """

    def assertInputOuput(self, directory, ls_str, expected, width=40):
        ls_pipe = StringIO(ls_str)
        tree = duviz._build_inode_count_tree(directory, ls_pipe, feedback=None)
        result = tree.block_display(width=width, size_renderer=duviz.human_readable_count)
        self.assertEqual(expected.split('\n'), result.split('\n'))

    def test_build_inode_count_tree_simple(self):
        self.assertInputOuput(
            directory='path/to',
            ls_str=textwrap.dedent('''\
                222 .
                  1 ..
                333 file.txt
                444 anotherfile.txt
            '''),
            expected=textwrap.dedent('''\
                ________________________________________
                [               path/to                ]
                [__________________3___________________]''')
        )

    def test_build_inode_count_tree_with_hardlink(self):
        self.assertInputOuput(
            directory='path/to',
            ls_str=textwrap.dedent('''\
                222 .
                  1 ..
                333 file.txt
                444 anotherfile.txt
                333 hardlink.txt
            '''),
            expected=textwrap.dedent('''\
                ________________________________________
                [               path/to                ]
                [__________________3___________________]''')
        )

    def test_build_inode_count_tree_subdir(self):
        self.assertInputOuput(
            directory='path/to',
            ls_str=textwrap.dedent('''\
                222 .
                  1 ..
                333 file.txt
                444 directory
                555 anotherfile.txt

                path/to/directory:
                444 .
                222 ..
                666 devil.txt
                777 god.txt
            '''),
            expected=textwrap.dedent('''\
                ________________________________________
                [               path/to                ]
                [__________________6___________________]
                [ directory ]                           \n\
                [_____2_____]                           ''')
        )

    def test_build_inode_count_tree_various(self):
        self.assertInputOuput(
            directory='path/to',
            ls_str=textwrap.dedent('''\
                2395 .
                2393 ..
                2849 bar
                1166 barln
                2845 a.txt
                2846 b b b.txt
                2842 c.txt

                path/to/A:
                2849 .
                2395 ..
                2851 d.txt
                2852 e.txt

                path/to/B:
                1166 .
                2395 ..
                2852 bla.txt
                1174 zaza
            '''),
            expected=textwrap.dedent('''\
                ________________________________________
                [               path/to                ]
                [__________________9___________________]
                [  A   ][ B ]                           \n\
                [__2___][_1_]                           ''')
        )


class BuildInodeCountTreeGnuLsTest(BuildInodeCountTreeBsdLsTest):
    """
    For GNU version of ls
    """

    def assertInputOuput(self, directory, ls_str, expected, width=40):
        ls_str = directory + ':\n' + ls_str
        BuildInodeCountTreeBsdLsTest.assertInputOuput(self, directory, ls_str, expected, width)


if __name__ == '__main__':
    unittest.main()
