
What is duviz?
--------------

``duviz.py`` is a simple command line utility written in Python to visualize disk space usage.

It's like the plethora of desktop applications and widgets
(e.g. Filelight, DaisyDisk, WinDirStat, JDiskReport, TreeSize, SpaceSniffer, ...),
but instead of a fancy GUI with animated pie charts and shaded boxes
you get a funky "ASCII art style hierarchical tree of bars".
If that didn't make a lot of sense to you, look at this example of my ``/opt`` folder::

	$ duviz.py /opt
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


Instead of size in bytes, you can also get inode usage: just use the option ``-i``.

How does it work?
-----------------

The script ``duviz.py`` dispatches the heavy work to the UNIX utility ``du`` to gather disk space statistics,
parses its output and renders this information in an easily understandable ASCII-art image.

For inode counting a recursive ``ls -i`` is used instead of ``du``.

Installation
------------

Dependencies
	``duviz.py`` is designed to run on UNIX platforms (like Linux and OS X),
	where its dependencies (a Python 2.x interpreter and the ``du`` utility)
	are typically available out of the box, so nothing to do on this front. Yay.
	On Windows you'll be sad probably.

Run it
	``duviz.py`` is a standalone script, you can store it and run it from where ever you want.

Installation
	To have it easily at your service (without having to remember the script's full path):
	copy or symlink the script to a folder in your ``$PATH``.
	If you don't know what this means, ask a UNIX guru near you.

Usage
-----

If you run ``duviz.py`` without arguments, it will render the disk usage of the current working folder.

If you specify one or more directories, it will render the usage of those directories, how intuitive is that!

Run it with option ``--help`` for more options.
