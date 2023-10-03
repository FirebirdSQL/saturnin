# SPDX-FileCopyrightText: 2020-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/_scripts/svcrun.py
# DESCRIPTION:    Script to run one service in main or separate thread
# CREATED:        19.11.2020
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

"""Saturnin script to run one service in main or separate thread

"""

from __future__ import annotations
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter, Action
from configparser import ConfigParser, ExtendedInterpolation
import logging
from logging.config import fileConfig
from firebird.base.logging import get_logger, Logger, bind_logger, ANY
from firebird.base.trace import trace_manager
from saturnin.base import directory_scheme, SECTION_SERVICE
from saturnin.component.controller import Outcome
from saturnin.component.single import SingleExecutor

LOG_FORMAT = '%(levelname)s [%(processName)s/%(threadName)s] [%(agent)s:%(context)s] %(message)s'

class UpperAction(Action):
    """Converts argument to uppercase.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values.upper())

def main(description: str=None, service_config: str=None):
    """Saturnin script to run one service, either unmanaged in main thread, or managed in
    separate thread.

    Arguments:
      description: Description shown when `--help` is used.
      service_config: Default value for `SERVICE-CONFIG` argument.

    usage::

      saturnin-service [-h] [-c CONFIG] [-s SECTION] [-q] [-o] [--main-thread]
                       [-l {critical,fatal,error,warn,warning,info,debug,notset}]
                       SERVICE-CONFIG

    positional arguments:
      SERVICE-CONFIG        Path to service configuration file

    optional arguments:
      -h, --help            show this help message and exit
      -c CONFIG, --config CONFIG
                            Path to additional configuration file. Could be specified multiple times. (default: None)
      -s SECTION, --section SECTION
                            Configuration section name (default: service)
      -q, --quiet           Suppress console output (default: False)
      -o, --outcome         Always print service execution outcome (default: False)
      --main-thread         Start the service in main thread (default: False)
      -l {critical,fatal,error,warn,warning,info,debug,notset}, --log-level {critical,fatal,error,warn,warning,info,debug,notset}
                            Logging level (default: None)
    """
    if description is None:
        description = "Saturnin script to run one service, either unmanaged in main thread, or managed in separate thread."
    parser: ArgumentParser = ArgumentParser(description=description,
                                            formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('service', metavar='SERVICE-CONFIG',
                        help="Path to service configuration file",
                        nargs=1 if service_config is None else '?',
                        default=service_config)
    parser.add_argument('-c','--config', metavar='CONFIG', action='append',
                        help="Path to additional configuration file. "
                             "Could be specified multiple times.")
    parser.add_argument('-s', '--section', help="Configuration section name",
                        default=SECTION_SERVICE)
    parser.add_argument('-q', '--quiet', action='store_true',
                        help="Suppress console output", default=False)
    parser.add_argument('-o','--outcome', action='store_true',
                        help="Always print service execution outcome", default=False)
    parser.add_argument('--main-thread', action='store_true',
                        help="Start the service in main thread", default=False)
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
        with SingleExecutor('saturnin-service', direct=args.main_thread) as executor:
            executor.configure(cfg_files, section=args.section)
            result = executor.run()
            if not args.quiet and result is not None:
                outcome, details = result
                if outcome is not Outcome.OK or args.outcome:
                    print(f'{args.section}: {outcome.value}')
                    if details:
                        for line in details:
                            print(f' {line}')
    except Exception as exc: # pylint: disable=W0703
        log.exception("Service execution failed")
        parser.exit(1, f'{exc!s}\n')
        parser.exit(1)
    finally:
        logging.shutdown()

if __name__ == '__main__':
    main()
