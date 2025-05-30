# SPDX-FileCopyrightText: 2023-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/base/config.py
# DESCRIPTION:    Saturnin configuration
# CREATED:        6.2.2023
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
# Copyright (c) 2023 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________

"""Code for configuration of Saturnin installation.

Handles Saturnin platform configuration, including directory schemes, configuration file
loading, and environment detection (e.g., virtual environments).
"""

from __future__ import annotations

import os
import sys
import sysconfig
from configparser import ConfigParser
from pathlib import Path
from typing import Final

from firebird.base.config import (Config, DirectoryScheme, StrOption, get_directory_scheme,
                                  EnvExtendedInterpolation)

#: filename for Saturnin configuration file
SATURNIN_CFG: Final[str] = 'saturnin.conf'
#: filename for Firebird configuration file
FIREBIRD_CFG: Final[str] = 'firebird.conf'
#: filename for logging configuration file
LOGGING_CFG: Final[str] = 'logging.conf'
#: Saturnin configuration file header
CONFIG_HDR: Final[str] = """;
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

#: True if current platform is Windows
WINDOWS: Final[bool] = sys.platform == "win32"
#: True if current platform is based on MINGW
MINGW: Final[bool] = sysconfig.get_platform().startswith("mingw")

class SaturninScheme(DirectoryScheme):
    """Saturnin platform directory scheme.

    When SATURNIN_HOME environment variable is not set, and Saturnin resides in virtual
    environment that contains `home` subdirectory, it's set as Saturnin HOME directory.

    This `home` subdirectory is created by `saturnin create home` command on request.
    """
    def __init__(self):
        super().__init__('saturnin')
        if not self.has_home_env() and is_virtual():
            home_dir: Path = venv() / 'home'
            if home_dir.is_dir():
                os.environ['SATURNIN_HOME'] = str(home_dir)
        self.dir_map.update(get_directory_scheme('saturnin').dir_map)
        self.__pip_path: Path | None = Path('pip')
        self.__pip_cmd: list[str] = ['pip']
        if is_virtual():
            root = venv()
            if WINDOWS:
                bin_path = root / "Scripts" if not MINGW else root / "bin"
                python_path = bin_path / "python.exe"
            else:
                bin_path = root / "bin"
                python_path = bin_path / "python"
            pip_path = bin_path / 'pip'
            if pip_path.is_file():
                self.__pip_path = pip_path
                self.__pip_cmd = [str(pip_path)]
            else:
                # No pip shortcut in venv, we must relly on python -m to run it, typical for pipx
                self.__pip_path = None
                self.__pip_cmd = [str(python_path), '-m', 'pip']
    def get_pip_cmd(self, *args) -> list[str]:
        """Returns a list representing the command to run pip, including any provided arguments.

        For example, `get_pip_cmd('install', 'requests')` might return
        `['/path/to/venv/bin/pip', 'install', 'requests']` or
        `['/path/to/venv/bin/python', '-m', 'pip', 'install', 'requests']`.

        Arguments:
           args: Additional arguments to be passed to the pip command.
        """
        result = self.__pip_cmd.copy()
        result.extend(args)
        return result
    @property
    def recipes(self) -> Path:
        """Path to directory with recipe files.
        """
        return self.data / 'recipes'
    @property
    def pids(self) -> Path:
        """Path to directory with PID files for running daemons.
        """
        return self.run_data / 'pids'
    @property
    def site_services_toml(self) -> Path:
        """Saturnin service registry file.
        """
        return self.data / 'services.toml'
    @property
    def site_apps_toml(self) -> Path:
        """Saturnin application registry file.
        """
        return self.data / 'apps.toml'
    @property
    def site_oids_toml(self) -> Path:
        """Saturnin OID registry file.
        """
        return self.data / 'oids.toml'
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
    @property
    def log_file(self) -> Path:
        """Saturnin log file.
        """
        return self.logs / 'saturnin.log'
    @property
    def history_file(self) -> Path:
        """Saturnin console command history file.
        """
        return self.data / 'saturnin.hist'
    @property
    def theme_file(self) -> Path:
        """Saturnin console theme file.
        """
        return self.config / 'theme.conf'
    @property
    def pip_path(self) -> Path:
        """Path to `pip`.
        """
        return self.__pip_path

class SaturninConfig(Config):
    """Saturnin (a Firebird Butler platform) configuration.
    """
    def __init__(self):
        super().__init__('saturnin')
        #: External editor
        self.editor: StrOption = StrOption('editor', "External editor",
                                           default=os.getenv('EDITOR'))

def is_virtual() -> bool:
    """Returns True if Saturnin runs in a virtual environment.
    """
    # Check supports venv && virtualenv >= 20.0.0
    return getattr(sys, 'base_prefix', sys.prefix) != sys.prefix

def venv() -> Path | None:
    """Returns the Path to the Saturnin virtual environment, orNone if not running in one.
    """
    return Path(sys.prefix) if is_virtual() else None

# Set SATURNIN_HOME if defined in virtual environment
if is_virtual():
    path: Path = venv() / 'home'
    if path.is_dir():
        os.environ['SATURNIN_HOME'] = str(path)

#: Active Saturnin directory scheme
directory_scheme: SaturninScheme = SaturninScheme()

#: Saturnin configuration object
saturnin_config: SaturninConfig = SaturninConfig()

parser: ConfigParser = ConfigParser(interpolation=EnvExtendedInterpolation())
parser.read([directory_scheme.site_conf, directory_scheme.user_conf])
if parser.has_section('saturnin'):
    saturnin_config.load_config(parser)
del parser
