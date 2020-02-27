#!/usr/bin/python
#coding:utf-8
#
# PROGRAM/MODULE: Saturnin - Runtime node service executor
# FILE:           saturnin/service/node/runner.py
# DESCRIPTION:    Script that runs Saturnin NODE service
# CREATED:        17.5.2019
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
# Copyright (c) 2019 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________.

"""Saturnin - Runtime node service executor

NODE Service manages Saturnin runtime node. It provides environment for execution and
management of other Saturnin services. This script is a simple initial runner for testing
purposes. It will be replaced with daemon (POSIX) / service (Windows) runners.
"""

import logging
#from typing import Dict, List, Optional
import signal
from uuid import uuid1
from os import getpid
from functools import reduce
import platform
import zmq
from argparse import ArgumentParser, Action
from saturnin.core.types import PeerDescriptor, ZMQAddress, AddressDomain
from saturnin.core.config import ServiceConfig
from saturnin.core.service import load, Event, SimpleServiceImpl, BaseService
from saturnin.service.node.api import SERVICE_DESCRIPTOR

__VERSION__ = '0.1'

# Classes

class UpperAction(Action):
    "Converts argument to uppercase."
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values.upper())

def main():
    "Main function"

    def handle_signal(signum, frame):
        if signum == signal.SIGINT:
            print("\nTerminating on user request...")
        else:
            print("\nTerminating...")
        stop_event.set()

    logging.basicConfig(format='%(levelname)s:%(processName)s:%(threadName)s:%(name)s:%(message)s')
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    stop_event = Event()
    node_uid = uuid1()

    local_address = ZMQAddress('inproc://%s' % node_uid.hex)
    if platform.system() == 'Linux':
        node_address = ZMQAddress('ipc://@%s' % node_uid.hex)
    else:
        node_address = ZMQAddress('tcp://127.0.0.1:9001')
    parser = ArgumentParser(description="Saturnin NODE runner")
    parser.add_argument('-e', '--endpoint', nargs='+', help="ZMQ addresses for the node service")
    parser.add_argument('-l', '--log-level', action=UpperAction,
                        choices=[x.lower() for x in logging._nameToLevel
                                 if isinstance(x, str)],
                        help="Logging level")
    parser.set_defaults(log_level='WARNING')
    args = parser.parse_args()
    logger = logging.getLogger()
    logger.setLevel(args.log_level)

    node_endpoints = [] if args.endpoint is None else [ZMQAddress(addr) for addr in args.endpoint]
    if not reduce(lambda result, addr: result or addr.domain == AddressDomain.LOCAL,
                  node_endpoints, False):
        node_endpoints.append(local_address)
    if not reduce(lambda result, addr: result or addr.domain == AddressDomain.NODE,
                  node_endpoints, False):
        node_endpoints.append(node_address)
    node_cfg: ServiceConfig = SERVICE_DESCRIPTOR.config()
    node_cfg.endpoints.set_value(node_endpoints)

    node_implementation: SimpleServiceImpl = \
        load(SERVICE_DESCRIPTOR.implementation)(SERVICE_DESCRIPTOR, stop_event)
    node_implementation.peer = PeerDescriptor(uuid1(), getpid(), platform.node())
    node_service:BaseService = \
        load(SERVICE_DESCRIPTOR.container)(node_implementation, zmq.Context.instance(),
                                            node_cfg)
    node_service.initialize()
    try:
        args = parser.parse_args()
        print(f"Saturnin node v{__VERSION__}")
        for addr in node_implementation.endpoints:
            print(f"Node address: {addr}")
        node_service.start()
    except Exception:
        logger.exception("Fatal exception, node terminated.")
    logging.shutdown()

if __name__ == '__main__':
    main()
