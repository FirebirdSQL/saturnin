#coding:utf-8
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

"""Saturnin script to run bundle of services


"""

from __future__ import annotations
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter, Action
from configparser import ConfigParser, ExtendedInterpolation
import logging
from logging.config import fileConfig
from datetime import datetime
import zmq
from firebird.base.logging import get_logger, Logger
from firebird.base.trace import trace_manager
from saturnin.base import ChannelManager
from saturnin.component.bundle import BundleThreadController
from saturnin.component.controller import Outcome

LOG_FORMAT = '%(levelname)s [%(processName)s/%(threadName)s] [%(agent)s:%(context)s] %(message)s'

class UpperAction(Action):
    """Converts argument to uppercase.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values.upper())

PROG_NAME = 'saturnin-bundle'

def main():
    """Runs bundle of services.
    """
    parser: ArgumentParser = ArgumentParser(PROG_NAME, description=main.__doc__,
                                            formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('service', metavar='SERVICE-CONFIG',
                        help="Path to service configuration file")
    parser.add_argument('-c','--config', metavar='CONFIG', action='append',
                        help="Path to additional configuration file. Could be specified multiple times.")
    parser.add_argument('-s', '--section', help="Configuration section name", default='bundle')
    parser.add_argument('-o','--outcome', action='store_true',
                        help="Always print service execution outcome", default=False)
    parser.add_argument('-l', '--log-level', action=UpperAction,
                        choices=[x.lower() for x in logging._nameToLevel
                                 if isinstance(x, str)],
                        help="Logging level")

    args = parser.parse_args()

    main_config: ConfigParser = ConfigParser(interpolation=ExtendedInterpolation())

    mngr: ChannelManager = None
    log: Logger = None
    try:
        cfg_files = []
        if args.config:
            cfg_files.extend(args.config)
        cfg_files.append(args.service)
        cfg_files = main_config.read(cfg_files)
        # Logging configuration
        if main_config.has_section('loggers'):
            fileConfig(main_config)
        else:
            logging.basicConfig(format=LOG_FORMAT)
        log = get_logger(PROG_NAME)
        if args.log_level is not None:
            log.setLevel(args.log_level)
        # trace configuration
        if main_config.has_section('trace'):
            trace_manager.load_config(main_config)
        #
        mngr: ChannelManager = ChannelManager(zmq.Context.instance())
        mngr.log_context = PROG_NAME
        executor: BundleThreadController = BundleThreadController(manager=mngr)
        executor.log_context = PROG_NAME
        executor.config.read(cfg_files)
        executor.configure(section=args.section)
        # run services
        start = datetime.now()
        executor.start()
        try:
            executor.join()
            raise KeyboardInterrupt() # This, or direct call to executor.stop()
        except KeyboardInterrupt: # SIGINT
            executor.stop()
        finally:
            for svc in executor.services:
                if svc.outcome is not Outcome.OK or args.outcome:
                    print(f'{svc.name} outcome:', svc.outcome.value)
                    if svc.details:
                        for line in svc.details:
                            print(' ', line)
            print('Execution time:', datetime.now() - start)
    except Exception as exc:
        if log:
            log.exception("Service execution failed")
        parser.exit(1, f'{exc!s}\n')
    finally:
        if mngr is not None:
            mngr.shutdown(forced=True)
        logging.shutdown()
        zmq.Context.instance().term()

if __name__ == '__main__':
    main()


