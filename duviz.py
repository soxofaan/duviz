#!/usr/bin/env python

"""
Command line tool for visualization of the disk space usage of a directory
and its subdirectories.

Copyright: 2009-2019 Stefaan Lippens
License: MIT
Website: http://soxofaan.github.io/duviz/
"""

import argparse
import contextlib
import itertools
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import unicodedata
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Tuple, Union
import zipfile
from pathlib import Path


# TODO: catch absence/failure of du/ls subprocesses
# TODO: how to handle unreadable subdirs in du/ls?
# TODO: option to sort alphabetically (instead of on size)
# TODO: use pathlib.Path instead of naive strings where appropriate


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
        cls,
        pairs: Iterable[Tuple[List[str], int]],
        root: str = "/",
        _recalculate_sizes: bool = False,
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

        if _recalculate_sizes:
            # TODO: automatically detect need to recalculate sizes
            tree._recalculate_own_sizes_to_total_sizes()
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

    # TODO no need for subclassing from SizeTree

    _du_regex = re.compile(r'([0-9]*)\s*(.*)')

    @classmethod
    def from_du(
        cls,
        root: str,
        one_filesystem: bool = False,
        dereference: bool = False,
        progress_report: Optional[Callable[[str], None]] = None,
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
                du_listing=(line.decode("utf-8") for line in process.stdout),
                progress_report=progress_report,
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
    # TODO no need for subclassing from SizeTree

    @classmethod
    def from_ls(
        cls, root: str, progress_report: Optional[Callable[[str], None]] = None
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
        cls,
        root: str,
        ls_listing: str,
        progress_report: Optional[Callable[[str], None]] = None,
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

        tree = cls.from_path_size_pairs(
            pairs=pairs(ls_listing), root=root, _recalculate_sizes=True
        )
        return tree


class ZipFileProcessor:
    """Build `SizeTree` from a file tree in a ZIP archive file."""

    @staticmethod
    def from_zipfile(path: Union[str, Path], compressed: bool = True) -> SizeTree:
        # TODO: handle zipfile.BadZipFile in nicer way?
        with zipfile.ZipFile(path, mode="r") as zf:
            if compressed:
                pairs = (
                    (path_split(z.filename), z.compress_size) for z in zf.infolist()
                )
            else:
                pairs = ((path_split(z.filename), z.file_size) for z in zf.infolist())
            return SizeTree.from_path_size_pairs(
                pairs=pairs, root=str(path), _recalculate_sizes=True
            )


class TarFileProcessor:
    """Build `SizeTree` from file tree in a tar archive file."""

    @staticmethod
    def from_tar_file(path: Union[str, Path]) -> SizeTree:
        with tarfile.open(path, mode="r") as tf:
            pairs = ((path_split(m.name), m.size) for m in tf.getmembers())
            return SizeTree.from_path_size_pairs(
                pairs=pairs, root=str(path), _recalculate_sizes=True
            )


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

    @staticmethod
    def bar(
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

    # Handle commandline interface.
    cli = argparse.ArgumentParser(
        prog="duviz", description="Render ASCII-art representation of disk space usage."
    )
    cli.add_argument(
        "paths",
        metavar="PATH",
        nargs="*",
        help="Directories or ZIP/tar archives to scan",
        default=["."],
    )
    cli.add_argument(
        "-w",
        "--width",
        type=int,
        dest="display_width",
        default=terminal_width,
        help="total width of all bars",
        metavar="WIDTH",
    )
    cli.add_argument(
        "-x",
        "--one-file-system",
        action="store_true",
        dest="one_file_system",
        default=False,
        help="skip directories on different filesystems",
    )
    cli.add_argument(
        "-L",
        "--dereference",
        action="store_true",
        dest="dereference",
        default=False,
        help="dereference all symbolic links",
    )
    cli.add_argument(
        "--max-depth",
        action="store",
        type=int,
        dest="max_depth",
        default=5,
        help="maximum recursion depth",
        metavar="N",
    )
    cli.add_argument(
        "-i",
        "--inodes",
        action="store_true",
        dest="inode_count",
        default=False,
        help="count inodes instead of file size",
    )
    cli.add_argument(
        "--no-progress",
        action="store_false",
        dest="show_progress",
        default=True,
        help="disable progress reporting",
    )
    cli.add_argument(
        "-1",
        "--one-line",
        action="store_true",
        dest="one_line",
        default=False,
        help="Show one line bars instead of two line bars",
    )
    cli.add_argument(
        "-c",
        "--color",
        action="store_true",
        dest="color",
        default=False,
        help="Use colors to render bars (instead of ASCII art)",
    )
    cli.add_argument(
        # TODO short option, "-z"?
        "--zip",
        action="store_true",
        dest="zip",
        help="Force ZIP-file handling of given paths (e.g. lacking a traditional `.zip` extension).",
    )
    cli.add_argument(
        "--unzip-size",
        action="store_true",
        help="Visualize decompressed file size instead of compressed file size for ZIP files.",
    )
    cli.add_argument(
        # TODO short option?
        "--tar",
        action="store_true",
        dest="tar",
        help="""
            Force tar-file handling of given paths
            (e.g. lacking a traditional extension like `.tar`, `.tar.gz`, ...).
        """,
    )

    args = cli.parse_args()

    # Make sure we have a valid list of paths
    paths: List[str] = []
    for path in args.paths:
        if os.path.exists(path):
            paths.append(path)
        else:
            sys.stderr.write('Warning: not a valid path: "%s"\n' % path)

    if args.show_progress:
        progress_report = get_progress_reporter(terminal_width=args.display_width)
    else:
        progress_report = None

    for path in paths:
        if args.zip or (
            os.path.isfile(path) and os.path.splitext(path)[1].lower() == ".zip"
        ):
            tree = ZipFileProcessor.from_zipfile(path, compressed=not args.unzip_size)
            size_formatter = SIZE_FORMATTER_BYTES
        elif args.tar or (
            os.path.isfile(path)
            and any(
                path.endswith(ext) for ext in {".tar", ".tar.gz", ".tgz", "tar.bz2"}
            )
        ):
            tree = TarFileProcessor().from_tar_file(path)
            size_formatter = SIZE_FORMATTER_BYTES
        elif args.inode_count:
            tree = InodeTree.from_ls(root=path, progress_report=progress_report)
            size_formatter = SIZE_FORMATTER_COUNT
        else:
            tree = DuTree.from_du(
                root=path,
                one_filesystem=args.one_file_system,
                dereference=args.dereference,
                progress_report=progress_report,
            )
            size_formatter = SIZE_FORMATTER_BYTES

        max_depth = args.max_depth
        if args.one_line:
            if args.color:
                renderer = ColorSingleLineBarRenderer(
                    max_depth=max_depth, size_formatter=size_formatter
                )
            else:
                renderer = AsciiSingleLineBarRenderer(
                    max_depth=max_depth, size_formatter=size_formatter
                )
        else:
            if args.color:
                renderer = ColorDoubleLineBarRenderer(
                    max_depth=max_depth, size_formatter=size_formatter
                )
            else:
                renderer = AsciiDoubleLineBarRenderer(
                    max_depth=max_depth, size_formatter=size_formatter
                )

        print("\n".join(renderer.render(tree, width=args.display_width)))


if __name__ == '__main__':
    main()
