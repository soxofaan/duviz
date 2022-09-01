
# Duviz Changelog


## [Unreleased]


## [3.1.1] - 2022-09-01

- Replace Travis CI with Github Actions


## [3.1.0] - 2019-11-12

- Add option `--color` to render with old fashioned ANSI colors
    instead of old fashioned ASCII art
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
- Python 3 related code cleanups and fine tuning


## [1.1.1] - 2019-10-20

- Probably last release supporting Python 2
- Added Homebrew formula and instructions
