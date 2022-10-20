#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/_scripts/site.py
# DESCRIPTION:    Script for Saturnin site manager
# CREATED:        11.3.2021
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
# Copyright (c) 2021 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________

"""saturnin - Script for Saturnin site manager


"""

from __future__ import annotations
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from saturnin.lib.command import CommandManager

#: Program name
PROG_NAME = 'saturnin-site'

def main():
    """Saturnin site manager.
    """
    parser: ArgumentParser = ArgumentParser(PROG_NAME, description=main.__doc__,
                                            formatter_class=ArgumentDefaultsHelpFormatter,
                                            usage="\n  saturnin-site <command> [options]")
    cmds = CommandManager(parser)
    cmds.load_commands('saturnin.commands.site')
    cmds.run()

if __name__ == '__main__':
    main()
