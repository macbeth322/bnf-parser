#!/usr/bin/env python3

from setuptools import setup, find_packages

setup(
    name='bnf',
    version='0.1.0',
    author='macbeth322',
    author_email='chrisp533@gmail.com',
    package_dir={'': 'src'},
    packages=find_packages('src'),
    install_requires=[
        'typing'
    ],
)