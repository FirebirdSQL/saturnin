#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/lib/pyproject.py
# DESCRIPTION:    Class to handle pyproject.toml files.
# CREATED:        12.2.2021
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

"""saturnin - Class to handle pyproject.toml files.


"""

from __future__ import annotations
from typing import List
import re

def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


class PyProjectTOML:
    """
    """
    def __init__(self, pyproject_data: Dict):
        project = pyproject_data['project']
        self.name: str = normalize(project['name'])
        self.original_name: str = project['name']
        self.version: str = project['version']
        self.description: str = project['description']
        self.readme: Union[str, Dict[str, str]] = project.get('readme')
        self.requires_python: str = project.get('requires-python')
        self.license: Dict[str, str] = project.get('license')
        self.authors: List[Dict[str, str]] = project.get('authors')
        self.maintainers: List[Dict[str, str]] = project.get('keywords')
        self.keywords: List[str] = project.get('keywords')
        self.classifiers: List[str] = project.get('classifiers')
        self.urls: Dict[str, str] = project.get('urls')
        self.scripts: Dict[str, str] = project.get('scripts')
        self.gui_scripts: Dict[str, str] = project.get('gui-scripts')
        self.entry_points: Dict[str, Dict[str, str]] = project.get('entry-points')
        self.dependencies: List[str] = project.get('dependencies')
        self.optional_dependencies: Dict[str, List[str]] = project.get('optional-dependencies')
        self.dynamic: List[str] = project.get('dynamic')
        #
        meta = pyproject_data['tool']['saturnin']['metadata']
        self.component_type: str = meta['component-type']
        self.uid: str = meta['uid']
        self.descriptor: str = meta['descriptor']
    def make_setup_cfg(self, cfg: 'ConfigParser') -> None:
        """
        """
        def set_content_type(readme_file: str):
            if readme_file.lower().endswith('.md'):
                cfg['metadata']['long_description_content_type'] = 'text/markdown; charset=UTF-8'
            elif readme_file.lower().endswith('.rst'):
                cfg['metadata']['long_description_content_type'] = 'text/x-rst; charset=UTF-8'
            else:
                cfg['metadata']['long_description_content_type'] = 'text/plain; charset=UTF-8'
        def multiline(lines: List) -> str:
            l = ['']
            l.extend(lines)
            return '\n'.join(l)

        if not cfg.has_section('metadata'):
            cfg.add_section('metadata')
        cfg['metadata']['name'] = self.name
        cfg['metadata']['version'] = self.version
        cfg['metadata']['description'] = self.description
        cfg['metadata']['name'] = self.name
        if self.readme is not None:
            if isinstance(self.readme, dict):
                if 'file' in self.readme:
                    cfg['metadata']['long_description'] = f"file: {self.readme['file']}"
                else:
                    cfg['metadata']['long_description'] = self.readme['text']
                if 'content-type' in self.readme:
                    cfg['metadata']['long_description_content_type'] = self.readme['content-type']
                elif 'file' in self.readme:
                    set_content_type(self.readme['file'])
            else:
                cfg['metadata']['long_description'] = f"file: {self.readme}"
                set_content_type(self.readme)
        if self.requires_python is not None:
            cfg['metadata']['python_requires'] = self.requires_python
        if self.license is not None:
            if 'file' in self.license:
                cfg['metadata']['license_file'] = self.license['file']
            else:
                cfg['metadata']['license'] = self.license['text']
        if self.authors is not None:
            author = self.authors[0]
            if 'name' in author:
                cfg['metadata']['author'] = author['name']
            if 'email' in author:
                cfg['metadata']['author_email'] = author['email']
            if 'name' in author and 'email' in author:
                cfg['metadata']['author_email'] = f"{author['name']} <{author['email']}>"
        if self.maintainers is not None:
            maintainer = self.maintainers[0]
            if 'name' in maintainer:
                cfg['metadata']['maintainer'] = maintainer['name']
            if 'email' in maintainer:
                cfg['metadata']['maintainer_email'] = maintainer['email']
            if 'name' in maintainer and 'email' in maintainer:
                cfg['metadata']['maintainer_email'] = f"{maintainer['name']} <{maintainer['email']}>"
        if self.keywords is not None:
            cfg['metadata']['keywords'] = ', '.join(self.keywords)
        if self.classifiers is not None:
            cfg['metadata']['classifiers'] = multiline(self.classifiers)
        if self.urls is not None:
            urls = []
            for k, v in self.urls.items():
                if k.lower() == 'home':
                    cfg['metadata']['url'] = v
                else:
                    urls.append(f'{k} = {v}')
            cfg['metadata']['project_urls '] = multiline(urls)
        if self.scripts is not None:
            if not cfg.has_section('options.entry_points'):
                cfg.add_section('options.entry_points')
            cfg['options.entry_points']['console_scripts'] = \
                multiline([f'{k} = {v}' for k, v in self.scripts.items()])
        if self.gui_scripts is not None:
            if not cfg.has_section('options.entry_points'):
                cfg.add_section('options.entry_points')
            cfg['options.entry_points']['gui_scripts'] = \
                multiline([f'{k} = {v}' for k, v in self.gui_scripts.items()])
        if self.entry_points is not None:
            if not cfg.has_section('options.entry_points'):
                cfg.add_section('options.entry_points')
            for group_name, group in self.entry_points.items():
                cfg['options.entry_points'][group_name] = \
                    multiline([f'{k} = {v}' for k, v in group.items()])
        if self.dependencies is not None:
            if not cfg.has_section('options'):
                cfg.add_section('options')
            cfg['options']['install_requires'] = multiline(self.dependencies)
        if self.optional_dependencies is not None:
            if not cfg.has_section('options.extras_require'):
                cfg.add_section('options.extras_require')
            for ext_name, extra in self.optional_dependencies.items():
                cfg['options.extras_require'][ext_name] = \
                    multiline([f'{k} = {v}' for k, v in extra.items()])

