#!/usr/bin/env python

"""
Command line tool for visualization of the disk space usage of a directory
and its subdirectories.

Copyright: 2009-2019 Stefaan Lippens
License: MIT
Website: http://soxofaan.github.io/duviz/
"""

import contextlib
import itertools
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from typing import List


# TODO: catch absence/failure of du/ls subprocesses
# TODO: how to handle unreadable subdirs in du/ls?
# TODO: option to sort alphabetically (instead of on size)


def path_split(path, base=''):
    """
    Split a file system path in a list of path components (as a recursive os.path.split()),
    optionally only up to a given base path.
    """
    if base.endswith(os.path.sep):
        base = base.rstrip(os.path.sep)
    items = []
    while True:
        if path == base:
            items.insert(0, path)
            break
        path, tail = os.path.split(path)
        if tail != '':
            items.insert(0, tail)
        if path == '':
            break
        if path == '/':
            items.insert(0, path)
            break
    return items


class SubprocessException(RuntimeError):
    pass


class SizeTree:
    """
    Base class for a tree of nodes where each node has a size and zero or more sub-nodes.
    """

    def __init__(self, name, size=0, children=None):
        self.name = name
        self.size = size
        self.children = children or {}

    @classmethod
    def from_path_size_pairs(cls, pairs, root='/'):
        """
        Build SizeTree from given (path, size) pairs
        """
        tree = cls(name=root)
        for path, size in pairs:
            cursor = tree
            for component in path:
                if component not in cursor.children:
                    # TODO: avoid redundancy of name: as key in children dict and as name
                    cursor.children[component] = cls(name=component)
                cursor = cursor.children[component]
            cursor.size = size
        return tree

    def __lt__(self, other):
        # We only implement rich comparison method __lt__ so make sorting work.
        return (self.size, self.name) < (other.size, other.name)

    def _recalculate_own_sizes_to_total_sizes(self):
        """
        If provided sizes are just own sizes and sizes of children still have to be included
        """
        self.size = self.size + sum(c._recalculate_own_sizes_to_total_sizes() for c in self.children.values())
        return self.size


class DuTree(SizeTree):
    """
    Size tree from `du` (disk usage) listings
    """

    _du_regex = re.compile(r'([0-9]*)\s*(.*)')

    @classmethod
    def from_du(cls, root, one_filesystem=False, dereference=False, progress_report=None):
        # Measure size in 1024 byte blocks. The GNU-du option -b enables counting
        # in bytes directly, but it is not available in BSD-du.
        command = ['du', '-k']
        # Handling of symbolic links.
        if one_filesystem:
            command.append('-x')
        if dereference:
            command.append('-L')
        command.append(root)
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE)
        except OSError:
            raise SubprocessException('Failed to launch "du" utility subprocess. Is it installed and in your PATH?')

        with contextlib.closing(process.stdout):
            return cls.from_du_listing(
                root=root,
                du_listing=(l.decode('utf-8') for l in process.stdout),
                progress_report=progress_report
            )

    @classmethod
    def from_du_listing(cls, root, du_listing, progress_report=None):
        def pairs(lines):
            for line in lines:
                kb, path = cls._du_regex.match(line).group(1, 2)
                if progress_report:
                    progress_report(path)
                yield path_split(path, root)[1:], 1024 * int(kb)

        return cls.from_path_size_pairs(root=root, pairs=pairs(du_listing))


class InodeTree(SizeTree):

    @classmethod
    def from_ls(cls, root, progress_report=None):
        command = ['ls', '-aiR', root]
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE)
        except OSError:
            raise SubprocessException('Failed to launch "ls" subprocess.')

        with contextlib.closing(process.stdout):
            return cls.from_ls_listing(
                root=root,
                ls_listing=process.stdout.read().decode('utf-8'),
                progress_report=progress_report
            )

    @classmethod
    def from_ls_listing(cls, root, ls_listing, progress_report=None):

        def pairs(listing):
            all_inodes = set()

            # Process data per directory block (separated by two newlines)
            blocks = listing.rstrip('\n').split('\n\n')
            for i, dir_ls in enumerate(blocks):
                items = dir_ls.split('\n')

                # Get current path in directory tree
                if i == 0 and not items[0].endswith(':'):
                    # BSD compatibility: in first block the root directory can be omitted
                    path = root
                else:
                    path = items.pop(0).rstrip(':')

                # Collect inodes for current directory
                count = 0
                for item in items:
                    inode, name = item.lstrip().split(' ', 1)
                    # Skip parent entry
                    if name == '..':
                        continue
                    # Get and process inode
                    inode = int(inode)
                    if inode not in all_inodes:
                        count += 1
                    all_inodes.add(inode)

                if progress_report:
                    progress_report(path)
                yield path_split(path, root)[1:], count

        tree = cls.from_path_size_pairs(pairs=pairs(ls_listing), root=root)
        tree._recalculate_own_sizes_to_total_sizes()
        return tree


class SizeFormatter:
    """Render a (byte) count in compact human readable way: 12, 34k, 56M, ..."""

    def __init__(self, base: int, formats: List[str]):
        self.base = base
        self.formats = formats

    def format(self, size: int) -> str:
        for f in self.formats[:-1]:
            if round(size, 2) < self.base:
                return f % size
            size = float(size) / self.base
        return self.formats[-1] % size


SIZE_FORMATTER_COUNT = SizeFormatter(1000, ['%d', '%.2fk', '%.2fM', '%.2fG', '%.2fT'])
SIZE_FORMATTER_BYTES = SizeFormatter(1000, ['%dB', '%.2fKB', '%.2fMB', '%.2fGB', '%.2fTB'])
SIZE_FORMATTER_BYTES_BINARY = SizeFormatter(1024, ['%dB', '%.2fKiB', '%.2fMiB', '%.2fGiB', '%.2fTiB'])


class TreeRenderer:
    """Base class for SizeTree renderers"""

    def __init__(self, max_depth: int = 5, size_formatter: SizeFormatter = SIZE_FORMATTER_COUNT):
        self.max_depth = max_depth
        self._size_formatter = size_formatter

    def render(self, tree: SizeTree, width: int) -> List[str]:
        raise NotImplementedError

    def bar(self, label: str, width: int, fill='-', left='[', right=']', small='|', label_padding='') -> str:
        """
        Render a label as string of certain width with given left, right part and fill.

        @param label the label to be rendered (will be clipped if too long).
        @param width the desired total width
        @param fill the fill character to fill empty space
        @param left the symbol to use at the left of the bar
        @param right the symbol to use at the right of the bar
        @param small the character to use when the bar is too small
        @param label_padding additional padding for the label

        @return rendered string
        """
        inner_width = width - len(left) - len(right)
        if inner_width >= 0:
            # Normalize unicode so that unicode code point count corresponds to character count as much as possible
            label = unicodedata.normalize('NFC', label)
            if len(label) < inner_width:
                label = label_padding + label + label_padding
            b = left + label[:inner_width].center(inner_width, fill) + right
        else:
            b = (small * width)[:width]
        return b


class AsciiDoubleLineBarRenderer(TreeRenderer):
    """
    Render a SizeTree with two line ASCII bars,
    containing name and size of each node.

    Example:

        ________________________________________
        [                 foo                  ]
        [_______________49.15KB________________]
        [          bar           ][    baz     ]
        [________32.77KB_________][__16.38KB___]
    """

    _top_line_fill = '_'

    def render(self, tree: SizeTree, width: int) -> List[str]:
        lines = []
        if self._top_line_fill:
            lines.append(self._top_line_fill * width)
        return lines + self._render(tree, width, self.max_depth)

    def render_node(self, node: SizeTree, width: int) -> List[str]:
        """Render a single node"""
        return [
            self.bar(
                label=node.name,
                width=width, fill=' ', left='[', right=']', small='|'
            ),
            self.bar(
                label=self._size_formatter.format(node.size),
                width=width, fill='_', left='[', right=']', small='|'
            )
        ]

    def _render(self, tree: SizeTree, width: int, depth: int) -> List[str]:
        lines = []
        if width < 1 or depth < 0:
            return lines

        # Render current dir.
        lines.extend(self.render_node(node=tree, width=width))

        # Render children.
        # TODO option to sort alphabetically
        children = sorted(tree.children.values(), reverse=True)
        if children:
            # Render each child as a subtree, which is a list of lines.
            subtrees = []
            cumulative_size = 0
            last_col = 0
            for child in children:
                cumulative_size += child.size
                curr_col = int(float(width * cumulative_size) / tree.size)
                subtrees.append(self._render(child, curr_col - last_col, depth - 1))
                last_col = curr_col
            # Assemble blocks.
            height = max(len(t) for t in subtrees)
            for i in range(height):
                line = ''
                for subtree in subtrees:
                    if i < len(subtree):
                        line += subtree[i]
                    elif subtree:
                        line += ' ' * self._str_len(subtree[0])
                lines.append(line + ' ' * (width - self._str_len(line)))

        return lines

    def _str_len(self, b: str) -> int:
        return len(b)


class AsciiSingleLineBarRenderer(AsciiDoubleLineBarRenderer):
    """
    Render a SizeTree with one-line ASCII bars.

    Example:

        [........... foo/: 61.44KB ............]
        [.... bar: 36.86KB ....][baz: 20.48K]
    """
    _top_line_fill = None

    def render_node(self, node: SizeTree, width: int) -> List[str]:
        return [
            self.bar(
                label="{n}: {s}".format(n=node.name, s=self._size_formatter.format(node.size)),
                width=width, fill='.', left='[', right=']', small='|', label_padding=' '
            )
        ]


class Colorizer:
    # Markers to start and end a color
    _START = '\x01'
    _END = '\x02'

    # Red, Green, Yellow
    COLOR_CYCLE_RGY = ['\x1b[41;97m', '\x1b[42;30m', '\x1b[43;30m']

    # Blue, Magenta, Cyan
    COLOR_CYCLE_BMC = ['\x1b[44;97m', '\x1b[45;30m', '\x1b[46;30m']

    COLOR_RESET = '\x1b[0m'

    def wrap(self, s: str) -> str:
        """Wrap given string in colorize markers"""
        return self._START + s + self._END

    def str_len(self, b: str) -> int:
        return len(b.replace(self._START, '').replace(self._END, ''))

    def get_colorize(self, colors: List[str]):
        """Construct function that replaces markers with color codes (cycling through given color codes)"""
        color_cycle = itertools.cycle(colors)

        def colorize(line: str) -> str:
            line = re.sub(self._START, lambda m: next(color_cycle), line)
            line = re.sub(self._END, self.COLOR_RESET, line)
            return line

        return colorize

    def get_colorize_rgy(self):
        return self.get_colorize(self.COLOR_CYCLE_RGY)

    def get_colorize_bmc(self):
        return self.get_colorize(self.COLOR_CYCLE_BMC)


class ColorDoubleLineBarRenderer(AsciiDoubleLineBarRenderer):
    """
    Render a SizeTree with two line ANSI color bars,
    """

    _top_line_fill = None
    _colorizer = Colorizer()

    def render_node(self, node: SizeTree, width: int) -> List[str]:
        return [
            self._colorizer.wrap(self.bar(
                label=node.name,
                width=width, fill=' ', left='', right='', small=' ',
            )),
            self._colorizer.wrap(self.bar(
                label=self._size_formatter.format(node.size),
                width=width, fill=' ', left='', right='', small=' ',
            )),
        ]

    def render(self, tree: SizeTree, width: int) -> List[str]:
        lines = super().render(tree=tree, width=width)
        colorize_cycle = itertools.cycle([
            self._colorizer.get_colorize_rgy(),
            self._colorizer.get_colorize_rgy(),
            self._colorizer.get_colorize_bmc(),
            self._colorizer.get_colorize_bmc(),
        ])
        return [colorize(line) for (line, colorize) in zip(lines, colorize_cycle)]

    def _str_len(self, b: str) -> int:
        return self._colorizer.str_len(b)


class ColorSingleLineBarRenderer(AsciiSingleLineBarRenderer):
    """
    Render a SizeTree with one line ANSI color bars,
    """

    _top_line_fill = None
    _colorizer = Colorizer()

    def render_node(self, node: SizeTree, width: int) -> List[str]:
        return [
            self._colorizer.wrap(self.bar(
                label="{n}: {s}".format(n=node.name, s=self._size_formatter.format(node.size)),
                width=width, fill=' ', left='', right='', small=' ',
            ))
        ]

    def render(self, tree: SizeTree, width: int) -> List[str]:
        lines = super().render(tree=tree, width=width)
        colorize_cycle = itertools.cycle([
            self._colorizer.get_colorize_rgy(),
            self._colorizer.get_colorize_bmc(),
        ])
        return [colorize(line) for (line, colorize) in zip(lines, colorize_cycle)]

    def _str_len(self, b: str) -> int:
        return self._colorizer.str_len(b)


def get_progress_reporter(max_interval=1, terminal_width=80, write=sys.stdout.write, time=time.time):
    """
    Create a progress reporting function that only actually prints in intervals
    """
    next_time = 0
    # Start printing frequently.
    interval = 0

    def progress(info: str):
        nonlocal next_time, interval
        if time() > next_time:
            write(info.ljust(terminal_width)[:terminal_width] + '\r')
            next_time = time() + interval
            # Converge to max interval.
            interval = 0.9 * interval + 0.1 * max_interval

    return progress


def main():
    terminal_width = shutil.get_terminal_size().columns

    # Handle commandline interface.
    # TODO switch to argparse?
    import optparse
    cliparser = optparse.OptionParser(
        """usage: %prog [options] [DIRS]
        %prog gives a graphic representation of the disk space
        usage of the folder trees under DIRS.""",
        version='%prog 3.1.0')
    cliparser.add_option(
        '-w', '--width',
        action='store', type='int', dest='display_width', default=terminal_width,
        help='total width of all bars', metavar='WIDTH'
    )
    cliparser.add_option(
        '-x', '--one-file-system',
        action='store_true', dest='onefilesystem', default=False,
        help='skip directories on different filesystems'
    )
    cliparser.add_option(
        '-L', '--dereference',
        action='store_true', dest='dereference', default=False,
        help='dereference all symbolic links'
    )
    cliparser.add_option(
        '--max-depth',
        action='store', type='int', dest='max_depth', default=5,
        help='maximum recursion depth', metavar='N'
    )
    cliparser.add_option(
        '-i', '--inodes',
        action='store_true', dest='inode_count', default=False,
        help='count inodes instead of file size'
    )
    cliparser.add_option(
        '--no-progress',
        action='store_false', dest='show_progress', default=True,
        help='disable progress reporting'
    )
    cliparser.add_option(
        '-1', '--one-line',
        action='store_true', dest='one_line', default=False,
        help='Show one line bars instead of two line bars'
    )
    cliparser.add_option(
        '-c', '--color',
        action='store_true', dest='color', default=False,
        help='Use colors to render bars (instead of ASCII art)'
    )

    (opts, args) = cliparser.parse_args()

    # Make sure we have a valid list of paths
    if args:
        paths = []
        for path in args:
            if os.path.exists(path):
                paths.append(path)
            else:
                sys.stderr.write('Warning: not a valid path: "%s"\n' % path)
    else:
        # Do current dir if no dirs are given.
        paths = ['.']

    if opts.show_progress:
        progress_report = get_progress_reporter(terminal_width=opts.display_width)
    else:
        progress_report = None

    for directory in paths:
        if opts.inode_count:
            tree = InodeTree.from_ls(root=directory, progress_report=progress_report)
            size_formatter = SIZE_FORMATTER_COUNT
        else:
            tree = DuTree.from_du(
                root=directory,
                one_filesystem=opts.onefilesystem, dereference=opts.dereference,
                progress_report=progress_report,
            )
            size_formatter = SIZE_FORMATTER_BYTES

        if opts.one_line:
            if opts.color:
                renderer = ColorSingleLineBarRenderer(max_depth=opts.max_depth, size_formatter=size_formatter)
            else:
                renderer = AsciiSingleLineBarRenderer(max_depth=opts.max_depth, size_formatter=size_formatter)
        else:
            if opts.color:
                renderer = ColorDoubleLineBarRenderer(max_depth=opts.max_depth, size_formatter=size_formatter)
            else:
                renderer = AsciiDoubleLineBarRenderer(max_depth=opts.max_depth, size_formatter=size_formatter)

        print("\n".join(renderer.render(tree, width=opts.display_width)))


if __name__ == '__main__':
    main()
