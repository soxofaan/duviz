
# Duviz Changelog


## [Unreleased]

- Migrate to `pyproject.toml` based project metadata
  and `hatchling` based packaging
  ([#15](https://github.com/soxofaan/duviz/issues/15))
- Bring back CLI option `--version` to show current version.
  ([#29](https://github.com/soxofaan/duviz/issues/29))


## [3.2.0] - 2022-12-18

- Replace `optparse` usage with `argparse`
  ([#10](https://github.com/soxofaan/duviz/issues/10))
- Drop Python 3.5 support ([#27](https://github.com/soxofaan/duviz/issues/27))
- New feature: size breakdown of ZIP and tar files ([#20](https://github.com/soxofaan/duviz/issues/20))


## [3.1.2] - 2022-12-09

- Add test runs for Python 3.10 and 3.11
- Add more type hinting
- Add `pipx` installation instructions ([#23](https://github.com/soxofaan/duviz/issues/23))
- Start using `pre-commit` for automated code style issue detection and fixing
- Start using `darker` for incrementally applying "black" code style
  ([#21](https://github.com/soxofaan/duviz/issues/21))


## [3.1.1] - 2022-09-01

- Replace Travis CI with GitHub Actions


## [3.1.0] - 2019-11-12

- Add option `--color` to render with old-fashioned ANSI colors
    instead of old-fashioned ASCII art
- Start using pytest for unit tests
- Bring back progress reporting after 3.0.0 refactor


## [3.0.0] - 2019-10-20

- Refactor size tree code for better encapsulation
- Refactor render code to allow different render styles
- Start using type hinting
- Add option `--one-line` to do "single line bar" rendering


## [2.0.1] - 2019-10-20

- Replace custom terminal size detection code with `shutil.get_terminal_size` (Issue #6)
- Trying out https://deepsource.io/ for static code analysis
- Add Travis run for Python 3.8 (instead of 3.8-dev)


## [2.0.0] - 2019-10-20

- Dropped Python 2 support
- Python 3 related code cleanups and fine-tuning


## [1.1.1] - 2019-10-20

- Probably last release supporting Python 2
- Added Homebrew formula and instructions
