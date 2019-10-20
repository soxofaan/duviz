from setuptools import setup
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='duviz',
    version='3.0.0',
    description='Command line disk space visualization tool',
    long_description=long_description,
    url='https://github.com/soxofaan/duviz',
    author='Stefaan Lippens',
    python_requires='>=3.5',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Topic :: System :: Systems Administration',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3 :: Only',
    ],
    keywords='disk usage visualization asciiart',
    py_modules=['duviz'],
    entry_points={
        'console_scripts': [
            'duviz=duviz:main',
        ],
    },
)
