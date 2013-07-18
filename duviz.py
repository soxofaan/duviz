#!/usr/bin/env python
##############################################################################
# Copyright 2009-2013 Stefaan Lippens
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
##############################################################################

'''
Command line tool for visualization of the disk space usage of a directory
and its subdirectories.

Copyright: 2009-2013 Stefaan Lippens
Website: http://soxofaan.github.io/duviz/
'''

import os
import sys
import re
import subprocess


# TODO: catch absence/failure of du/ls subprocesses
# TODO: how to handle unreadable subdirs in du/ls?
# TODO: option to sort alphabetically (instead of on size)

##############################################################################
def terminal_size():
    '''
    Best effort guess of terminal size.

    @return (height, width)
    '''
    try:
        # Try to get size from ioctl system call (Unix only).
        import struct, fcntl, termios
        # Dummy string, determining answer buffer size
        # (for struct of two unsigend short ints) for ioctl call.
        dummy_string = struct.pack('HH', 0, 0)
        # File descriptor of standard output.
        file_descriptor = sys.stdout.fileno()
        # The ioctl call to get terminal size.
        answer = fcntl.ioctl(file_descriptor, termios.TIOCGWINSZ, dummy_string)
        # Unpack answer to height and width values.
        height, width = struct.unpack('HH', answer)
    except (ImportError, IOError):
        try:
            # Try to get size from environment variables.
            height, width = int(os.environ['LINES']), int(os.environ['COLUMNS'])
        except KeyError:
            # No info found: just use some sensible defaults.
            height, width = (25, 80)
    return height, width


##############################################################################
def bar(width, label, fill='-', left='[', right=']', one='|'):
    '''
    Helper function to render bar strings of certain width with a label.

    @param width the desired total width
    @param label the label to be rendered (will be clipped if too long).
    @param fill the fill character to fill empty space
    @param left the symbol to use at the left of the bar
    @param right the symbol to use at the right of the bar
    @param one the character to use when the bar should be only one character wide

    @return rendered string
    '''
    if width >= 2:
        label_width = width - len(left) - len(right)
        return left + label[:label_width].center(label_width, fill) + right
    elif width == 1:
        return one
    else:
        return ''


##############################################################################
def _human_readable_size(size, base, formats):
    '''Helper function to render counts and sizes in a easily readable format.'''
    for f in formats[:-1]:
        if round(size, 2) < base:
            return f % size
        size = float(size) / base
    return formats[-1] % size


def human_readable_byte_size(size, binary=False):
    '''Return byte size as 11B, 12.34KB or 345.24MB (or binary: 12.34KiB, 345.24MiB).'''
    if binary:
        return _human_readable_size(size, 1024, ['%dB', '%.2fKiB', '%.2fMiB', '%.2fGiB', '%.2fTiB'])
    else:
        return _human_readable_size(size, 1000, ['%dB', '%.2fKB', '%.2fMB', '%.2fGB', '%.2fTB'])


def human_readable_count(count):
    '''Return inode count as 11, 12.34k or 345.24M.'''
    return _human_readable_size(count, 1000, ['%d', '%.2fk', '%.2fM', '%.2fG', '%.2fT'])


##############################################################################
def path_split(path, base=''):
    '''
    Split a file system path in a list of path components (as a recursive os.path.split()),
    optionally only up to a given base path.
    '''
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



##############################################################################
class DirectoryTreeNode(object):
    '''
    Node in a directory tree, holds the name of the node, its size (including
    subdirectories) and the subdirectories.
    '''

    def __init__(self, path):
        # Name of the node. For root node: path up to root node as given, for subnodes: just the folder name
        self.name = path
        # Total size of node.
        # By default this is assumed to be total node size, inclusive sub nodes,
        # otherwise recalculate_own_sizes_to_total_sizes() should be called.
        self.size = None
        # Dictionary of subnodess
        self._subnodes = {}


    def import_path(self, path, size):
        '''
        Import directory tree data
        @param path Path object: list of path directory components.
        @param size total size of the path in bytes.
        '''
        # Get relative path
        path = path_split(path, base=self.name)[1:]
        # Walk down path and create subnodes if required.
        cursor = self
        for component in path:
            if component not in cursor._subnodes:
                cursor._subnodes[component] = DirectoryTreeNode(component)
            cursor = cursor._subnodes[component]
        # Set size at cursor
        assert cursor.size == None
        cursor.size = size

    def recalculate_own_sizes_to_total_sizes(self):
        '''
        If provided sizes were own sizes instead of total node sizes.

        @return (recalculated) total size of node
        '''
        self.size = self.size + sum([n.recalculate_own_sizes_to_total_sizes() for n in self._subnodes.values()])
        return self.size

    def __cmp__(self, other):
        return - cmp(self.size, other.size)

    def __repr__(self):
        return '[%s(%d):%s]' % (self.name, self.size, repr(self._subnodes))

    def block_display(self, width, max_depth=5, top=True, size_renderer=human_readable_byte_size):
        if width < 1 or max_depth < 0:
            return ''

        lines = []

        if top:
            lines.append('_' * width)

        # Display of current dir.
        lines.append(bar(width, self.name, fill=' '))
        lines.append(bar(width, size_renderer(self.size), fill='_'))

        # Display of subdirectories.
        subdirs = self._subnodes.values()
        if len(subdirs) > 0:
            # Generate block display.
            subdirs.sort()
            subdir_blocks = []
            cumsize = 0
            currpos = 0
            lastpos = 0
            for sd in subdirs:
                cumsize += sd.size
                currpos = int(float(width * cumsize) / self.size)
                subdir_blocks.append(sd.block_display(currpos - lastpos, max_depth - 1, top=False, size_renderer=size_renderer).split('\n'))
                lastpos = currpos
            # Assemble blocks.
            height = max([len(lns) for lns in subdir_blocks])
            for i in range(height):
                line = ''
                for sdb in subdir_blocks:
                    if i < len(sdb):
                        line += sdb[i]
                    elif len(sdb) > 0:
                        line += ' ' * len(sdb[0])
                lines.append(line.ljust(width))

        return '\n'.join(lines)


class SubprocessException(Exception):
    pass


##############################################################################
def build_du_tree(directory, feedback=sys.stdout, terminal_width=80, one_filesystem=False, dereference=False):
    '''
    Build a tree of DirectoryTreeNodes, starting at the given directory.
    '''

    # Measure size in 1024 byte blocks. The GNU-du option -b enables counting
    # in bytes directely, but it is not available in BSD-du.
    duargs = ['-k']
    # Handling of symbolic links.
    if one_filesystem:
        duargs.append('-x')
    if dereference:
        duargs.append('-L')
    try:
        du_pipe = subprocess.Popen(['du'] + duargs + [directory], stdout=subprocess.PIPE)
    except OSError:
        raise SubprocessException('Failed to launch "du" utility subprocess. Is it installed and in your PATH?')

    dir_tree = _build_du_tree(directory, du_pipe.stdout, feedback=feedback, terminal_width=terminal_width)

    du_pipe.stdout.close()

    return dir_tree


def _build_du_tree(directory, du_pipe, feedback=None, terminal_width=80):
    '''
    Helper function
    '''
    du_rep = re.compile(r'([0-9]*)\s*(.*)')

    dir_tree = DirectoryTreeNode(directory)

    for line in du_pipe:
        mo = du_rep.match(line)
        # Size in bytes.
        size = int(mo.group(1)) * 1024
        path = mo.group(2)
        if feedback:
            feedback.write(('scanning %s' % path).ljust(terminal_width)[:terminal_width] + '\r')
        dir_tree.import_path(path, size)
    if feedback:
        feedback.write(' ' * terminal_width + '\r')

    return dir_tree


def build_inode_count_tree(directory, feedback=sys.stdout, terminal_width=80):
    '''
    Build tree of DirectoryTreeNodes withinode counts.
    '''

    try:
        process = subprocess.Popen(['ls', '-aiR'] + [directory], stdout=subprocess.PIPE)
    except OSError:
        raise SubprocessException('Failed to launch "ls" subprocess.')

    tree = _build_inode_count_tree(directory, process.stdout, feedback=feedback, terminal_width=terminal_width)

    process.stdout.close()

    return tree


def _build_inode_count_tree(directory, ls_pipe, feedback=None, terminal_width=80):
    tree = DirectoryTreeNode(directory)
    # Path of current directory.
    path = directory
    count = 0
    all_inodes = set()

    # Process data per directory block (separated by two newlines)
    blocks = ls_pipe.read().rstrip('\n').split('\n\n')
    for i, dir_ls in enumerate(blocks):
        items = dir_ls.split('\n')

        # Get current path in directory tree
        if i == 0 and not items[0].endswith(':'):
            # BSD compatibility: in first block the root directory can be omitted
            path = directory
        else:
            path = items.pop(0).rstrip(':')

        if feedback:
            feedback.write(('scanning %s' % path).ljust(terminal_width)[:terminal_width] + '\r')

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

        # Store count.
        tree.import_path(path, count)

    # Clear feedback output.
    if feedback:
        feedback.write(' ' * terminal_width + '\r')

    tree.recalculate_own_sizes_to_total_sizes()

    return tree


##############################################################################
def main():

    terminal_width = terminal_size()[1]

    #########################################
    # Handle commandline interface.
    import optparse
    cliparser = optparse.OptionParser(
        '''usage: %prog [options] [DIRS]
        %prog gives a graphic representation of the disk space
        usage of the folder trees under DIRS.''',
        version='%prog 1.0')
    cliparser.add_option('-w', '--width',
        action='store', type='int', dest='display_width', default=terminal_width,
        help='total width of all bars', metavar='WIDTH')
    cliparser.add_option('-x', '--one-file-system',
        action='store_true', dest='onefilesystem', default=False,
        help='skip directories on different filesystems')
    cliparser.add_option('-L', '--dereference',
        action='store_true', dest='dereference', default=False,
        help='dereference all symbolic links')
    cliparser.add_option('--max-depth',
        action='store', type='int', dest='max_depth', default=5,
        help='maximum recursion depth', metavar='N')
    cliparser.add_option('-i', '--inodes',
        action='store_true', dest='inode_count', default=False,
        help='count inodes instead of file size')

    (clioptions, cliargs) = cliparser.parse_args()

    ########################################
    # Make sure we have a valid list of paths
    if len(cliargs) > 0:
        paths = []
        for path in cliargs:
            if os.path.exists(path):
                paths.append(path)
            else:
                sys.stderr.write('Warning: not a valid path: "%s"\n' % path)
    else:
        # Do current dir if no dirs are given.
        paths = ['.']

    if clioptions.inode_count:
        for directory in paths:
            tree = build_inode_count_tree(directory, terminal_width=clioptions.display_width)
            print tree.block_display(clioptions.display_width, max_depth=clioptions.max_depth, size_renderer=human_readable_count)
    else:
        for directory in paths:
            tree = build_du_tree(directory, terminal_width=clioptions.display_width, one_filesystem=clioptions.onefilesystem, dereference=clioptions.dereference)
            print tree.block_display(clioptions.display_width, max_depth=clioptions.max_depth)

if __name__ == '__main__':
    main()
