#!/usr/bin/env python
##############################################################################
# Copyright 2009 Stefaan Lippens
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
Command line tool for visual rendering the disk space usage of a directory
and its subdirectories.
'''

import os
import sys
import re
import subprocess

##############################################################################
def terminal_size():
    '''Best effort guess of terminal size: returns (height, width).'''
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
    Make a string of length 'width' with 'label' in the center,
    (trimmed if too long to fit in the string), 'left' at the left,
    'right' at the right and filling the void, if any, with 'fill'.
    If the width is one, return 'one'.
    '''
    if width >= 2:
        label_width = width - len(left) - len(right)
        return left + label[:label_width].center(label_width, fill) + right
    elif width == 1:
        return one
    else:
        return ''

##############################################################################
def human_readable_size(size):
    '''Return size as 11B, 12.34KB or 345.24MB.'''
    if size < 1e3:
        return '%dB' % size
    elif size < 1e6:
        return '%.2fKB' % (size / 1.0e3)
    elif size < 1e9:
        return '%.2fMB' % (size / 1.0e6)
    else:
        return '%.2fGB' % (size / 1.0e9)

##############################################################################
def path_split(path):
    '''Split a file system path in items.'''
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
        @param path list of path directory entries
        @param size total size of the path
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
        return -cmp(self.size, other.size)

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
        lines.append(bar(width, str(human_readable_size(self.size)), fill='_'))

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
                subdir_blocks.append(sd.block_display(currpos-lastpos, max_depth-1, top=False).split('\n'))
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
    duargs = ['-b']
    if hasattr(options, 'onefilesystem') and options.onefilesystem:
        duargs.append('-x')
    if hasattr(options, 'dereference') and options.dereference:
        duargs.append('-L')
    dupipe = subprocess.Popen(['du'] + duargs + [directory], stdout=subprocess.PIPE)
    dirtree = DirectoryTreeNode(directory)
    for line in dupipe.stdout:
        mo = durep.match(line)
        size = int(mo.group(1))
        path = mo.group(2)
        if feedback:
            feedback.write(('scanning %s' % path).ljust(terminal_width)[:terminal_width] + '\r')
        dirtree.import_path(path_split(path), size)
    if feedback:
        feedback.write(' '*terminal_width + '\r')
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
    if len(cliargs)==0:
        cliargs = ['.']


    for directory in cliargs:
        tree = build_tree(directory, terminal_width=clioptions.display_width, options=clioptions)
        print tree.block_display(clioptions.display_width, max_depth=clioptions.max_depth)

