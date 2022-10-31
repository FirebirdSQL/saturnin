#!/usr/bin/env python
#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin-setup.py
# DESCRIPTION:    Saturnin platform installation script
# CREATED:        9.2.2021
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

"""Saturnin platform installation script.


"""

from __future__ import annotations
from typing import Dict
import venv
import sys
import os
import subprocess
import platform
import ctypes
import enum
import argparse
from pathlib import Path

class SW(enum.IntEnum):
    "Windows ShellExecute options."
    HIDE = 0
    MAXIMIZE = 3
    MINIMIZE = 6
    RESTORE = 9
    SHOW = 5
    SHOWDEFAULT = 10
    SHOWMAXIMIZED = 3
    SHOWMINIMIZED = 2
    SHOWMINNOACTIVE = 7
    SHOWNA = 8
    SHOWNOACTIVATE = 4
    SHOWNORMAL = 1

class ERROR(enum.IntEnum):
    "Windows ShellExecute return codes."
    ZERO = 0
    FILE_NOT_FOUND = 2
    PATH_NOT_FOUND = 3
    BAD_FORMAT = 11
    ACCESS_DENIED = 5
    ASSOC_INCOMPLETE = 27
    DDE_BUSY = 30
    DDE_FAIL = 29
    DDE_TIMEOUT = 28
    DLL_NOT_FOUND = 32
    NO_ASSOC = 31
    OOM = 8
    SHARE = 26

def elevate(*args, **kwargs):
    """Runs main() with elevated privileges if necessary.
    """
    if platform.system() == 'Windows':
        if ctypes.windll.shell32.IsUserAnAdmin():
            main(*args, **kwargs)
            return True
        hinstance = ctypes.windll.shell32.ShellExecuteW(
            None,
            'runas',
            sys.executable,
            subprocess.list2cmdline(sys.argv),
            None,
            SW.SHOWNORMAL
        )
        if hinstance <= 32:
            raise RuntimeError(ERROR(hinstance))
        return False
    # Not Windows
    main(*args, **kwargs)
    return True

# copied from firebird.base.config
class DirectoryScheme:
    """Class that provide paths to typically used application directories.

    Default scheme uses HOME directory as root for other directories. The HOME is
    determined as follows:

    1. If environment variable "<app_name>_HOME" exists, its value is used as HOME directory.
    2. HOME directory is set to current working directory.

    Note:
        All paths are set when the instance is created and can be changed later.
    """
    def __init__(self, name: str, version: str=None):
        """
        Arguments:
            name: Appplication name.
            version: Application version.
        """
        self.name: str = name
        self.version: str = version
        home = self.home
        self.dir_map: Dict[str, Path] = {'config': home / 'config',
                                         'run_data': home / 'run_data',
                                         'logs': home / 'logs',
                                         'data': home / 'data',
                                         'tmp': home / 'tmp',
                                         'cache': home / 'cache',
                                         'srv': home / 'srv',
                                         'user_config': home / 'user_config',
                                         'user_data': home / 'user_data',
                                         'user_sync': home / 'user_sync',
                                         'user_cache': home / 'user_cache',
                                      }
    def has_home_env(self) -> bool:
        """Returns True if HOME directory is set by "<app_name>_HOME" environment variable.
        """
        return os.getenv(f'{self.name.upper()}_HOME') is not None
    @property
    def home(self) -> Path:
        """HOME directory. Either path set by "<app_name>_HOME" environment variable, or
        current working directory.
        """
        home = os.getenv(f'{self.name.upper()}_HOME')
        return Path(home) if home is not None else Path(os.getcwd())
    @property
    def config(self) -> Path:
        """Directory for host-specific system-wide configuration files.
        """
        return self.dir_map['config']
    @config.setter
    def config(self, path: Path) -> None:
        self.dir_map['config'] = path
    @property
    def run_data(self) -> Path:
        """Directory for run-time variable data that may not persist over boot.
        """
        return self.dir_map['run_data']
    @run_data.setter
    def run_data(self, path: Path) -> None:
        self.dir_map['run_data'] = path
    @property
    def logs(self) -> Path:
        """Directory for log files.
        """
        return self.dir_map['logs']
    @logs.setter
    def logs(self, path: Path) -> None:
        self.dir_map['logs'] = path
    @property
    def data(self) -> Path:
        """Directory for state information / persistent data modified by application as
        it runs.
        """
        return self.dir_map['data']
    @data.setter
    def data(self, path: Path) -> None:
        self.dir_map['data'] = path
    @property
    def tmp(self) -> Path:
        """Directory for temporary files to be preserved between reboots.
        """
        return self.dir_map['tmp']
    @tmp.setter
    def tmp(self, path: Path) -> None:
        self.dir_map['tmp'] = path
    @property
    def cache(self) -> Path:
        """Directory for application cache data.

        Such data are locally generated as a result of time-consuming I/O or calculation.
        The application must be able to regenerate or restore the data. The cached files
        can be deleted without loss of data.
        """
        return self.dir_map['cache']
    @cache.setter
    def cache(self, path: Path) -> None:
        self.dir_map['cache'] = path
    @property
    def srv(self) -> Path:
        """Directory for site-specific data served by this system, such as data and
        scripts for web servers, data offered by FTP servers, and repositories for
        version control systems etc.
        """
        return self.dir_map['srv']
    @srv.setter
    def srv(self, path: Path) -> None:
        self.dir_map['srv'] = path
    @property
    def user_config(self) -> Path:
        """Directory for user-specific configuration.
        """
        return self.dir_map['user_config']
    @user_config.setter
    def user_config(self, path: Path) -> None:
        self.dir_map['user_config'] = path
    @property
    def user_data(self) -> Path:
        """Directory for User local data.
        """
        return self.dir_map['user_data']
    @user_data.setter
    def user_data(self, path: Path) -> None:
        self.dir_map['user_data'] = path
    @property
    def user_sync(self) -> Path:
        """Directory for user data synced accross systems (roaming).
        """
        return self.dir_map['user_sync']
    @user_sync.setter
    def user_sync(self, path: Path) -> None:
        self.dir_map['user_sync'] = path
    @property
    def user_cache(self) -> Path:
        """Directory for user-specific application cache data.
        """
        return self.dir_map['user_cache']
    @user_cache.setter
    def user_cache(self, path: Path) -> None:
        self.dir_map['user_cache'] = path


class WindowsDirectoryScheme(DirectoryScheme):
    """Directory scheme that conforms to Windows standards.

    If HOME is defined using "<app_name>_HOME" environment variable, only user-specific
    directories and TMP are set according to platform standars, while general directories
    remain as defined by base `DirectoryScheme`.
    """
    def __init__(self, name: str, version: str=None):
        """
        Arguments:
            name: Appplication name.
            version: Application version.
        """
        super().__init__(name, version)
        app_dir = Path(self.name)
        if self.version is not None:
            app_dir /= self.version
        p_data = Path(os.path.expandvars('%PROGRAMDATA%'))
        la_data = Path(os.path.expandvars('%LOCALAPPDATA%'))
        a_data = Path(os.path.expandvars('%APPDATA%'))
        # Set general directories only when HOME is not forced by environment variable.
        if not self.has_home_env():
            self.dir_map.update({'config': p_data / app_dir / 'config',
                                 'run_data': p_data / app_dir / 'run',
                                 'logs': p_data / app_dir / 'log',
                                 'data': p_data / app_dir / 'data',
                                 'cache': p_data / app_dir / 'cache',
                                 'srv': p_data / app_dir / 'srv',
                                 })
        # Always set user-specific directories and TMP
        self.dir_map.update({'tmp': la_data / app_dir / 'tmp',
                             'user_config': la_data / app_dir / 'config',
                             'user_data': la_data / app_dir / 'data',
                             'user_sync': a_data / app_dir,
                             'user_cache': la_data / app_dir / 'cache',
                             })

class LinuxDirectoryScheme(DirectoryScheme):
    """Directory scheme that conforms to Linux standards.

    If HOME is defined using "<app_name>_HOME" environment variable, only user-specific
    directories and TMP are set according to platform standars, while general directories
    remain as defined by base `DirectoryScheme`.
    """
    def __init__(self, name: str, version: str=None):
        """
        Arguments:
            name: Appplication name.
            version: Application version.
        """
        super().__init__(name, version)
        app_dir = Path(self.name)
        if self.version is not None:
            app_dir /= self.version
        # Set general directories only when HOME is not forced by environment variable.
        if not self.has_home_env():
            self.dir_map.update({'config': Path('/etc') / app_dir,
                                 'run_data': Path('/run') / app_dir,
                                 'logs': Path('/var/log') / app_dir,
                                 'data': Path('/var/lib') / app_dir,
                                 'cache': Path('/var/cache') / app_dir,
                                 'srv': Path('/srv') / app_dir,
                                 })
        # Always set user-specific directories and TMP
        self.dir_map.update({'tmp': Path('/var/tmp') / app_dir,
                             'user_config': Path('~/.config').expanduser() / app_dir,
                             'user_data': Path('~/.local/share').expanduser() / app_dir,
                             'user_sync': Path('~/.local/sync').expanduser() / app_dir,
                             'user_cache': Path('~/.cache').expanduser() / app_dir,
                             })

class MacOSDirectoryScheme(DirectoryScheme):
    """Directory scheme that conforms to MacOS standards.

    If HOME is defined using "<app_name>_HOME" environment variable, only user-specific
    directories and TMP are set according to platform standars, while general directories
    remain as defined by base `DirectoryScheme`.
    """
    def __init__(self, name: str, version: str=None):
        """
        Arguments:
            name: Appplication name.
            version: Application version.
        """
        super().__init__(name, version)
        app_dir = Path(self.name)
        if self.version is not None:
            app_dir /= self.version
        p_data = Path('/Library/Application Support')
        l_data = Path('~/Library/Application Support').expanduser()
        # Set general directories only when HOME is not forced by environment variable.
        if not self.has_home_env():
            self.dir_map.update({'config': p_data / app_dir / 'config',
                                 'run_data': p_data / app_dir / 'run',
                                 'logs': p_data / app_dir / 'log',
                                 'data': p_data / app_dir / 'data',
                                 'cache': p_data / app_dir / 'cache',
                                 'srv': p_data / app_dir / 'srv',
                                 })
        # Always set user-specific directories and TMP
        self.dir_map.update({'tmp': Path(os.getenv('TMPDIR')) / app_dir,
                             'user_config': l_data / app_dir / 'config',
                             'user_data': l_data / app_dir / 'data',
                             'user_sync': l_data / app_dir,
                             'user_cache': Path('~/Library/Caches').expanduser()
                             / app_dir / 'cache',
                             })

def get_directory_scheme(app_name: str, version: str=None) -> DirectoryScheme:
    """Returns directory scheme for current platform.
    """
    return {'Windows': WindowsDirectoryScheme,
            'Linux':LinuxDirectoryScheme,
            'Darwin': MacOSDirectoryScheme}.get(platform.system(),
                                                DirectoryScheme)(app_name, version)

# copied from saturnin.site
SATURNIN_CFG = 'saturnin.conf'

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
        """Saturni site configuration file.
        """
        return self.config / SATURNIN_CFG
    @property
    def user_conf(self) -> Path:
        """Saturnin user configuration file.
        """
        return self.user_config / SATURNIN_CFG

#

class ExtendedEnvBuilder(venv.EnvBuilder):
    """Extended virtual env. builder."""
    def post_setup(self, context):
        print("Updating package management...")
        bin_path = Path(context.bin_path)
        self.bin_path = bin_path
        subprocess.run([str(bin_path / 'pip'),'install','-U','pip','setuptools','wheel'],
                       stdout=sys.stdout,stderr=sys.stderr)


def init(args=None):
    """
    """
    compatible = True
    if sys.version_info < (3, 8):
        compatible = False
    elif not hasattr(sys, 'base_prefix'):
        compatible = False
    if not compatible:
        raise ValueError('This script is only for use with Python >= 3.8')
    #
    parser = argparse.ArgumentParser(prog='saturnin-setup',
                                     description='Installs Saturnin in separate '
                                                 'virtual Python environment')
    parser.add_argument('--home', metavar='PATH',
                        help='Saturnin HOME directory.')
    parser.add_argument('--prompt', default='saturnin',
                        help='Provides an alternative prompt prefix for '
                             'Saturnin environment.')
    if platform.system() == 'Windows':
        parser.add_argument('--no-shortcut', default=False, action='store_true',
                            help='Do not create desktop shortcut.')
    parser.add_argument('--system-site-packages', default=False,
                        action='store_true', dest='system_site',
                        help='Give the virtual environment access to the '
                             'system site-packages dir.')
    if platform.system() == 'Windows':
        use_symlinks = False
    else:
        use_symlinks = True
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--symlinks', default=use_symlinks,
                       action='store_true', dest='symlinks',
                       help='Try to use symlinks rather than copies, '
                            'when symlinks are not the default for '
                            'the platform.')
    group.add_argument('--copies', default=not use_symlinks,
                       action='store_false', dest='symlinks',
                       help='Try to use copies rather than symlinks, '
                            'even when symlinks are the default for '
                            'the platform.')
    parser.add_argument('--clear', default=False, action='store_true',
                        dest='clear', help='Delete the contents of the '
                                           'environment directory if it '
                                           'already exists, before '
                                           'environment creation.')
    parser.add_argument('--upgrade', default=False, action='store_true',
                        dest='upgrade', help='Upgrade the environment '
                                             'directory to use this version '
                                             'of Python, assuming Python '
                                             'has been upgraded in-place.')
    parser.add_argument('-f','--find-links', metavar='<url>',
                        help="If a URL or path to an html file, "
                        "then parse for links to archives such as sdist (.tar.gz) "
                        "or wheel (.whl) files. If a local path or file:// URL "
                        "that's a directory,  then look for archives in the directory "
                        "listing. Links to VCS project URLs are not supported.")
    return parser.parse_args(args)

def main(options):
    use_home = options.home is not None
    if options.upgrade and options.clear:
        raise ValueError('you cannot supply --upgrade and --clear together.')
    if use_home and os.getenv('SATURNIN_HOME') is not None:
        raise ValueError('you cannot supply --home when SATURNIN_HOME is defined.')
    if platform.system() == 'Windows' and not options.no_shortcut:
        try:
            import winreg
            from win32com.client import Dispatch
        except Exception as exc:
            raise ValueError("PyWin32 package not installed. "
                             "Execute 'pip install pywin32' or "
                             "use --no-shortcut option.") from exc
    #
    if use_home:
        os.environ['SATURNIN_HOME'] = options.home
    scheme = get_directory_scheme('saturnin')
    venv_home = scheme.data / 'venv'
    # If venv already exists, either --upgrade or --clear is required
    if venv_home.is_dir() and not (options.upgrade or options.clear):
        raise ValueError("Target virtual environment already exists, "
                         "either --upgrade or --clear is required")
    #
    builder = ExtendedEnvBuilder(system_site_packages=options.system_site,
                                 clear=options.clear,
                                 symlinks=options.symlinks,
                                 upgrade=options.upgrade,
                                 with_pip=True,
                                 prompt=options.prompt)
    builder.bin_path: Path = None
    print("Creating Saturnin virtual environment...")
    builder.create(venv_home)
    home_file: Path = venv_home / '.saturnin-bin'
    home_file.write_text(str(builder.bin_path))
    if use_home:
        home_file: Path = venv_home / '.saturnin-home'
        home_file.write_text(options.home)
    print("Ensuring latest setuptools, pip and build...")
    cmd = [str(builder.bin_path / 'pip'), 'install', '-U', 'setuptools',
           'pip', 'build']
    if options.find_links is not None:
        cmd.extend(['-f', options.find_links])
    subprocess.run(cmd, stdout=sys.stdout,stderr=sys.stderr)
    print("Installing Saturnin...")
    cmd = [str(builder.bin_path / 'pip'), 'install']
    if options.find_links is not None:
        cmd.extend(['-f', options.find_links])
    cmd.append('saturnin>=0.7.0')
    subprocess.run(cmd, stdout=sys.stdout,stderr=sys.stderr)
    print("Saturnin site initialization...")
    cmd = [str(builder.bin_path / 'saturnin'), 'site', 'init']
    subprocess.run(cmd, stdout=sys.stdout,stderr=sys.stderr, check=True)
    if platform.system() == 'Windows' and not options.no_shortcut:
        print("Creating desktop shortcut...")
        pth = r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders'
        registry_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, pth, 0,
                                      winreg.KEY_READ)
        reg_value, _ = winreg.QueryValueEx(registry_key, 'Common Desktop')
        winreg.CloseKey(registry_key)
        desktop_dir = os.path.normpath(reg_value)
        shortcut_path = os.path.expandvars(os.path.join(desktop_dir,
                                                        'saturnin-shell.lnk'))
        #
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.Description = 'Saturnin shell'
        shortcut.TargetPath = 'cmd.exe'
        shortcut.Arguments = f"/K {str(venv_home / 'Scripts' / 'activate.bat')}"
        shortcut.save()

if __name__ == '__main__':
    return_code = 1
    elevated = False
    try:
        options = init()
        elevated = elevate(options)
        return_code = 0
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
    else:
        if elevated:
            print("\nSaturnin installation complete!")
            print(input('Press any key...'))
    sys.exit(return_code)
