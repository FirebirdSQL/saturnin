#coding:utf-8
"""A setuptools based setup module for saturnin package.
See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# Arguments marked as "Required" below must be included for upload to PyPI.
# Fields marked as "Optional" may be commented out.

setup(
    name='saturnin',
    version= '0.1',
    description='Reference implementation of selected Firebird Butler services in Python',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/FirebirdSQL/saturnin',
    author='Pavel Císař',
    author_email='pcisar@users.sourceforge.net',
    license='MIT',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',

        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',

        'Operating System :: POSIX :: Linux',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: MacOS',

        'Topic :: Database',
        'Topic :: System :: Systems Administration',
        'Topic :: System :: Monitoring',
        'Topic :: System :: Logging'
],
    keywords='Firebird Butler Services ZeroMQ',  # Optional
    packages=find_packages(),  # Required
    install_requires=[],  # Optional
    python_requires='>=3.0, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, <4',
    test_suite='nose.collector',
    data_files=[],
    project_urls={
        #'Documentation': 'http://fdb2.readthedocs.io/en/latest/',
        'Bug Reports': 'https://github.com/FirebirdSQL/saturnin/issues',
        'Funding': 'https://www.firebirdsql.org/en/donate/',
        'Source': 'https://github.com/FirebirdSQL/saturnin',
    },
)
