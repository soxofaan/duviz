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
from typing import List, Optional, Dict, Iterable, Tuple, Callable, Iterator, Any


# TODO: catch absence/failure of du/ls subprocesses
# TODO: how to handle unreadable subdirs in du/ls?
# TODO: option to sort alphabetically (instead of on size)


def path_split(path: str, base: str = "") -> List[str]:
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


def truncate(s: str, maxlen: int, truncation_indicator: str = "..."):
    """
    Truncate the string s to fit in maxlen chars including a truncation_indicator 
    placed at the end.
    """
    if len(s) <= maxlen:
        return s
    return s[: maxlen - len(truncation_indicator)] + truncation_indicator

class SubprocessException(RuntimeError):
    pass


class SizeTree:
    """
    Base class for a tree of nodes where each node has a size and zero or more sub-nodes.
    """

    __slots__ = ["name", "size", "children"]

    def __init__(
        self, name: str, size: int = 0, children: Optional[Dict[str, "SizeTree"]] = None
    ):
        self.name = name
        self.size = size
        self.children = children or {}

    @classmethod
    def from_path_size_pairs(
        cls, pairs: Iterable[Tuple[List[str], int]], root: str = "/"
    ) -> "SizeTree":
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

    def __lt__(self, other: "SizeTree") -> bool:
        # We only implement rich comparison method __lt__ so make sorting work.
        return (self.size, self.name) < (other.size, other.name)

    def _recalculate_own_sizes_to_total_sizes(self) -> int:
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
    def from_du(
        cls,
        root: str,
        one_filesystem: bool = False,
        dereference: bool = False,
        progress_report: Callable[[str], None] = None,
    ) -> "DuTree":
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
    def from_du_listing(
        cls,
        root: str,
        du_listing: Iterable[str],
        progress_report: Optional[Callable[[str], None]] = None,
    ) -> "DuTree":
        def pairs(lines: Iterable[str]) -> Iterator[Tuple[List[str], int]]:
            for line in lines:
                kb, path = cls._du_regex.match(line).group(1, 2)
                if progress_report:
                    progress_report(path)
                yield path_split(path, root)[1:], 1024 * int(kb)

        return cls.from_path_size_pairs(root=root, pairs=pairs(du_listing))


class InodeTree(SizeTree):

    @classmethod
    def from_ls(
        cls, root: str, progress_report: Callable[[str], None] = None
    ) -> "InodeTree":
        command = ["ls", "-aiR", root]
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
    def from_ls_listing(
        cls, root: str, ls_listing: str, progress_report: Callable[[str], None] = None
    ) -> "InodeTree":
        def pairs(listing: str) -> Iterator[Tuple[List[str], int]]:
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
    """Render a (byte) count in compact human-readable way: 12, 34k, 56M, ..."""

    __slots__ = ["base", "formats"]

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

    def bar(
        self,
        label: str,
        width: int,
        fill: str = "-",
        left: str = "[",
        right: str = "]",
        small: str = "|",
        label_padding: str = "",
    ) -> str:
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


class ColumnsRenderer(TreeRenderer):
    """
    Render a SizeTree with vertical columns.
    """

    def __init__(
        self,
        height: int,
        max_depth: int = 5,
        size_formatter: SizeFormatter = SIZE_FORMATTER_COUNT,
        color_mode: bool = False,
    ):
        super().__init__(max_depth, size_formatter)
        self.height = height
        self.color_mode = color_mode
        if color_mode:
            self.colorizers = []
            c = Colorizer()
            # We use reverse order so that the root is always the same color regardless of the depth
            for i in reversed(range(max_depth + 1)):
                cycle = itertools.cycle(
                    c._COLOR_CYCLE_BMC if i % 2 == 0 else c._COLOR_CYCLE_RGY
                )
                self.colorizers.append(cycle)

    def render(self, tree: SizeTree, width: int) -> List[str]:
        return self._render(
            tree, width // (self.max_depth + 1), self.height, self.max_depth, topmost=True, leftmost=True
        )

    def render_node(
        self,
        node: Optional[SizeTree],
        width: int,
        height: int,
        depth: int,
        topmost: bool,
        leftmost: bool,
    ) -> List[str]:
        """Render a single node"""
        if self.color_mode:
            color = next(self.colorizers[depth])
            prefix = color
            suffix = Colorizer._COLOR_RESET
            left = ""
            right = ""
            top_border = " "
            bottom_border = " "
            horiz_padding = 1
        else:
            prefix = ""
            suffix = ""
            left = "|" if leftmost else ""
            right = "|"
            top_border = "~" if topmost else " "
            bottom_border = "_"
            horiz_padding = 2
        if node:
            text_lines = min(2, height)
            size_str = self._size_formatter.format(node.size)
            if text_lines == 0:
                label_line_arr = []
            elif text_lines == 1:
                name_size_separator = " "
                name_maxlen = (
                    width - len(size_str) - len(left) - len(right) - len(name_size_separator) - 2 * horiz_padding
                )
                label_line_arr = [
                    truncate(node.name, name_maxlen) + name_size_separator + size_str
                ]
            elif text_lines == 2:
                name_maxlen = width - len(left) - len(right) - 2 * horiz_padding
                label_line_arr = [
                    truncate(node.name, name_maxlen),
                    size_str,
                ]
            else:
                raise ValueError(text_lines)
        else:
            # When called without a specific node, it means that we need to
            # render a block to collectively represent multiple directories that
            # are not large enough in themselves to get their own block.
            text_lines = min(1, height)
            if text_lines == 0:
                label_line_arr = []
            elif text_lines == 1:
                label_line_arr = ["..."]
            else:
                raise ValueError(text_lines)

        padding_lines = height - text_lines
        padding_lines_above = padding_lines // 2
        padding_lines_below = padding_lines - padding_lines_above

        lines: List[str] = []

        def _bar(label=""):
            if len(lines) == height - 1:
                fill = bottom_border
            elif len(lines) == 0:
                fill = top_border
            else:
                fill = " "
            lines.append(
                prefix
                + self.bar(width=width, left=left + fill, fill=fill, right=fill + right, label=label)
                + suffix
            )

        for i in range(padding_lines_above):
            _bar()
        for line in label_line_arr:
            _bar(line)
        for i in range(padding_lines_below):
            _bar()

        return lines

    def _render(self, tree: SizeTree, width: int, height: int, depth: int, topmost: bool, leftmost: bool) -> List[str]:
        if height < 1:
            return []

        # Render current dir.
        parent_block = self.render_node(tree, width=width, height=height, depth=depth, topmost=topmost, leftmost=leftmost)
        if depth == 0:
            return parent_block

        # Render children.
        children = sorted(tree.children.values(), reverse=True)
        # Render each child as a subtree, which is a list of lines.
        subtrees_block = []
        cumulative_size = 0
        last_row = curr_row = 0
        last_block_height = sys.maxsize
        size_of_all_children = sum([child.size for child in children])
        height_of_all_children = int(
            round(float(height * size_of_all_children) / tree.size, 0)
        )
        assert height_of_all_children <= height
        for child in children:
            cumulative_size += child.size
            curr_row = int(round(float(height * cumulative_size) / tree.size, 0))
            block_height = max(0, curr_row - last_row)
            # Don't let the grid-alignment make any blocks more than twice as
            # tall than without alignment.
            block_height = min(
                block_height, 2 * int(round(float(height * child.size) / tree.size, 0))
            )
            # Because of aligning the blocks to the text grid, sometimes a taller
            # block would follow a shorter one, even though the nodes are in a
            # decreasing order by size. This would look confusing, so we limit the
            # height of some blocks to avoid that. This causes the build-up of a
            # deficit of rows, which eventually gets resolved in one of two ways:
            #
            # - If a height-truncated block is followed by blocks that could be
            # slightly shorter, they will get the same height until the
            # difference is eliminated.
            #
            # - If there is still a deficit at the end, we make up for it by adding
            # space-filler lines at the bottom.
            block_height = min(block_height, last_block_height)
            # Because of the descreasing order, the last block height is the
            # shortest block height encountered so far. Don't allow taller
            # blocks than that in the following iterations.
            last_block_height = block_height
            subtrees_block.extend(self._render(child, width, block_height, depth - 1, topmost=topmost, leftmost=False))
            topmost = False
            last_row += block_height

        # An extra block to represent small directories that didn't get their
        # own block and to make up for the deficit caused by grid alignment.
        if curr_row > last_row:
            lines = self.render_node(
                None, width=width, height=curr_row - last_row, depth=depth - 1, topmost=topmost, leftmost=False
            )
            topmost = False
            for line in lines:
                subtrees_block.append(line)

        # Assemble blocks.
        lines = []
        subtrees_linecount = len(subtrees_block)
        assert subtrees_linecount <= height_of_all_children
        desired_length = width * (depth + 1)
        for i in range(height):
            parent_line = parent_block[i]
            if i < subtrees_linecount:
                assert i < height_of_all_children
                line = parent_line + subtrees_block[i]
            else:
                line = parent_line
            if not self.color_mode:
                # Add a background pattern to make the content stand out
                line += "▒" * (desired_length - len(line))
            lines.append(line)
        return lines


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
        lines: List[str] = []
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
    _COLOR_CYCLE_RGY = ["\x1b[41;97m", "\x1b[42;30m", "\x1b[43;30m"]

    # Blue, Magenta, Cyan
    _COLOR_CYCLE_BMC = ["\x1b[44;97m", "\x1b[45;30m", "\x1b[46;30m"]

    _COLOR_RESET = "\x1b[0m"

    @classmethod
    def wrap(cls, s: str) -> str:
        """Wrap given string in colorize markers"""
        return cls._START + s + cls._END

    @classmethod
    def str_len(cls, b: str) -> int:
        return len(b.replace(cls._START, "").replace(cls._END, ""))

    @classmethod
    def _get_colorize(cls, colors: List[str]):
        """Construct function that replaces markers with color codes (cycling through given color codes)"""
        color_cycle = itertools.cycle(colors)

        def colorize(line: str) -> str:
            line = re.sub(cls._START, lambda m: next(color_cycle), line)
            line = re.sub(cls._END, cls._COLOR_RESET, line)
            return line

        return colorize

    @classmethod
    def get_colorize_rgy(cls):
        return cls._get_colorize(cls._COLOR_CYCLE_RGY)

    @classmethod
    def get_colorize_bmc(cls):
        return cls._get_colorize(cls._COLOR_CYCLE_BMC)


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


def get_progress_reporter(
    max_interval: float = 1,
    terminal_width: int = 80,
    write: Callable[[str], Any] = sys.stdout.write,
    time: Callable[[], float] = time.time,
) -> Callable[[str], None]:
    """
    Create a progress reporting function that only actually prints in intervals
    """
    next_time = 0.0
    # Start printing frequently.
    interval = 0.0

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
    terminal_height = shutil.get_terminal_size().lines

    # Handle commandline interface.
    # TODO switch to argparse?
    import optparse
    cliparser = optparse.OptionParser(
        """usage: %prog [options] [DIRS]
        %prog gives a graphic representation of the disk space
        usage of the folder trees under DIRS.""",
        version='%prog 3.1.1')
    cliparser.add_option(
        '-w', '--width',
        action='store', type='int', dest='display_width', default=terminal_width,
        help='total width of the chart', metavar='WIDTH'
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
        help='Show one line bars instead of two line bars (ignored in columns mode)'
    )
    cliparser.add_option(
        '-c', '--color',
        action='store_true', dest='color', default=False,
        help='Use colors to render bars (instead of ASCII art)'
    )
    cliparser.add_option(
        '-C', '--columns',
        action='store_true', dest='columns_mode', default=False,
        help='Build the chart from vertical columns (instead of horizontal bars)'
    )
    cliparser.add_option(
        '-H', '--height',
        action='store', type='int', dest='display_height', default=terminal_height - 5,
        help='Height of the chart in columns mode (ignored in bars mode)', metavar='HEIGHT'
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

        if opts.columns_mode:
            renderer = ColumnsRenderer(
                height=opts.display_height,
                max_depth=opts.max_depth,
                size_formatter=size_formatter,
                color_mode=opts.color
            )
        elif opts.one_line:
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
