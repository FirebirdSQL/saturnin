# SPDX-FileCopyrightText: 2022-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/_scripts/commands/recipes.py
# DESCRIPTION:    Saturnin recipe commands
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
# Copyright (c) 2023 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________
# pylint: disable=R0912, R0913, R0914, R0915

"""Saturnin recipe commands


"""

from __future__ import annotations
from typing import List, Tuple
from pathlib import Path
from tempfile import TemporaryDirectory
from configparser import ConfigParser, ExtendedInterpolation
from uuid import UUID
from datetime import datetime
import subprocess
import typer
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich import box
from firebird.uuid import oid_registry, Node
from firebird.base.config import Config
from saturnin.base import (saturnin_config, SECTION_BUNDLE, SECTION_SERVICE,
                           directory_scheme, RESTART)
from saturnin.component.recipe import (recipe_registry, RecipeInfo, SaturninRecipe,
                                       RecipeType, RecipeExecutionMode)
from saturnin.component.registry import service_registry, ServiceInfo
from saturnin.lib.console import console, _h, RICH_YES, RICH_NO
from saturnin.component.apps import application_registry, ApplicationInfo
from saturnin.component.bundle import ServiceBundleConfig
from saturnin.component.controller import ServiceExecConfig
from saturnin._scripts.completers import (recipe_completer, service_completer,
                                          path_completer, application_completer,
                                          get_first_line)

#: Typer command group for recipe management commands
app = typer.Typer(rich_markup_mode="markdown", help="Saturnin recipes.")

def run_recipe(ctx: typer.Context,
               section: str=typer.Option(None, help="Main recipe section name"),
               print_outcome: bool=typer.Option(False, '--print-outcome',
                                                help="Print service execution outcome"),
               config: List[str]=typer.Option(None,
                                              help="Path to additional configuration file "
                                              "(could be specified multiple times)"),
               quiet: bool=typer.Option(False, '--quiet', help="Suppress console output"),
               main_thread: bool=typer.Option(False, '--main-thread',
                                              help="Start the service in main thread. "
                                              "Ignored for bundles.")) -> None:
    """Runs Saturnin recipe.
    """
    recipe_name = ctx.command.name
    recipe: RecipeInfo = recipe_registry.get(recipe_name)
    if recipe is None:
        console.print_error(f"Recipe '{recipe_name}' not installed")
        return
    if recipe.recipe_type is RecipeType.BUNDLE:
        cmd = ['saturnin-bundle' if recipe.executor is None else str(recipe.executor)]
    else:
        cmd = ['saturnin-service' if recipe.executor is None else str(recipe.executor)]
        if main_thread:
            cmd.append('--main-thread')
    if section:
        cmd.extend(['--section', section])
    if quiet:
        cmd.append('--quiet')
    if print_outcome:
        cmd.append('--outcome')
    for cfg in config:
        cmd.extend(['-c', str(cfg)])
    cmd.append(str(recipe.filename))
    # Daemonize
    pid_file: Path = None
    with TemporaryDirectory() as tmp_dir:
        if recipe.execution_mode is RecipeExecutionMode.DAEMON:
            cmd.insert(1, '-q')
            pid_file = Path(tmp_dir) / 'pid'
            cmd.insert(0, str(pid_file))
            cmd.insert(0, '-p')
            cmd.insert(0, 'start')
            cmd.insert(0, 'saturnin-daemon')
        start = datetime.now()
        result = subprocess.run(cmd) # pylint: disable=W1510
        console.print(f'Execution time: {datetime.now() - start}')
        if pid_file:
            if pid_file.exists():
                pid = int(pid_file.read_text())
                pid_file = directory_scheme.pids / f'{pid}.pid'
                pid_file.write_text(recipe_name)
            else:
                console.print_error("Daemonized recipe execution failed [PID file not found]")
    #result = subprocess.run(cmd, capture_output=True, text=True)
    #console.print(result.stdout)
    if result.returncode != 0:
        console.print_error('Recipe execution failed')

@app.command()
def list_recipes() -> None:
    """List installed Saturnin recipes.
    """
    if recipe_registry:
        table = Table(title='Installed recipes', box=box.ROUNDED)
        table.add_column('Name', style='green')
        table.add_column('Type', style='enum')
        table.add_column('Execution mode', style='enum')
        table.add_column('App', width=3, justify='center')
        table.add_column('Description')
        recipe: RecipeInfo = None
        for recipe in recipe_registry.values():
            table.add_row(recipe.name, recipe.recipe_type.name, recipe.execution_mode.name,
                          RICH_NO if recipe.application is None else RICH_YES,
                          get_first_line(recipe.description))
        console.print(table)
    else:
        console.print("There are no Saturnin recipes installed.")

@app.command()
def show_recipe(recipe_name: str=typer.Argument(..., help="Recipe name",
                                                autocompletion=recipe_completer),
                section: str=typer.Option(None, help="Configuration section name"),
                raw: bool=typer.Option(False, '--raw',
                                       help="Print recipe file content instead normal output")):
    """It analyzes the content of the recipe and displays its structure and configuration according to the default
   sections of the container configuration. If the recipe contains several variants, it is necessary to enter
   the name of the specific section for the configuration of the container to display them.

   Alternatively, it is possible to display the entire recipe in text form (with syntax highlighting).

    """
    recipe: RecipeInfo = recipe_registry.get(recipe_name)
    if recipe is None:
        console.print_error(f"Recipe '{recipe_name}' not installed")
        return
    if raw:
        console.print(Syntax(recipe.filename.read_text(), 'cfg',word_wrap=True))
    else:
        config: ConfigParser = ConfigParser(interpolation=ExtendedInterpolation())
        config.read(recipe.filename)
        recipe_config = SaturninRecipe()
        recipe_config.load_config(config)
        recipe_config.validate()
        #
        title = "default section" if section is None else f'section "[section]{section}[/]"'
        services: List[Tuple[str, ServiceInfo]] = []
        if section is None:
            section = SECTION_BUNDLE if recipe_config.recipe_type.value is RecipeType.BUNDLE \
                else SECTION_SERVICE
        if config.has_section(section):
            if recipe_config.recipe_type.value is RecipeType.BUNDLE:
                bundle_cfg: ServiceBundleConfig = ServiceBundleConfig(section)
                bundle_cfg.load_config(config)
                for agent_config in bundle_cfg.agents.value:
                    services.append((agent_config.name, service_registry[agent_config.agent.value]))
            else:
                svc_cfg: ServiceExecConfig = ServiceExecConfig(section)
                svc_cfg.load_config(config)
                services.append(('service', service_registry[svc_cfg.agent.value]))
        #
        table = Table.grid()
        table.add_column('', style='green')
        table.add_column('')
        table.add_row(' Name:', Text(recipe.name, style='bold cyan'))
        table.add_row(' Type:', Text(recipe.recipe_type.name, style='enum'))
        table.add_row(' Exec. mode:', Text(recipe.execution_mode.name, style='enum'))
        table.add_row(' Executor:', _h(Text('DEFAULT' if recipe.executor is None
                                            else str(recipe.executor))))
        table.add_row(' Application:', _h(Text(str(recipe.application) if recipe.application
                                               else '')))
        table.add_row(' Description: ', Markdown(recipe.description))
        console.print(table)
        console.print()
        if not services:
            if recipe_config.application.has_value():
                console.print("[important] Recipe components deternimed dynamically by application.")
            else:
                console.print_error(f"Recipe does not have expected section {section}")
        else:
            table = Table(title=f"  Recipe components ({title})", box=box.ROUNDED, title_justify='left')
            table.add_column('Cfg. name', style='bold yellow')
            table.add_column('Component', style='green')
            table.add_column('Version', style='number')
            table.add_column('Description')
            for cfg_name, svc in services:
                table.add_row(cfg_name, svc.name, svc.version, get_first_line(svc.description))
            console.print(table)
            console.print()
            for cfg_name, svc in services:
                table = Table(title=f"  [title]{cfg_name}[/] configuration", box=box.ROUNDED,
                              title_justify='left', highlight=True)
                table.add_column('Parameter', style='green')
                table.add_column('Value')
                cmp_conf: Config = svc.descriptor_obj.config()
                cmp_conf.load_config(config, cfg_name)
                for option in cmp_conf.options:
                    table.add_row(option.name, 'None' if option.get_value() is None
                                  else option.get_as_str())
                console.print(table)
                console.print()

@app.command()
def edit_recipe(recipe_name: str=typer.Argument(..., help="Recipe name",
                                                autocompletion=recipe_completer)):
    """Edit recipe.
    """
    recipe: RecipeInfo = recipe_registry.get(recipe_name)
    if recipe is None:
        console.print_error(f"Recipe '{recipe_name}' not installed")
        return None
    edited = typer.edit(recipe.filename.read_text(), saturnin_config.editor.value,
                        extension=recipe.filename.suffix)
    if edited is not None:
        recipe.filename.write_text(edited)
        console.print("Recipe updated.")
    recipe_registry.clear()
    recipe_registry.load_from(directory_scheme.recipes)
    return RESTART

@app.command()
def install_recipe(recipe_name: str= \
                     typer.Option(None, help="Recipe name (default is recipe file name / application name)"),
                   recipe_file: Path= \
                     typer.Option(None, help="Recipe file. Mutually exclusive with ",
                                  dir_okay=False, autocompletion=path_completer),
                   app_id: str=typer.Option(None, help="Application UID or name",
                                            autocompletion=application_completer)):
    """Installs a new recipe from an external recipe file or from an installed application.
    Once installed, recipe can be executed immediately with the `run <recipe-name>` command.
    """
    if recipe_file is None and app_id is None:
        console.print_error("Either recipe file or application must be specified.")
        return None
    if recipe_file is not None and app_id is not None:
        console.print_error("Either recipe file or application must be specified, but not both")
        return None
    app: ApplicationInfo = None
    if app_id is not None:
        try:
            app = application_registry.get(UUID(app_id))
        except Exception: # pylint: disable=W0703
            app = application_registry.get_by_name(app_id)
        if app is None:
            console.print_error('Application not registered!')
            return None
    if recipe_name is None:
        if app is None:
            recipe_name = recipe_file.stem
        else:
            recipe_name = app.get_recipe_name()
    #
    if recipe_name in recipe_registry:
        console.print_error(f"Recipe '{recipe_name}' already installed")
        return None
    #
    target: Path = directory_scheme.recipes
    config: ConfigParser = ConfigParser(interpolation=ExtendedInterpolation())
    if app is None: # Import recipe
        config.read(recipe_file)
        recipe_content = recipe_file.read_text()
        target = target / recipe_file.with_stem(recipe_name).name
    else: # Import application
        recipe_content = app.config_obj()
        config.read_string(recipe_content)
        target = target / f'{recipe_name}.cfg'

    recipe_config = SaturninRecipe()
    recipe_config.load_config(config)
    recipe_config.validate()
    # Check whether all required components are installed
    application = recipe_config.application.value
    if (application and application not in application_registry):
        node: Node = oid_registry.get(application)
        console.print_error(f"Required application '{node.name if node else application}' not installed")
        return None
    section = SECTION_BUNDLE if recipe_config.recipe_type.value is RecipeType.BUNDLE \
        else SECTION_SERVICE
    services: List[UUID] = []
    if config.has_section(section):
        if recipe_config.recipe_type.value is RecipeType.BUNDLE:
            bundle_cfg: ServiceBundleConfig = ServiceBundleConfig(section)
            bundle_cfg.load_config(config)
            for agent_config in bundle_cfg.agents.value:
                services.append(agent_config.agent.value)
        else:
            svc_cfg: ServiceExecConfig = ServiceExecConfig(section)
            svc_cfg.load_config(config)
            services.append(svc_cfg.agent.value)
        stop = False
        for svc_uid in services:
            if svc_uid not in service_registry:
                node: Node = oid_registry.get(svc_uid)
                console.print_error(f"Required service '{node.name if node else svc_uid}' not installed")
                stop = True
        if stop:
            return None
    else:
        console.print_error(f"The recipe does not have the required section '{section}'")
        return None
    #
    target.write_text(recipe_content)
    console.print("Recipe installed.")
    recipe_registry.clear()
    recipe_registry.load_from(directory_scheme.recipes)
    return RESTART

@app.command()
def uninstall_recipe(recipe_name: str=typer.Argument(None, autocompletion=recipe_completer,
                                                     help="The name of the recipe to be uninstalled"),
                     save_to: Path=typer.Option(None, dir_okay=False, writable=True,
                                                help="File where recipe should be saved before it's removed")):
    """Uninstall recipe. Can optionally save the recipe file
    """
    recipe: RecipeInfo = recipe_registry.get(recipe_name)
    if recipe is None:
        console.print_error(f"Recipe '{recipe_name}' not installed")
        return None
    if save_to is not None:
        save_to.write_text(recipe.filename.read_text())
    recipe.filename.unlink()
    console.print("Recipe uninstalled.")
    recipe_registry.clear()
    recipe_registry.load_from(directory_scheme.recipes)
    return RESTART

@app.command()
def create_recipe(plain: bool=typer.Option(False, '--plain', help="Create recipe without comments"),
                  recipe_name: str=typer.Argument(..., help="Recipe name", metavar='NAME'),
                  components: List[str]=typer.Argument(..., help="Recipe components",
                                                       autocompletion=service_completer)):
    """Creates a recipe template that uses the specified Butler services. Such a template
    contains only default settings and usually needs to be modified to achieve the desired
    results.
    """
    if recipe_name in recipe_registry:
        console.print_error(f"Recipe '{recipe_name}' already exists")
        return None
    #
    recipe_type: RecipeType = RecipeType.SERVICE if len(components) == 1 \
        else RecipeType.BUNDLE
    service_config: ServiceExecConfig = ServiceExecConfig(SECTION_SERVICE)
    bundle_config: ServiceBundleConfig = ServiceBundleConfig(SECTION_BUNDLE)
    recipe_config = SaturninRecipe()
    recipe_config.recipe_type.value = recipe_type
    #
    for i, component in enumerate(components, 1):
        svc: ServiceInfo = None
        try:
            svc = service_registry.get(UUID(component))
        except Exception: # pylint: disable=W0703
            svc = service_registry.get_by_name(component)
        if svc is None:
            console.print_error('Service not registered!')
            return None
        service_config.agent.value = svc.uid
        component_config = svc.descriptor_obj.config()
        if recipe_type is RecipeType.BUNDLE:
            component_config._name = f'component_{i}'
            service_config._name = f'component_{i}'
            bundle_config.agents.value.append(component_config)
        else:
            component_config._name = SECTION_SERVICE
    #
    recipe_text: str = recipe_config.get_config(plain=plain)
    recipe_text += '\n'
    recipe_text += bundle_config.get_config(plain=plain) if recipe_type is RecipeType.BUNDLE\
        else component_config.get_config(plain=plain)
    target: Path = directory_scheme.recipes / f'{recipe_name}.cfg'
    recipe_text = typer.edit(recipe_text, saturnin_config.editor.value,
                             extension='.cfg', require_save=False)
    if recipe_text is not None:
        target.write_text(recipe_text)
        console.print("Recipe created.")
        recipe_registry.clear()
        recipe_registry.load_from(directory_scheme.recipes)
        return RESTART
    return None
