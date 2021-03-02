#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/_scripts/commands/pkg.py
# DESCRIPTION:    Saturnin package manager commands
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

"""Saturnin package manager commands


"""

from __future__ import annotations
from typing import Dict, List, Optional
import sys
import toml
import zipfile
import subprocess
from pathlib import Path
from packaging import version
from argparse import ArgumentParser, Namespace, REMAINDER
from configparser import ConfigParser, ExtendedInterpolation
from saturnin.base import Error, site
from saturnin.lib.command import Command, CommandManager
from saturnin.lib.pyproject import PyProjectTOML

PKG_TOML = 'pyproject.toml'
SETUP_CFG = 'setup.cfg'
SEC_OPTIONS = 'options'
SEC_ENTRYPOINTS = 'options.entry_points'

# Component registry TOML structure
#
# [[components]]
# uid = component GUID
# component-type = 'service' or 'app'
# package = normalized component name
# name = component name
# version = component version
# description = component description
# descriptor = locator string for component descriptor (incl. top level package)
# top-level = top level package with component

CMP_UID = 'uid'
CMP_PACKAGE = 'package'
CMP_NAME = 'name'
CMP_VERSION = 'version'
CMP_DESCRIPTION = 'description'
CMP_DESCRIPTOR = 'descriptor'
CMP_TOPLEVEL = 'top-level'

class BasePkgCommand(Command):
    """Base class for saturnin-pkg commands.
    """
    def __init__(self, name: str, description: str):
        super().__init__(name, description)
        self.components: List[Dict]= []
    def load_components(self) -> None:
        if site.scheme.site_components_toml.is_file():
            self.components.extend(toml.load(site.scheme.site_components_toml)['components'])
    def save_components(self) -> None:
        site.scheme.site_components_toml.write_text(toml.dumps({'components': self.components}))
    def get_new_toplevel(self) -> str:
        ids = [int(s[1:]) for s in (c['top-level'] for c in self.components)]
        i = 1
        while i in ids:
            i += 1
        return f'C{i:05}'
    def find_component_index(self, *, uid: str=None, name: str=None, package: str=None) -> int:
        if uid is not None:
            key = CMP_UID
            value = uid
        elif name is not None:
            key = CMP_NAME
            value = name
        elif package is not None:
            key = CMP_PACKAGE
            value = package
        else:
            raise ValueError("Missing lookup key specification")
        for i in range(len(self.components)):
            if value == self.components[i][key]:
                return i
        return -1
    def find_component(self, *, uid: str=None, name: str=None, package: str=None) -> Optional[Dict]:
        i = self.find_component_index(uid=uid, name=name, package=package)
        return None if i < 0 else self.components[i]

class InstallCommand(BasePkgCommand):
    """saturnin-pkg INSTALL command.

    Installation of Saturnin packages.
    """
    def __init__(self):
        super().__init__('install', "Install Saturnin ZIP package.")
    def copy_tree(self, package: Path, path: zipfile.Path, skip_list: List[str]=[]):
        ""
        package.mkdir(exist_ok=True)
        for item in path.iterdir():
            if item.is_dir():
                self.copy_tree(package / item.name, item)
            elif item.name not in skip_list:
                target = package / item.name
                target.write_bytes(item.read_bytes())
    def set_arguments(self, manager: CommandManager, parser: ArgumentParser) -> None:
        """Set command arguments.
        """
        parser.add_argument('package', help="Saturnin ZIP package")
        parser.add_argument('args', nargs=REMAINDER, help="Arguments for 'pip install'")
    def run(self, args: Namespace) -> None:
        """Command execution.

        Arguments:
            args: Collected argument values.
        """
        pkg = Path(args.package)
        if not pkg.is_file():
            raise ValueError("File not found")
        self.load_components()
        with zipfile.ZipFile(pkg) as zf:
            root = zipfile.Path(zf)
            pkg_info = root / PKG_TOML
            if pkg_info.exists():
                # Single-service package
                self.install_package(args.args, zf, root)
            else:
                # Service bundle, each subdirectory should contain one service
                for pkg in root.iterdir():
                    pkg_info = pkg / PKG_TOML
                    if pkg_info.exists():
                        self.install_package(args.args, zf, pkg)
    def remove_dir(self, path: Path) -> None:
        if isinstance(path, str):
            path = Path(path)
        paths = list(path.rglob('*'))
        paths.reverse()
        for p in paths:
            if p.is_file():
                p.unlink()
            else:
                p.rmdir()
        path.rmdir()
    def install_package(self, args: List, zfile: zipfile.ZipFile, path: zipfile.Path):
        work_dir = site.scheme.tmp / 'import'
        if work_dir.exists():
            self.remove_dir(work_dir)
        work_dir.mkdir()
        #
        root_files = [PKG_TOML]
        # pyproject.toml
        pkg_file: zipfile.Path = path / PKG_TOML
        if not pkg_file.exists():
            raise Error(f"Invalid package: File {_file} not found")
        toml_data = pkg_file.read_text()
        pkg_toml: PyProjectTOML = PyProjectTOML(toml.loads(toml_data))
        self.out(f"Found: {pkg_toml.original_name}-{pkg_toml.version}\n")
        #
        add_component = False
        cmp: Dict = self.find_component(uid=pkg_toml.uid)
        if cmp is None:
            cmp = {}
            top_level = self.get_new_toplevel()
            cmp[CMP_UID] = pkg_toml.uid
            cmp[CMP_NAME] = pkg_toml.original_name
            cmp[CMP_PACKAGE] = pkg_toml.name
            cmp[CMP_VERSION] = pkg_toml.version
            cmp[CMP_DESCRIPTION] = pkg_toml.description
            cmp[CMP_DESCRIPTOR] = f'{top_level}.{pkg_toml.descriptor}'
            cmp[CMP_TOPLEVEL] = top_level
            add_component = True
        else:
            top_level = cmp[CMP_TOPLEVEL]
            vn = version.parse(pkg_toml.version)
            vo = version.parse(cmp[CMP_VERSION])
            if vn < vo:
                self.out(f"Newer version {cmp[CMP_VERSION]} already installed\n")
                return
            elif vn == vo:
                self.out(f"Version {cmp[CMP_VERSION]} already installed\n")
                return
            cmp[CMP_NAME] = pkg_toml.original_name
            cmp[CMP_PACKAGE] = pkg_toml.name
            cmp[CMP_VERSION] = pkg_toml.version
            cmp[CMP_DESCRIPTION] = pkg_toml.description
            cmp[CMP_DESCRIPTOR] = f'{top_level}.{pkg_toml.descriptor}'
        # write toml
        target: Path = work_dir / PKG_TOML
        target.write_text(toml_data)
        # setup.cfg
        cfg: ConfigParser = ConfigParser(interpolation=ExtendedInterpolation())
        pkg_file = path / SETUP_CFG
        if pkg_file.exists():
            root_files.append(SETUP_CFG)
            cfg.read_string(pkg_file.read_text())
        pkg_toml.make_setup_cfg(cfg)
        if not cfg.has_section(SEC_OPTIONS):
            cfg.add_section(SEC_OPTIONS)
        cfg[SEC_OPTIONS]['packages'] = top_level
        if not cfg.has_section(SEC_ENTRYPOINTS):
            cfg.add_section(SEC_ENTRYPOINTS)
        if pkg_toml.component_type == 'service':
            cfg[SEC_ENTRYPOINTS]['saturnin.service'] = f'\n{cmp[CMP_UID]} = {cmp[CMP_DESCRIPTOR]}'
        elif pkg_toml.component_type == 'application':
            cfg[SEC_ENTRYPOINTS]['saturnin.application'] = f'\n{cmp[CMP_UID]} = {cmp[CMP_DESCRIPTOR]}'
        target = work_dir / SETUP_CFG
        with target.open('w') as f:
            cfg.write(f)
        # README
        if pkg_toml.readme is not None:
            readme_file = None
            if isinstance(pkg_toml.readme, str):
                readme_file = pkg_toml.readme
            elif 'file' in pkg_toml.readme:
                readme_file = pkg_toml.readme['file']
            if readme_file is not None:
                root_files.append(readme_file)
                target = work_dir / readme_file
                pkg_file = path / readme_file
                target.write_bytes(pkg_file.read_bytes())
        # LICENSE
        if pkg_toml.license is not None:
            if (license_file := pkg_toml.license.get('file')) is not None:
                root_files.append(license_file)
                target = work_dir / license_file
                pkg_file = path / license_file
                target.write_bytes(pkg_file.read_bytes())
        # copy files to top-level
        self.copy_tree(work_dir / top_level, path, root_files)
        # Run pip to install prepared package
        pip_cmd = [str(site.pip_path), 'install']
        pip_cmd.extend(args)
        pip_cmd.append(str(work_dir))
        try:
            subprocess.run(pip_cmd, stdout=sys.stdout, stderr=sys.stderr,
                           check=True, text=True)
        except subprocess.CalledProcessError:
            print('Component installation failed')
            raise
        else:
            if add_component:
                self.components.append(cmp)
            self.save_components()

class UninstallCommand(BasePkgCommand):
    """saturnin-pkg UNINSTALL command.

    Uninstallation of Saturnin components.
    """
    def __init__(self):
        super().__init__('uninstall', "Uninstall Saturnin component.")
    def set_arguments(self, manager: CommandManager, parser: ArgumentParser) -> None:
        """Set command arguments.
        """
        parser.add_argument('component', help="Component name")
    def run(self, args: Namespace) -> None:
        """Command execution.

        Arguments:
            args: Collected argument values.
        """
        self.load_components()
        i = self.find_component_index(name=args.component)
        if i < 0:
            raise ValueError("Component not found.")
        cmp = self.components.pop(i)
        # Run pip to uninstall package
        try:
            subprocess.run([str(site.pip_path), 'uninstall', '-y', cmp[CMP_PACKAGE]],
                           stdout=sys.stdout, stderr=sys.stderr,
                           check=True, text=True)
        except subprocess.CalledProcessError:
            print('Component uninstallation failed')
            raise
        #
        self.save_components()

class ListCommand(BasePkgCommand):
    """saturnin-pkg LIST command.

    List installed Saturnin components.
    """
    def __init__(self):
        super().__init__('list', "List installed Saturnin components.")
    def set_arguments(self, manager: CommandManager, parser: ArgumentParser) -> None:
        """Set command arguments.
        """
    def run(self, args: Namespace) -> None:
        """Command execution.

        Arguments:
            args: Collected argument values.
        """
        self.load_components()
        self.print_table(['Component', 'Version', 'Package'],
                         [[cmp[CMP_NAME], cmp[CMP_VERSION], cmp[CMP_PACKAGE]]
                          for cmp in self.components])

class PipCommand(BasePkgCommand):
    """saturnin-pkg PIP command.

    Run pip from Saturnin virtual environment.
    """
    def __init__(self):
        super().__init__('pip', "Run pip from Saturnin virtual environment.")
    def set_arguments(self, manager: CommandManager, parser: ArgumentParser) -> None:
        """Set command arguments.
        """
        parser.add_argument('args', nargs=REMAINDER, help="Arguments for pip")
    def run(self, args: Namespace) -> None:
        """Command execution.

        Arguments:
            args: Collected argument values.
        """
        # Run pip to uninstall package
        pip_cmd = [str(site.pip_path)]
        pip_cmd.extend(args.args)
        try:
            subprocess.run(pip_cmd, stdout=sys.stdout, stderr=sys.stderr,
                           check=True, text=True)
        except subprocess.CalledProcessError:
            print('pip execution failed')
            raise
