#coding:utf-8
"""A setuptools based setup module for saturnin package.
See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

# To use a consistent encoding
from codecs import open
from os import path
# Always prefer setuptools over distutils
from setuptools import setup, find_packages

HERE = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(HERE, 'README.md'), encoding='utf-8') as f:
    LONG_DESCRIPTION = f.read()

# Arguments marked as "Required" below must be included for upload to PyPI.
# Fields marked as "Optional" may be commented out.

setup(
    name='saturnin',
    version='0.2.0',
    description='Reference implementation of selected Firebird Butler services in Python',
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    url='https://github.com/FirebirdSQL/saturnin',
    author='Pavel Císař',
    author_email='pcisar@users.sourceforge.net',
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',

        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',

        'Operating System :: POSIX :: Linux',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: MacOS',

#        'Framework :: Saturnin SDK',

        'Topic :: Database',
        'Topic :: System :: Systems Administration',
        'Topic :: System :: Monitoring',
        'Topic :: System :: Logging'
        ],
    keywords='Firebird Butler Services ZeroMQ',  # Optional
    packages=['saturnin'],  # Required
    install_requires=['pyzmq>=18.0.0', 'protobuf>=3.9.0', 'saturnin-sdk>=0.4.0',
                      'tabulate>=0.8.3'],
    python_requires='>=3.6, <4',
    test_suite='nose.collector',
    data_files=[],
    namespace_packages=[],
    project_urls={
        'Documentation': 'http://saturnin.readthedocs.io/en/latest/',
        'Bug Reports': 'https://github.com/FirebirdSQL/saturnin/issues',
        'Funding': 'https://www.firebirdsql.org/en/donate/',
        'Source': 'https://github.com/FirebirdSQL/saturnin',
    },
    entry_points={'console_scripts': ['saturnin-node = saturnin.service.node.runner:main',
                                      'nodeconsole = saturnin.service.node.console:main',
                                     ],
                  'saturnin.service': ['saturnin-node = saturnin.service.node.api:SERVICE_DESCRIPTION',
                                       'firebird-log = saturnin.micro.fblog.api:SERVICE_DESCRIPTION',
                                      ],
                 }
)
