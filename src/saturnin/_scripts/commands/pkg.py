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
from typing import Dict, List, Optional, Any
import sys
import zipfile
import subprocess
from pathlib import Path
import toml
from packaging import version
from rich.table import Table
import typer
from saturnin.base import Error, site
from saturnin.component.registry import get_service_desciptors
from saturnin.lib.pyproject import PyProjectTOML

app = typer.Typer(rich_markup_mode="rich", help="Package management.")

#: Package TOML file
PKG_TOML = 'pyproject.toml'

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

#: Component UID item
CMP_UID = 'uid'
#: Component PACKAGE item
CMP_PACKAGE = 'package'
#: Component NAME item
CMP_NAME = 'name'
#: Component VERSION item
CMP_VERSION = 'version'
#: Component DESCRIPTION item
CMP_DESCRIPTION = 'description'
#: Component DESCIPTOR item
CMP_DESCRIPTOR = 'descriptor'
#: Component TOP-LEVEL item
CMP_TOPLEVEL = 'top-level'

class PackageManager:
    """Saturnin package manager.
    """
    def __init__(self):
        self.components: List[Dict[str, Any]]= []
    def load_components(self) -> None:
        "Read information about installed components."
        self.components.clear()
        if site.scheme.site_components_toml.is_file():
            self.components.extend(toml.load(site.scheme.site_components_toml)['components'])
    def save_components(self) -> None:
        "Save information about installed components."
        site.scheme.site_components_toml.write_text(toml.dumps({'components': self.components}))
    def get_new_toplevel(self) -> str:
        "Return new top-level package name for component."
        ids = [int(s[1:]) for s in (c['top-level'] for c in self.components)]
        i = 1
        while i in ids:
            i += 1
        return f'C{i:05}'
    def find_component_index(self, *, uid: str=None, name: str=None, package: str=None) -> int:
        "Returns component registry index by uid, name or package."
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
        for i, cmp in enumerate(self.components):
            if value == cmp[key]:
                return i
        return -1
    def find_component(self, *, uid: str=None, name: str=None, package: str=None) -> Optional[Dict]:
        "Returns component by uid, name or package."
        i = self.find_component_index(uid=uid, name=name, package=package)
        return None if i < 0 else self.components[i]

mngr: PackageManager = PackageManager()

def copy_tree(package: Path, path: zipfile.Path, skip_list: Optional[List[str]]=None):
    "Copy package tree."
    if skip_list is None:
        skip_list = []
    package.mkdir(exist_ok=True)
    for item in path.iterdir():
        if item.is_dir():
            copy_tree(package / item.name, item)
        elif item.name not in skip_list:
            target = package / item.name
            target.write_bytes(item.read_bytes())

def remove_dir(path: Path) -> None:
    "revove directory incl. sub-dirs and files contained within."
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

def install_package(args: List, zfile: zipfile.ZipFile, path: zipfile.Path):
    "Install single package from zip file."
    work_dir = site.scheme.tmp / 'import'
    if work_dir.exists():
        remove_dir(work_dir)
    work_dir.mkdir()
    #
    root_files = [PKG_TOML]
    # pyproject.toml
    pkg_file: zipfile.Path = path / PKG_TOML
    if not pkg_file.exists():
        raise Error(f"Invalid package: File {PKG_TOML} not found")
    toml_data = toml.loads(pkg_file.read_text())
    pkg_toml: PyProjectTOML = PyProjectTOML(toml_data)
    site.print(f"Found: {pkg_toml.original_name}-{pkg_toml.version}")
    #
    add_component = False
    cmp: Dict[str, Any] = mngr.find_component(uid=pkg_toml.uid)
    if cmp is None:
        cmp = {}
        top_level = mngr.get_new_toplevel()
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
        new_version = version.parse(pkg_toml.version)
        old_version = version.parse(cmp[CMP_VERSION])
        if new_version < old_version:
            site.print(f"Newer version {cmp[CMP_VERSION]} already installed")
            return
        if new_version == old_version:
            site.print(f"Version {cmp[CMP_VERSION]} already installed")
            return
        cmp[CMP_NAME] = pkg_toml.original_name
        cmp[CMP_PACKAGE] = pkg_toml.name
        cmp[CMP_VERSION] = pkg_toml.version
        cmp[CMP_DESCRIPTION] = pkg_toml.description
        cmp[CMP_DESCRIPTOR] = f'{top_level}.{pkg_toml.descriptor}'
    # update toml
    project = toml_data['project']
    project['name'] = pkg_toml.name # Use augmented name for package
    tool = toml_data.setdefault('tool', {})
    setup = tool.setdefault('setuptools', {})
    setup['packages'] = [top_level]
    if pkg_toml.component_type == 'service':
        entry = project.setdefault('entry-points', {})
        entry = entry.setdefault('saturnin.service', {})
        entry[cmp[CMP_UID]] = cmp[CMP_DESCRIPTOR]
    elif pkg_toml.component_type == 'application':
        entry = project.setdefault('entry-points', {})
        entry = entry.setdefault('saturnin.application', {})
        entry[cmp[CMP_UID]] = cmp[CMP_DESCRIPTOR]
    # write toml
    target: Path = work_dir / PKG_TOML
    target.write_text(toml.dumps(toml_data))
    #README
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
    copy_tree(work_dir / top_level, path, root_files)
    # Run pip to install prepared package
    pip_cmd = [str(site.pip_path), 'install']
    pip_cmd.extend(args)
    pip_cmd.append(str(work_dir))
    try:
        subprocess.run(pip_cmd, stdout=sys.stdout, stderr=sys.stderr,
                       check=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise Error('Component installation failed') from exc
    if add_component:
        mngr.components.append(cmp)
    mngr.save_components()

@app.command()
def install(package: Path=typer.Argument(..., help="Saturnin ZIP package",
                                         file_okay=True, metavar='FILE'),
            args: List[str]=typer.Argument(None, help="Arguments for 'pip install'. "
                            "If you're using options, it's neccessary to use -- separator"
                            " after package name. Example: pkg install mypkg.zip -- -V")):
    "Installation of Saturnin packages."
    mngr.load_components()
    try:
        had_some: bool = False
        with zipfile.ZipFile(package) as zf:
            root = zipfile.Path(zf)
            pkg_info = root / PKG_TOML
            if pkg_info.exists():
                # Single-service package
                had_some = True
                install_package(args, zf, root)
            else:
                # Service bundle, each subdirectory should contain one service
                for pkg in root.iterdir():
                    pkg_info = pkg / PKG_TOML
                    if pkg_info.exists():
                        had_some = True
                        install_package(args, zf, pkg)
        if not had_some:
            site.print_error(f"The file '{package}' does not contain any Saturnin component")
    except Exception as exc:
        site.print_error(str(exc))

@app.command()
def uninstall(component: str=typer.Argument(..., help="Component name", metavar='NAME')):
    "Uninstallation of Saturnin components."
    mngr.load_components()
    i = mngr.find_component_index(name=component)
    if i < 0:
        site.print_error("Component not found.")
        return
    cmp = mngr.components.pop(i)
    # Run pip to uninstall package
    try:
        subprocess.run([str(site.pip_path), 'uninstall', '-y', cmp[CMP_PACKAGE]],
                       stdout=sys.stdout, stderr=sys.stderr,
                       check=True, text=True)
    except subprocess.CalledProcessError:
        site.print_error('Component uninstallation failed')
        return
    #
    mngr.save_components()

@app.command('list')
def _list():
    "List installed Saturnin components."
    mngr.load_components()
    components = [[cmp[CMP_NAME], cmp[CMP_VERSION], cmp[CMP_UID], cmp[CMP_PACKAGE],
                   cmp[CMP_TOPLEVEL]]
                  for cmp in mngr.components]
    managed = {cmp[CMP_UID]: None for cmp in mngr.components}
    # components not installed via saturnin-pkg, i.e. registered directly, for example
    # by saturnin-sdk
    for svc in get_service_desciptors():
        if str(svc.agent.uid) not in managed:
            components.append([svc.agent.name, svc.agent.version,
                               str(svc.agent.uid), '', svc.package])
    table = Table(title='Registered components')
    table.add_column('Component', style='green')
    table.add_column('Version', style='yellow')
    table.add_column('UID', style='white')
    table.add_column('Package', style='white')
    table.add_column('Top-level', style='white')
    for cmp in components:
        table.add_row(*cmp)
    site.console.print(table)

@app.command()
def pip(args: List[str]=typer.Argument(None, help="Arguments for pip. If you're using options,"
                                       " it's neccessary to use -- separator after pip command."
                                       " Example: pkg pip -- -V")):
    "Run pip from Saturnin virtual environment."
    pip_cmd = [str(site.pip_path)]
    pip_cmd.extend(args)
    try:
        subprocess.run(pip_cmd, stdout=sys.stdout, stderr=sys.stderr,
                       check=True, text=True)
    except subprocess.CalledProcessError:
        site.print_error('pip execution failed')
