.. image:: https://travis-ci.org/soxofaan/duviz.svg?branch=master
    :target: https://travis-ci.org/soxofaan/duviz

What is duviz?
--------------

``duviz`` is a simple command line utility written in Python to visualize disk space usage.

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


Instead of size in bytes, you can also get inode usage: just use the option ``-i``.


Installation
------------

Dependencies
	``duviz`` is designed to run on Unix platforms (like Linux and OS X).
	It just requires the ``du`` command line utility to collect disk usage information (and ``ls`` for file counting).
	Apart from that it doesn't require anything outside of the Python standard library.
	These things are typically available out of the box on a standard Unix-like system.


Installation (Pip)
	``duviz`` can be installed through ``pip`` (e.g. in a virtual env)::

		pip install duviz

	which will install the ``duviz`` utility to the corresponding ``bin`` folder.

Installation (Homebrew)
	``duviz`` can also be installed with `Homebrew <https://brew.sh/>`_::

		brew install https://raw.github.com/soxofaan/duviz/master/extra/homebrew/duviz.rb


Without installation
	The file ``duviz.py`` is also intended to be usable as a standalone Python script,
	without having to install it.
	Download ``duviz.py`` to some location of your liking and run it::

		python path/to/duviz.py



Usage
-----

If you run ``duviz`` without arguments, it will render the disk usage of the current working folder.

If you specify one or more directories, it will render the usage of those directories, how intuitive is that!

Run it with option ``--help`` for more options.


How does it work?
-----------------

``duviz`` dispatches the heavy work to the UNIX utility ``du`` to gather disk space statistics,
parses its output and renders this information in an easily understandable ASCII-art image.

For inode counting a recursive ``ls -i`` is used instead of ``du``.
