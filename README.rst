.. image:: https://img.shields.io/pypi/pyversions/duviz
    :target: https://pypi.org/project/duviz/
    :alt: PyPI - Python Version
.. image:: https://github.com/soxofaan/duviz/actions/workflows/unittests.yml/badge.svg?branch=master
    :target: https://github.com/soxofaan/duviz/actions/workflows/unittests.yml
    :alt: unit tests
.. image:: https://github.com/soxofaan/duviz/actions/workflows/pre-commit.yml/badge.svg?branch=master
    :target: https://github.com/soxofaan/duviz/actions/workflows/pre-commit.yml
    :alt: pre-commit


What is duviz?
--------------

``duviz`` is a (Python 3) command-line tool to visualize disk space usage.

It's like the plethora of desktop applications and widgets
(e.g. Filelight, DaisyDisk, WinDirStat, JDiskReport, TreeSize, SpaceSniffer, ...),
but instead of a fancy GUI with animated pie charts and shaded boxes
you get a funky "ASCII art style hierarchical tree of bars" in your shell.
If that didn't make a lot of sense to you, look at this example of this ``/opt`` folder::

    $ duviz /opt
    ________________________________________________________________________________
    [                                     /opt                                     ]
    [____________________________________3.30GB____________________________________]
    [                                    local                                     ]
    [____________________________________3.30GB____________________________________]
    [              var              ][        lib         ][ share  ][Libr][lib][]|
    [_____________1.36GB____________][______925.47MB______][411.37MB][231.][222][]|
    [           macports           ]|[gcc][gcc4][]|||      [][]||||||[Fra]|[gc] |
    [____________1.36GB____________]|[250][226.][]|||      [][]||||||[231]|[21] |
    [    software    ][distfile][]| |           ||  |      | ||||||||[Pyt] [x8]
    [____785.31MB____][421.56MB][]| |           ||  |      | ||||||||[231] [21]
    [gc][][]||||||||||||||||||||[]               |            ||| |  [Ve]  ||[]
    [17][][]||||||||||||||||||||[]               |            ||| |  [23]  ||[]


Features
--------

- Basically it consists of just one Python 3 script ``duviz.py``.
  No installation required: put it where you want it. Use it how you want it.
- Only uses standard library and just depends on ``du`` and ``ls`` utilities,
  which are available out of the box on a typical Unix platform (Linux, macOS)
- Speed. No need to wait for a GUI tool to get up and running, let alone scanning your disk.
  The hard work is done by ``du`` (or ``ls``), which run an C-speed.
- Progress reporting while you wait. Be hypnotized!
- Detects your terminal width for maximum visualization pleasure.
- Not only supports "disk usage" based on file size,
  but also allows to count files (inode count mode)
  or give a size breakdown of ZIP or tar files.
- Option to use terminal colors for the boxes instead of ASCII art


Installation
------------

Pip based
    duviz can be installed with pip in a desired virtual environment::

        pip install duviz

    which will install a ``duviz`` command line utility in your environment.

    If you already have `pipx <https://pypa.github.io/pipx/>`_ on your toolbelt,
    you might prefer to install duviz in an automatically managed,
    isolated environment with ``pipx install duviz``.

With Homebrew
    duviz can also be installed with `Homebrew <https://brew.sh/>`_::

        brew install https://raw.github.com/soxofaan/duviz/master/extra/homebrew/duviz.rb

No installation
    The file ``duviz.py`` is also designed to be usable as a standalone Python script,
    without having to install it.
    Download ``duviz.py`` and just run it::

        python path/to/duviz.py


Python 2 Support
~~~~~~~~~~~~~~~~

``duviz`` was originally (2009) a Python 2 script, and started supporting Python 3 around 2016.
With the end of life of Python 2 nearing in 2019, support for Python 2 was dropped.
The Python 2 compatible version can be found in the ``py2-compatible`` branch (last release: 1.1.1).

Usage
-----

If you run ``duviz`` without arguments, it will render the disk usage of the current working folder.
If you specify one or more directories, it will render the usage of those directories, how intuitive is that!

Instead of size in bytes, you can also get inode usage: just use the option ``--inodes`` (or ``-i`` in short).

If you directly pass ``duviz`` a ZIP or tar file,
it will visualize the size breakdown of the file tree in the ZIP/tar file.
In case of ZIP files, the compressed size will be shown by default
(option ``--unzip-size`` will toggle showing of decompressed size).
For tar files, only the decompressed size is available.

Run it with option ``--help`` for more options.
