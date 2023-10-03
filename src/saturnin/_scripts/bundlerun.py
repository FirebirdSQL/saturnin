# SPDX-FileCopyrightText: 2020-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/_scripts/bundlerun.py
# DESCRIPTION:    Script to run bundle of services
# CREATED:        6.12.2020
#
# The contents of this file are subject to the MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Copyright (c) 2020 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________

"""Saturnin script to run bundle of services.


"""

from __future__ import annotations
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter, Action
from configparser import ConfigParser, ExtendedInterpolation
import logging
from logging.config import fileConfig
from firebird.base.logging import get_logger, Logger, ANY, bind_logger
from firebird.base.trace import trace_manager
from saturnin.base import directory_scheme, SECTION_BUNDLE
from saturnin.component.controller import Outcome
from saturnin.component.bundle import BundleExecutor

LOG_FORMAT = '%(levelname)s [%(processName)s/%(threadName)s] %(message)s'

class UpperAction(Action):
    """Converts argument to uppercase.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values.upper())

def main(description: str=None, bundle_config: str=None):
    """Saturnin script to run bundle of services.

    Arguments:
      description: Description shown when `--help` is used.
      bundle_config: Default value for `BUNDLE-CONFIG` argument.

    usage::

      saturnin-bundle [-h] [-c CONFIG] [-s SECTION] [-q] [-o]
                      [-l {critical,fatal,error,warn,warning,info,debug,notset}]
                      BUNDLE-CONFIG

    positional arguments:
      BUNDLE-CONFIG         Path to service bundle configuration file.

    optional arguments:
      -h, --help            show this help message and exit
      -c CONFIG, --config CONFIG
                            Path to additional configuration file. Could be specified multiple times. (default: None)
      -s SECTION, --section SECTION
                            Configuration section name (default: bundle)
      -q, --quiet           Suppress console output. (default: False)
      -o, --outcome         Always print service execution outcome (default: False)
      -l {critical,fatal,error,warn,warning,info,debug,notset}, --log-level {critical,fatal,error,warn,warning,info,debug,notset}
                            Logging level (default: None)
    """
    if description is None:
        description = "Saturnin script to run bundle of services."
    parser: ArgumentParser = ArgumentParser(description=description,
                                            formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('service', metavar='BUNDLE-CONFIG',
                        help="Path to service bundle configuration file.",
                        nargs=1 if bundle_config is None else '?',
                        default=bundle_config)
    parser.add_argument('-c','--config', metavar='CONFIG', action='append',
                        help="Path to additional configuration file. "
                             "Could be specified multiple times.")
    parser.add_argument('-s', '--section', help="Configuration section name",
                        default=SECTION_BUNDLE)
    parser.add_argument('-q', '--quiet', action='store_true', help="Suppress console output.",
                        default=False)
    parser.add_argument('-o','--outcome', action='store_true',
                        help="Always print service execution outcome", default=False)
    parser.add_argument('-l', '--log-level', action=UpperAction,
                        choices=[x.lower() for x in logging._nameToLevel
                                 if isinstance(x, str)],
                        help="Logging level")

    args = parser.parse_args()

    main_config: ConfigParser = ConfigParser(interpolation=ExtendedInterpolation())
    cfg_files = [str(directory_scheme.logging_conf)]
    if args.config:
        cfg_files.extend(args.config)
    if isinstance(args.service, list):
        cfg_files.extend(args.service)
    else:
        cfg_files.append(args.service)
    cfg_files = main_config.read(cfg_files)
    # Logging configuration
    if main_config.has_section('loggers'):
        fileConfig(main_config)
    else:
        logging.basicConfig(format=LOG_FORMAT)
    bind_logger(ANY, ANY, 'saturnin')
    log: Logger = get_logger('saturnin')
    if args.log_level is not None:
        log.setLevel(args.log_level)
    # trace configuration
    if main_config.has_section('trace'):
        trace_manager.load_config(main_config)

    try:
        with BundleExecutor('saturnin-bundle') as executor:
            executor.configure(cfg_files, section=args.section)
            result = executor.run()
            if not args.quiet:
                for name, outcome, details in result:
                    if outcome is not Outcome.OK or args.outcome:
                        print(f'{name}: {outcome.value}')
                        if details:
                            for line in details:
                                print(f' {line}')
    except Exception as exc: # pylint: disable=W0703
        log.exception("Service execution failed")
        parser.exit(1, f'{exc!s}\n')
    finally:
        logging.shutdown()

if __name__ == '__main__':
    main()
