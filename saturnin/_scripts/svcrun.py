#coding:utf-8
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
import sys
from os import getcwd
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter, Action
from configparser import ConfigParser, ExtendedInterpolation, DEFAULTSECT
import logging
from logging.config import fileConfig
import zmq
from firebird.base.logging import get_logger, Logger
from firebird.base.trace import trace_manager
from saturnin.base import StopError, ServiceDescriptor
from saturnin.component.registry import get_service_desciptors
from saturnin.component.controller import Outcome, DirectController, ThreadController, \
     ServiceExecConfig

LOG_FORMAT = '%(levelname)s [%(processName)s/%(threadName)s] [%(agent)s:%(context)s] %(message)s'

class UpperAction(Action):
    """Converts argument to uppercase.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values.upper())

PROG_NAME = 'saturnin-service'

def main():
    """Runs one service, either unmanaged in main thread, or managed in separate thread.
    """
    parser: ArgumentParser = ArgumentParser(PROG_NAME, description=main.__doc__,
                                            formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('service', metavar='SERVICE-CONFIG',
                        help="Path to service configuration file")
    parser.add_argument('-c','--config', metavar='CONFIG', action='append',
                        help="Path to additional configuration file. Could be specified multiple times.")
    parser.add_argument('-s', '--section', help="Configuration section name", default='service')
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
    # Defaults
    main_config[DEFAULTSECT]['here'] = getcwd()

    #: Could be used to stop the service in debugger session
    debug_stop: bool = False
    log: Logger = None
    try:
        # Read config
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
            log.setLevel(args.log_level.upper())
        # trace configuration
        if main_config.has_section('trace'):
            trace_manager.load_config(main_config)
        #
        if not main_config.has_section(args.section):
            raise StopError(f"Missing configuration section '{args.section}'")
        svc_executor_config: ServiceExecConfig = ServiceExecConfig(args.section)
        svc_executor_config.load_config(main_config)
        entries = get_service_desciptors(str(svc_executor_config.agent.value))
        if not entries:
            raise StopError(f"Unregistered agent '{svc_executor_config.agent.value}'")
        service_desc: ServiceDescriptor = entries[0]
        #
        if args.main_thread:
            executor: DirectController = DirectController(service_desc)
        else:
            executor: ThreadController = ThreadController(service_desc)
        executor.log_context = PROG_NAME
        executor.configure(main_config, args.section)
        # run the service
        executor.start(timeout=10000 if sys.gettrace() is None else None)
        if not args.main_thread:
            try:
                while True:
                    executor.join(1)
                    # This, or direct call to executor.stop()
                    if debug_stop or not executor.is_running():
                        raise KeyboardInterrupt()
            except KeyboardInterrupt: # SIGINT
                print()
                try:
                    executor.stop()
                except TimeoutError:
                    executor.terminate()
                except Exception as exc:
                    if log:
                        log.error("Error while stopping the service")
            finally:
                if executor.outcome is not Outcome.OK or args.outcome:
                    print('Outcome:', executor.outcome.value)
                    if executor.details:
                        print('Details:')
                        for line in executor.details:
                            print(line)
    except Exception as exc:
        if log:
            log.error("Service execution failed")
        parser.exit(1, f'{exc!s}\n')
    finally:
        logging.shutdown()
        zmq.Context.instance().term()

if __name__ == '__main__':
    main()

