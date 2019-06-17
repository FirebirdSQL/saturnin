#!/usr/bin/python
#coding:utf-8
#
# PROGRAM/MODULE: Saturnin - utilities
# FILE:           saturni.utils.nodemngr.py
# DESCRIPTION:    Saturnin node manager (CLI version)
# CREATED:        14.6.2019
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

"""Saturnin - Node manager (CLI version)


"""

import logging
from argparse import ArgumentParser, Action
from saturnin.sdk.types import PeerDescriptor, ZMQAddress
from saturnin.service.node.client import SaturninNodeClient

__VERSION__ = '0.1'

# Classes

class UpperAction(Action):
    "Converts argument to uppercase."
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values.upper())

def main():
    "Main function"

    node = SaturninNodeClient()

    logging.basicConfig(format='%(levelname)s:%(threadName)s:%(name)s:%(message)s')
    description = """Saturnin node manager."""
    parser = ArgumentParser(description=description)
    parser.add_argument('-e', '--endpoint', nargs='+', help="ZMQ addresses for the service")
    parser.add_argument('-l', '--log-level', action=UpperAction,
                        choices=[x.lower() for x in logging._nameToLevel
                                 if isinstance(x, str)],
                        help="Logging level")
    parser.set_defaults(log_level='ERROR')
    args = parser.parse_args()
    logger = logging.getLogger()
    logger.setLevel(args.log_level)

    #node.
    print('Done.')

if __name__ == '__main__':
    main()
