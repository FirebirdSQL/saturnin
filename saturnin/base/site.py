#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/site.py
# DESCRIPTION:    Saturnin site
# CREATED:        7.12.2020
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

"""Saturnin site contains code for configuration and management of Saturnin installation.

"""

from __future__ import annotations
from typing import List, Optional
import sys
import os
from pathlib import Path
from configparser import ConfigParser, ExtendedInterpolation
from rich.console import Console
from rich.theme import Theme
from firebird.base.config import DirectoryScheme, get_directory_scheme, Config, StrOption
from firebird.base.logging import LoggingIdMixin
from .types import Error

#: filename for Saturnin configuration file
SATURNIN_CFG = 'saturnin.conf'
#: filename for Firebird configuration file
FIREBIRD_CFG = 'firebird.conf'
#: filename for logging configuration file
LOGGING_CFG = 'logging.conf'
#: Saturnin configuration file header
CONFIG_HDR = """;
; A configuration file consists of sections, each led by a [section] header, followed by
; key/value entries separated by = or : string. Section names are case sensitive but keys
; are not. Leading and trailing whitespace is removed from keys and values. Values can be
; omitted, in which case the key/value delimiter may also be left out. Values can also
; span multiple lines, as long as they are indented deeper than the first line of the value.
;
; Configuration files may include comments, prefixed by # and ; characters. Comments may
; appear on their own on an otherwise empty line, possibly indented.
;
; Values can contain ${section:option} format strings which refer to other values.
; If the section: part is omitted, interpolation defaults to the current section (and possibly
; the default values from the special DEFAULT section). Interpolation can span multiple levels.

"""

_theme = Theme({"option": "bold cyan",
                "switch": "bold green",
                "metavar": "bold yellow",
                "help_require": "dim",
                "args_and_cmds": "yellow"
                })

FORCE_TERMINAL = True if os.getenv("FORCE_COLOR") or os.getenv("PY_COLORS") else None

class SaturninScheme(DirectoryScheme):
    """Saturnin platform directory scheme.
    """
    def __init__(self):
        super().__init__('saturnin')
        self.dir_map.update(get_directory_scheme('saturnin').dir_map)
    @property
    def pids(self) -> Path:
        """Path to directory with PID files for running daemons.
        """
        return self.run_data / 'pids'
    @property
    def site_components_toml(self) -> Path:
        """Saturnin package registry file.
        """
        return self.data / 'components.toml'
    @property
    def site_conf(self) -> Path:
        """Saturnin site configuration file.
        """
        return self.config / SATURNIN_CFG
    @property
    def user_conf(self) -> Path:
        """Saturnin user configuration file.
        """
        return self.user_config / SATURNIN_CFG
    @property
    def firebird_conf(self) -> Path:
        """Firebird driver configuration file.
        """
        return self.config / FIREBIRD_CFG
    @property
    def logging_conf(self) -> Path:
        """Python logging configuration file.
        """
        return self.config / LOGGING_CFG

class SaturninConfig(Config):
    """Saturnin (a Firebird Butler platform) configuration.
    """
    def __init__(self):
        super().__init__('saturnin')
        #: External editor
        self.editor: StrOption = StrOption('editor', "External editor",
                                           default=os.getenv('EDITOR'))

class SiteManager(LoggingIdMixin):
    """Saturnin site manager.
    """
    def __init__(self):
        # Path to pip
        self.pip_path: Path = 'pip'
        # Set SATUTNIN_HOME if defined in virtual environment
        if self.is_virtual():
            path: Path = self.venv / '.saturnin-home'
            if path.is_file():
                os.environ['SATURNIN_HOME'] = path.read_text()
            path = self.venv / '.saturnin-bin'
            if path.is_file():
                self.pip_path = Path(path.read_text()) / 'pip'
        #: Saturnin directory scheme
        self.scheme: SaturninScheme = SaturninScheme()
        #: Saturnin configuration
        self.config: SaturninConfig = SaturninConfig()
        #: Used configuration files
        self.used_config_files: List[Path] = []
        self.quiet: bool = False
        self.verbose: bool = False
        self.console = Console(theme=_theme, emoji=False, tab_size=4,
                               force_terminal=FORCE_TERMINAL)
        if not sys.stdout.isatty():
            self.console.width = 5000
        self.err_console = Console(stderr=True, style='bold red', emoji=False, tab_size=4,
                                   force_terminal=FORCE_TERMINAL)

    def print_info(self, message = '') -> None:
        "Prints information message to console."
        if message:
            #self.logger.info(message)
            if self.verbose:
                self.console.print(message, style='yellow')
        else:
            if self.verbose:
                self.console.print()
    def print_error(self, message) -> None:
        "Prints error message to error console."
        #self.logger.error(message)
        self.err_console.print(message)
    def print_exception(self) -> None:
        "Prints exception to error console."
        #self.logger.exception(message)
        self.err_console.print_exception()
    def print(self, message = '', end='\n') -> None:
        "Prints message to console."
        if not self.quiet:
            self.console.print(message, end=end)
    def load_configuration(self) -> None:
        """Loads the configuration from configuration files.
        """
        parser: ConfigParser = ConfigParser(interpolation=ExtendedInterpolation())
        for _file in parser.read([self.scheme.site_conf,
                              self.scheme.user_conf]):
            self.used_config_files.append(Path(_file))
        if parser.has_section('saturnin'):
            self.config.load_config(parser)
    def initialize(self) -> None:
        """Saturnin site initialization.
        """
        self.load_configuration()
    def is_virtual(self) -> bool:
        """Returns True if site runs in a virtual environtment.
        """
        # Check supports venv && virtualenv >= 20.0.0
        return getattr(sys, 'base_prefix', sys.prefix) != sys.prefix
    def configure_firebird_driver(self) -> None:
        """Configure the firebird-driver.
        """
        try:
            from firebird.driver import driver_config # pylint: disable=C0415
        except ImportError as exc:
            raise Error("Firebird driver not installed.") from exc
        driver_config.read(self.scheme.firebird_conf, encoding='utf8')
    @property
    def venv(self) -> Optional[Path]:
        """Path to Saturnin virtual environment.
        """
        return Path(sys.prefix) if self.is_virtual() else None

#: Saturnin site manager
site: SiteManager = SiteManager()
site.initialize()
