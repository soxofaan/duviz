#!/usr/bin/env python
##############################################################################
# Copyright 2009-2012 Stefaan Lippens
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
'''

import os
import sys
import re
import subprocess


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
            return f.format(size)
        size = float(size) / base
    return f[-1].forma(size)


def human_readable_byte_size(size, binary=False):
    '''Return byte size as 11B, 12.34KB or 345.24MB (or binary: 12.34KiB, 345.24MiB).'''
    if binary:
        return _human_readable_size(size, 1024, ['{0:d}B', '{0:.2f}KiB', '{0:.2f}MiB', '{0:.2f}GiB', '{0:.2f}TiB'])
    else:
        return _human_readable_size(size, 1000, ['{0:d}B', '{0:.2f}KB', '{0:.2f}MB', '{0:.2f}GB', '{0:.2f}TB'])


def human_readable_count(count):
    '''Return inode count as 11, 12.34k or 345.24M.'''
    return _human_readable_size(count, 1000, ['{0:d}', '{0:.2f}k', '{0:.2f}M', '{0:.2f}G', '{0:.2f}T'])


##############################################################################
def path_split(path):
    '''Split a file system path in a list of path components (as a recursive os.path.split()).'''
    items = []
    while True:
        head, tail = os.path.split(path)
        items.insert(0, tail)
        if head == '':
            break
        elif head == '/':
            items.insert(0, head)
            break
        path = head
    return items


##############################################################################
class DirectoryTreeNode(object):
    '''
    Node in a directory tree, holds the name of the node, its size (including
    subdirectories) and the subdirectories.
    '''
    def __init__(self, name, size=None):
        self.name = name
        self.size = size
        self.subdirs = {}

    def own_size(self):
        return self.size - sum([d.size for d in self.subdirs])

    def import_path(self, path, size):
        '''
        Import directory tree data
        @param path list of path directory entries.
        @param size total size of the path in bytes.
        '''
        assert len(path) > 0
        # Make sure that given path is compatible with the path of current
        # node. For example:
        #     self.name = 'a/b/' -> self_path = ['a', 'b', '']
        #     path = ['a', 'b', 'c']
        self_path = path_split(self.name)
        # Remove common prefix, resulting in
        #     self_path = []
        #     path = ['c']
        while len(self_path) > 0:
            if self_path[0] == path[0]:
                self_path.pop(0)
                path.pop(0)
            elif len(self_path) == 1 and self_path[0] == '':
                self_path.pop(0)
            else:
                raise ValueError
        # Do something with the remaining path.
        if len(path) == 0:
            # We are at the end of the path: store size.
            assert self.size == None
            self.size = size
        else:
            # We are not yet at end of path: descend further.
            name = path[0]
            if name not in self.subdirs.keys():
                self.subdirs[name] = DirectoryTreeNode(name)
            self.subdirs[name].import_path(path, size)

    def __cmp__(self, other):
        return - cmp(self.size, other.size)

    def __repr__(self):
        return '%s(%d)%s' % (self.name, self.size, self.subdirs.values())

    def block_display(self, width, max_depth=5, top=True):
        if width < 1 or max_depth < 0:
            return ''

        lines = []

        if top:
            lines.append('_' * width)

        # Display of current dir.
        lines.append(bar(width, self.name, fill=' '))
        lines.append(bar(width, str(human_readable_byte_size(self.size)), fill='_'))

        # Display of subdirectories.
        subdirs = self.subdirs.values()
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
                subdir_blocks.append(sd.block_display(currpos - lastpos, max_depth - 1, top=False).split('\n'))
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


##############################################################################
def build_tree(directory, feedback=sys.stdout, terminal_width=80, options=None):
    '''
    Build a tree of DirectoryTreeNodes, starting at the given directory.
    '''

    durep = re.compile(r'([0-9]*)\s*(.*)')
    # Measure size in 1024 byte blocks. The GNU-du option -b enables counting
    # in bytes directely, but it is not available in BSD-du.
    duargs = ['-k']
    # Handling of symbolic links.
    if hasattr(options, 'onefilesystem') and options.onefilesystem:
        duargs.append('-x')
    if hasattr(options, 'dereference') and options.dereference:
        duargs.append('-L')
    dupipe = subprocess.Popen(['du'] + duargs + [directory], stdout=subprocess.PIPE)
    dirtree = DirectoryTreeNode(directory)
    for line in dupipe.stdout:
        mo = durep.match(line)
        # Size in bytes.
        size = int(mo.group(1)) * 1024
        path = mo.group(2)
        if feedback:
            feedback.write(('scanning %s' % path).ljust(terminal_width)[:terminal_width] + '\r')
        dirtree.import_path(path_split(path), size)
    if feedback:
        feedback.write(' ' * terminal_width + '\r')
    dupipe.stdout.close()
    return dirtree


##############################################################################
if __name__ == '__main__':

    terminal_width = terminal_size()[1]

    #########################################
    # Handle commandline interface.
    import optparse
    cliparser = optparse.OptionParser(
        '''usage: %prog [options] [DIRS]
        %prog gives a graphic representation of the
        usage of the subdirs in the directories DIRS.''',
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

    (clioptions, cliargs) = cliparser.parse_args()

    ########################################
    # Do current dir if no dirs are given.
    if len(cliargs) == 0:
        cliargs = ['.']

    for directory in cliargs:
        tree = build_tree(directory, terminal_width=clioptions.display_width, options=clioptions)
        print tree.block_display(clioptions.display_width, max_depth=clioptions.max_depth)
