#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/_scripts/init.py
# DESCRIPTION:    Script for Saturnin platform deployment initialization
# CREATED:        19.1.2021
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

"""Saturnin platform deployment initialization script


"""

from __future__ import annotations
from traceback import format_exception_only
from argparse import ArgumentParser, Namespace # , ArgumentDefaultsHelpFormatter
from pathlib import Path
#from site import getsitepackages
#from saturnin.core import Error
from saturnin.base.site import site, CONFIG_HDR

PROG_NAME = 'saturnin-init'



class Script:
    """Saturnin platform initialization.
    """
    def __init__(self):
        ""
    def out(self, msg: str) -> None:
        ""
        print(msg, end='', flush=True)
    def init_directories(self, args: Namespace) -> None:
        ""
        def ensure_dir(name: str, path: Path):
            self.out(f"{name}: {path} ... ")
            if not path.exists():
                path.mkdir(parents=True)
            self.out("OK\n")

        self.out('Saturnin directories...\n')
        if site.scheme.has_home_env():
            print(f"  SATURNIN_HOME is set to     : {site.scheme.home}")
        else:
            print("  SATURNIN_HOME env. variable not defined")
        ensure_dir("  Saturnin configuration      ", site.scheme.config)
        ensure_dir("  Saturnin data               ", site.scheme.data)
        ensure_dir("  Run-time data               ", site.scheme.run_data)
        ensure_dir("  Log files                   ", site.scheme.logs)
        ensure_dir("  Temporary files             ", site.scheme.tmp)
        ensure_dir("  Cache                       ", site.scheme.cache)
        ensure_dir("  User-specific configuration ", site.scheme.user_config)
        ensure_dir("  User-specific data          ", site.scheme.user_data)
        #ensure_dir("  Python virtual environment  ", site.scheme.venv)
        ensure_dir("  PID files                   ", site.scheme.pids)
    def create_config_files(self, args: Namespace) -> None:
        ""
        self.out("Creating configuration files...\n")
        self.out(f"  Writing : {site.scheme.site_conf} ... ")
        cfg = CONFIG_HDR + site.config.get_config()
        site.scheme.site_conf.write_text(cfg)
        self.out("OK\n")
        self.out(f"  Writing : {site.scheme.user_conf} ... ")
        site.scheme.user_conf.write_text(cfg)
        self.out("OK\n")
    def run(self) -> None:
        ""
        parser: ArgumentParser = ArgumentParser(PROG_NAME, description=self.__doc__)
        parser.add_argument('--make-dirs', action='store_true',
                            help="Create saturnin directories", default=None)
        parser.add_argument('--config-files', action='store_true',
                            help="Create configuration files", default=None)
        try:
            args = parser.parse_args()
            no_args = True
            for k in vars(args):
                if getattr(args, k) is not None:
                    no_args = False
                    break
            if no_args or args.make_dirs:
                self.init_directories(args)
            if no_args or args.config_files:
                self.create_config_files(args)
        except Exception as exc:
            self.out("ERROR\n")
            msg = ''.join(format_exception_only(type(exc), exc))
            _, msg = msg.split(': ', 1)
            parser.exit(1, msg)

def main():
    script = Script()
    script.run()

if __name__ == '__main__':
    main()

