.. image:: https://travis-ci.org/soxofaan/duviz.svg?branch=master
    :target: https://travis-ci.org/soxofaan/duviz


What is duviz?
--------------

``duviz`` is a command-line utility written in Python to visualize disk space usage.

It's like the plethora of desktop applications and widgets
(e.g. Filelight, DaisyDisk, WinDirStat, JDiskReport, TreeSize, SpaceSniffer, ...),
but instead of a fancy GUI with animated pie charts and shaded boxes
you get a funky "ASCII art style hierarchical tree of bars".
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

- Basically there is just one python script ``duviz.py``.
  No installation required: put it where you want it. Use it how you want it.
- Only uses standard library and just depends on ``du`` and ``ls`` utilities,
  which are available out of the box on a typical Unix platform (Linux, macOS)
- Works with Python 3.
- Speed. No need to wait for a GUI tool to get up and running, let alone scanning your disk.
  The hard work is done by ``du`` (or ``ls``), which run an C-speed.
- Progress reporting while you wait. Be hypnotized!
- Detects your terminal width for maximum visualization pleasure.
- Apart from file size (the default), you can also just count files (inodes)


Installation
------------

With Pip
    ``duviz`` can be installed through ``pip`` (e.g. in a virtual env)::

        pip install duviz

    which will install the ``duviz`` utility to the corresponding ``bin`` folder.

With Homebrew
    ``duviz`` can also be installed with `Homebrew <https://brew.sh/>`_::

        brew install https://raw.github.com/soxofaan/duviz/master/extra/homebrew/duviz.rb

No installation
    The file ``duviz.py`` is also intended to be usable as a standalone Python script,
    without having to install it.
    Download ``duviz.py`` to some location of your liking and run it::

        python path/to/duviz.py


Usage
-----

If you run ``duviz`` without arguments, it will render the disk usage of the current working folder.
If you specify one or more directories, it will render the usage of those directories, how intuitive is that!

Instead of size in bytes, you can also get inode usage: just use the option ``--inodes`` (or ``-i`` in short).

Run it with option ``--help`` for more options.
