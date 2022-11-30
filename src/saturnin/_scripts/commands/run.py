#coding:utf-8
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/_scripts/commands/run.py
# DESCRIPTION:    Saturnin run commands
# CREATED:        29.11.2022
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

"""Saturnin run commands


"""

from __future__ import annotations
from typing import List
import subprocess
import typer
from saturnin.base import site
from saturnin.component.registry import get_service_distributions, service_registry

app = typer.Typer(rich_markup_mode="rich", help="Saturnin executor.")

@app.command('recipe')
def recipe(name: str = typer.Argument(..., help="Recipe name")) -> None:
    """Runs Saturnin recipe.
    """
    cmd = ['saturnin-bundle', str(site.scheme.recipes / f'{name}.cfg')]
    result = subprocess.run(cmd, capture_output=True, text=True)
    site.print(result.stdout)
    if result.returncode != 0:
        site.err_console.print(result.stderr)
