# coding: utf-8


import textwrap
import time
from io import StringIO
from typing import List

import pytest

from duviz import TreeRenderer, SIZE_FORMATTER_COUNT, SIZE_FORMATTER_BYTES, SIZE_FORMATTER_BYTES_BINARY, path_split, \
    SizeTree, AsciiDoubleLineBarRenderer, DuTree, InodeTree, get_progress_callback, AsciiSingleLineBarRenderer, \
    ColorDoubleLineBarRenderer, ColorSingleLineBarRenderer, Colorizer


def test_bar_one():
    assert 'y' == TreeRenderer().bar('x', 1, small='y')


def test_bar_zero():
    assert '' == TreeRenderer().bar('x', 0)


def test_bar_basic():
    assert '[--abcd--]' == TreeRenderer().bar('abcd', 10)


def test_bar_left_and_right():
    assert '<<--abcd--**' == TreeRenderer().bar('abcd', 12, left='<<', right='**')


def test_bar_fill():
    assert '[++abcd++]' == TreeRenderer().bar('abcd', 10, fill='+')


def test_bar_unicode():
    assert '[++åßc∂++]' == TreeRenderer().bar('åßc∂', 10, fill='+')


def test_bar_unicode2():
    label = b'\xc3\xb8o\xcc\x82o\xcc\x88o\xcc\x81a\xcc\x8a'.decode('utf8')
    assert '[+øôöóå+]' == TreeRenderer().bar(label, 9, fill='+')


@pytest.mark.parametrize(
    "expected",
    [
        '',
        '|',
        '[]',
        '[f]',
        '[fo]',
        '[foo]',
        '[_foo]',
        '[_foo_]',
        '[_foo_-]',
        '[-_foo_-]',
        '[-_foo_--]',
        '[--_foo_--]',
        '[--_foo_---]',
        '[---_foo_---]',
    ]
)
def test_bar_padding(expected):
    assert expected == TreeRenderer().bar('foo', width=len(expected), fill="-", label_padding='_')


@pytest.mark.parametrize(
    "expected",
    [
        '',
        'f',
        'fo',
        'foo',
        '_foo',
        '_foo_',
        '_foo_-',
        '-_foo_-',
    ]
)
def test_bar_no_left_right(expected):
    assert expected == TreeRenderer().bar(
        'foo', width=len(expected),
        left='', right='', small='*', fill="-", label_padding='_',
    )


@pytest.mark.parametrize(
    "expected",
    [
        '',
        '=',
        '==',
        '===',
        '[[]]',
        '[[f]]',
        '[[fo]]',
        '[[foo]]',
        '[[_foo]]',
        '[[_foo_]]',
        '[[_foo_-]]',
        '[[-_foo_-]]',
    ]
)
def test_bar_small(expected):
    assert expected == TreeRenderer().bar(
        'foo', width=len(expected),
        left='[[', right=']]', small='=', fill="-", label_padding='_',
    )


@pytest.mark.parametrize(
    "expected",
    [
        '',
        '#',
        '#=',
        '#=+',
        '#=+#',
        '#=+#=',
        '[<[]>]',
        '[<[f]>]',
    ]
)
def test_bar_small_multiple(expected):
    assert expected == TreeRenderer().bar(
        'f', width=len(expected),
        left='[<[', right=']>]', small='#=+', fill="-", label_padding='_',
    )


TREE123 = SizeTree("foo", 123)

TREE60 = SizeTree("foo", 60, children={
    "bar": SizeTree("bar", 40, children={
        "xe": SizeTree("xe", 20),
        "vo": SizeTree("vo", 10),
    }),
    "baz": SizeTree("baz", 20, children={
        "pu": SizeTree("pu", 10),
    }),
})

TREE80 = SizeTree("foo", 80, children={
    "vy": SizeTree("vy", 50, children={
        "a": SizeTree("a", 20),
        "b": SizeTree("b", 9),
        "c": SizeTree("c", 10),
        "d": SizeTree("d", 11),
    }),
    "dy": SizeTree("dy", 11, children={
        "py": SizeTree("py", 11),
    }),
    "do": SizeTree("do", 9, children={
        "po": SizeTree("po", 9),
    }),
    "da": SizeTree("da", 10, ),
})


@pytest.mark.parametrize(
    ["tree", "width", "expected"],
    [
        (TREE123, 4, [
            "____",
            "[fo]",
            "[12]"
        ]),
        (TREE123, 5, [
            "_____",
            "[foo]",
            "[123]"
        ]),
        (TREE123, 10, [
            "__________",
            "[  foo   ]",
            "[__123___]"
        ]),
        (TREE123, 20, [
            "____________________",
            "[       foo        ]",
            "[_______123________]"
        ]),
        (TREE60, 18, [
            "__________________",
            "[      foo       ]",
            "[_______60_______]",
            "[   bar    ][baz ]",
            "[____40____][_20_]",
            "[ xe ][v]   [p]   ",
            "[_20_][1]   [1]   ",
        ]),
        (TREE60, 36, [
            "____________________________________",
            "[               foo                ]",
            "[________________60________________]",
            "[         bar          ][   baz    ]",
            "[__________40__________][____20____]",
            "[    xe    ][ vo ]      [ pu ]      ",
            "[____20____][_10_]      [_10_]      ",
        ]),
        (TREE60, 60, [
            "____________________________________________________________",
            "[                           foo                            ]",
            "[____________________________60____________________________]",
            "[                 bar                  ][       baz        ]",
            "[__________________40__________________][________20________]",
            "[        xe        ][   vo   ]          [   pu   ]          ",
            "[________20________][___10___]          [___10___]          ",
        ]),
    ]
)
def test_ascii_double_line_bar_renderer(tree, width, expected):
    assert AsciiDoubleLineBarRenderer().render(tree, width=width) == expected


@pytest.mark.parametrize(
    ["tree", "width", "expected"],
    [
        (TREE123, 5, ["[foo]"]),
        (TREE123, 10, ["[foo: 123]"]),
        (TREE123, 20, ["[.... foo: 123 ....]"]),
        (TREE60, 18, [
            "[... foo: 60 ....]",
            "[ bar: 40 .][baz:]",
            "[xe: ][v]   [p]   ",

        ]),
        (TREE60, 36, [
            "[............ foo: 60 .............]",
            "[...... bar: 40 .......][ baz: 20 .]",
            "[. xe: 20 .][vo: ]      [pu: ]      ",

        ]),
        (TREE60, 60, [
            "[........................ foo: 60 .........................]",
            "[.............. bar: 40 ...............][.... baz: 20 .....]",
            "[..... xe: 20 .....][ vo: 10 ]          [ pu: 10 ]          ",
        ]
         )
    ]
)
def test_ascii_single_line_bar_renderer(tree, width, expected):
    assert AsciiSingleLineBarRenderer().render(tree, width=width) == expected


def test_colorize_rgy():
    clz = Colorizer()
    marked = "_".join(clz.wrap(t) for t in ["AAA", "BBB", "CCC", "DDD", "EEE"])
    colorize = clz.get_colorize_rgy()
    expected = "\x1b[41;97mAAA\x1b[0m_\x1b[42;30mBBB\x1b[0m_\x1b[43;30mCCC\x1b[0m" \
               "_\x1b[41;97mDDD\x1b[0m_\x1b[42;30mEEE\x1b[0m"
    assert colorize(marked) == expected


def test_colorize_bmc():
    clz = Colorizer()
    marked = "_".join(clz.wrap(t) for t in ["AAA", "BBB", "CCC", "DDD", "EEE"])
    colorize = clz.get_colorize_bmc()
    expected = "\x1b[44;97mAAA\x1b[0m_\x1b[45;30mBBB\x1b[0m_\x1b[46;30mCCC\x1b[0m" \
               "_\x1b[44;97mDDD\x1b[0m_\x1b[45;30mEEE\x1b[0m"
    assert colorize(marked) == expected


@pytest.mark.parametrize(
    ["tree", "width", "expected"],
    [
        (TREE123, 5, [
            "\x1b[41;97m foo \x1b[0m",
            "\x1b[41;97m 123 \x1b[0m",
        ]),
        (TREE123, 10, [
            "\x1b[41;97m   foo    \x1b[0m",
            "\x1b[41;97m   123    \x1b[0m"
        ]),
        (TREE80, 40, [
            "\x1b[41;97m                  foo                   \x1b[0m",
            "\x1b[41;97m                   80                   \x1b[0m",
            "\x1b[44;97m            vy           \x1b[0m\x1b"
            + "[45;30m  dy \x1b[0m\x1b[46;30m  da \x1b[0m\x1b[44;97m  do \x1b[0m",
            "\x1b[44;97m            50           \x1b[0m\x1b"
            + "[45;30m  11 \x1b[0m\x1b[46;30m  10 \x1b[0m\x1b[44;97m  9  \x1b[0m",
            "\x1b[42;30m    a     \x1b[0m\x1b[43;30m  d  \x1b[0m\x1b[41;97m  c  \x1b[0m\x1b[42;30m  b  \x1b[0m"
            + "\x1b[43;30m  py \x1b[0m     \x1b[41;97m  po \x1b[0m",
            "\x1b[42;30m    20    \x1b[0m\x1b[43;30m  11 \x1b[0m\x1b[41;97m  10 \x1b[0m\x1b[42;30m  9  \x1b[0m"
            + "\x1b[43;30m  11 \x1b[0m     \x1b[41;97m  9  \x1b[0m"
        ])
    ]
)
def test_color_double_line_bar_renderer(tree, width, expected):
    assert ColorDoubleLineBarRenderer().render(tree, width=width) == expected


@pytest.mark.parametrize(
    ["tree", "width", "expected"],
    [
        (TREE123, 5, ["\x1b[41;97mfoo: \x1b[0m"]),
        (TREE123, 10, ["\x1b[41;97m foo: 123 \x1b[0m"]),
        (TREE80, 40, [
            "\x1b[41;97m                foo: 80                 \x1b[0m",
            "\x1b[44;97m          vy: 50         \x1b[0m"
            + "\x1b[45;30mdy: 1\x1b[0m\x1b[46;30mda: 1\x1b[0m\x1b[44;97mdo: 9\x1b[0m",
            "\x1b[42;30m  a: 20   \x1b[0m\x1b[43;30md: 11\x1b[0m\x1b[41;97mc: 10\x1b[0m\x1b[42;30m b: 9\x1b[0m"
            + "\x1b[43;30mpy: 1\x1b[0m     \x1b[41;97mpo: 9\x1b[0m",
        ])
    ]
)
def test_color_single_line_bar_renderer(tree, width, expected):
    assert ColorSingleLineBarRenderer().render(tree, width=width) == expected


@pytest.mark.parametrize(
    ["x", "expected"],
    [
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
)
def test_formatter_count(x, expected):
    assert expected == SIZE_FORMATTER_COUNT.format(x)


@pytest.mark.parametrize(
    ["x", "expected"],
    [
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
)
def test_formatter_bytes(x, expected):
    assert expected == SIZE_FORMATTER_BYTES.format(x)


@pytest.mark.parametrize(
    ["x", "expected"],
    [
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
)
def test_formatter_bytes_binary(x, expected):
    assert expected == SIZE_FORMATTER_BYTES_BINARY.format(x)


@pytest.mark.parametrize(
    ["path", "expected"],
    [
        ('aa', ['aa']),
        ('aa/', ['aa']),
        ('aa/bB', ['aa', 'bB']),
        ('/aA/bB/c_c', ['/', 'aA', 'bB', 'c_c']),
        ('/aA/bB/c_c/', ['/', 'aA', 'bB', 'c_c']),
    ]
)
def test_path_split(path, expected):
    assert expected == path_split(path)


@pytest.mark.parametrize(
    ["path", "base", "expected"],
    [
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
)
def test_path_split_with_base(path, base, expected):
    assert expected == path_split(path, base)


def _dedent(s: str) -> str:
    """Helper to unindent strings for quick and easy text listings"""
    return textwrap.dedent(s.lstrip("\n").rstrip(" "))


def _dedent_and_split(s: str) -> List[str]:
    return _dedent(s).strip("\n").split("\n")


@pytest.mark.parametrize(["input", "output"], [
    ("foo", "foo"),
    ("   foo\n   bar", "foo\nbar"),
    ("\n   foo\n   bar", "foo\nbar"),
    ("\n   foo\n   bar\n", "foo\nbar\n"),
    ("\n   foo\n   bar\n    ", "foo\nbar\n"),
    ("\n   foo\n     bar\n    ", "foo\n  bar\n"),
    ("\n     foo\n   bar\n    ", "  foo\nbar\n"),
])
def test_dedent(input, output):
    assert _dedent(input) == output


@pytest.mark.parametrize(["input", "output"], [
    ("foo", ["foo"]),
    ("   foo\n   bar", ["foo", "bar"]),
    ("\n   foo\n   bar", ["foo", "bar"]),
    ("\n   foo\n   bar\n", ["foo", "bar"]),
    ("\n   foo\n   bar\n    ", ["foo", "bar"]),
    ("\n   foo\n     bar\n    ", ["foo", "  bar"]),
    ("\n     foo\n   bar\n    ", ["  foo", "bar"]),
])
def test_dedent_and_split(input, output):
    assert _dedent_and_split(input) == output


def test_build_du_tree1():
    directory = 'path/to'
    du_listing = _dedent_and_split('''
        120     path/to/foo
        10      path/to/bar/a
        163     path/to/bar/b
        360     path/to/bar/c
        612     path/to/bar
        2       path/to/s p a c e s
        800     path/to
    ''')
    tree = DuTree.from_du_listing(directory, du_listing)
    renderer = AsciiDoubleLineBarRenderer(size_formatter=SIZE_FORMATTER_BYTES)
    result = renderer.render(tree, width=40)
    expected = _dedent_and_split('''
        ________________________________________
        [               path/to                ]
        [_______________819.20KB_______________]
        [            bar             ][foo ]    \n\
        [__________626.69KB__________][122.]    \n\
        [       c       ][  b   ]|              \n\
        [____368.64KB___][166.91]|              \n\
    ''')
    assert result == expected


def test_build_du_tree2():
    directory = 'path/to'
    du_listing = _dedent_and_split('''
        1       path/to/A
        1       path/to/b
        2       path/to/C
        4       path/to
    ''')
    tree = DuTree.from_du_listing(directory, du_listing)
    renderer = AsciiDoubleLineBarRenderer(size_formatter=SIZE_FORMATTER_BYTES)
    result = renderer.render(tree, width=40)
    expected = _dedent_and_split('''
        ________________________________________
        [               path/to                ]
        [________________4.10KB________________]
        [        C         ][   b    ][   A    ]
        [______2.05KB______][_1.02KB_][_1.02KB_]
    ''')
    assert result == expected


def _check_ls_listing_render(ls_listing: str, expected: str, directory='path/to', width=40):
    """Helper to parse a ls listing, render as ASCII bars and check result"""
    tree = InodeTree.from_ls_listing(root=directory, ls_listing=_dedent(ls_listing))
    result = AsciiDoubleLineBarRenderer().render(tree, width=width)
    assert result == _dedent_and_split(expected)


def test_inode_tree_bsd_ls_simple():
    _check_ls_listing_render(
        ls_listing="""
            222 .
              1 ..
            333 file.txt
            444 anotherfile.txt
        """,
        expected="""
            ________________________________________
            [               path/to                ]
            [__________________3___________________]
        """
    )


def test_inode_tree_bsd_ls_with_hardlink():
    _check_ls_listing_render(
        ls_listing="""
            222 .
              1 ..
            333 file.txt
            444 anotherfile.txt
            333 hardlink.txt
        """,
        expected="""
            ________________________________________
            [               path/to                ]
            [__________________3___________________]
        """
    )


def test_inode_tree_bsd_ls_subdir():
    _check_ls_listing_render(
        ls_listing="""
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
        """,
        expected="""
            ________________________________________
            [               path/to                ]
            [__________________6___________________]
            [ directory ]                           \n\
            [_____2_____]                           \n\
        """
    )


def test_inode_tree_bsd_ls_various():
    _check_ls_listing_render(
        ls_listing="""
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
        """,
        expected="""
            ________________________________________
            [               path/to                ]
            [__________________9___________________]
            [  A   ][ B ]                           \n\
            [__2___][_1_]                           \n\
        """
    )


def test_inode_tree_gnu_ls_simple():
    _check_ls_listing_render(
        ls_listing="""
            path/to:
            222 .
              1 ..
            333 file.txt
            444 anotherfile.txt
        """,
        expected="""
            ________________________________________
            [               path/to                ]
            [__________________3___________________]
        """
    )


def test_inode_tree_gnu_ls_various():
    _check_ls_listing_render(
        ls_listing="""
            path/to:
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
        """,
        expected="""
            ________________________________________
            [               path/to                ]
            [__________________9___________________]
            [  A   ][ B ]                           \n\
            [__2___][_1_]                           \n\
        """
    )


def test_get_progress_callback():
    stream = StringIO()
    progress = get_progress_callback(stream=stream, interval=0.1, terminal_width=10)
    for i in range(4):
        progress('path %d' % i)
        time.sleep(0.05)

    assert stream.getvalue() == 'path 0    \rpath 2    \r'
