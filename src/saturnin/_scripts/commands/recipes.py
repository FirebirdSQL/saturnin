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

"""Saturnin recipe management commands.

This module provides Typer commands for listing, showing, editing, installing,
uninstalling, and creating Saturnin recipes. Recipes are configuration files
that define how to run services or bundles of services.
"""

from __future__ import annotations

import os
import subprocess
from configparser import ConfigParser
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated
from uuid import UUID

import typer
from rich import box
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from saturnin._scripts.completers import (
    application_completer,
    get_first_line,
    path_completer,
    recipe_completer,
    service_completer,
)
from saturnin.base import RESTART, SECTION_BUNDLE, SECTION_SERVICE, directory_scheme, saturnin_config
from saturnin.component.apps import ApplicationInfo, application_registry
from saturnin.component.bundle import ServiceBundleConfig
from saturnin.component.controller import ServiceExecConfig
from saturnin.component.recipe import RecipeExecutionMode, RecipeInfo, RecipeType, SaturninRecipe, recipe_registry
from saturnin.component.registry import ServiceInfo, service_registry
from saturnin.lib.console import RICH_NO, RICH_YES, _h, console

from firebird.base.config import Config, EnvExtendedInterpolation
from firebird.uuid import OIDNode, oid_registry

#: Typer command group for recipe management commands
app = typer.Typer(rich_markup_mode="markdown", help="Saturnin recipes.")

def run_recipe(
    ctx: typer.Context,
    section: Annotated[str | None, typer.Option(help="Main recipe section name")]=None,
    config: Annotated[list[str] | None, typer.Option(help="Path to additional configuration file "
                                                     "(could be specified multiple times)")]=None,
    *,
    print_outcome: Annotated[bool, typer.Option('--print-outcome',
                                                help="Print service execution outcome")]=False,
    quiet: Annotated[bool, typer.Option('--quiet', help="Suppress console output")]=False,
    main_thread: Annotated[bool, typer.Option('--main-thread',
                                      help="Start the service in main thread. Ignored for bundles.")]=False
    ) -> None:
    """Internal handler to execute a Saturnin recipe.

    This function is invoked by Typer when a `run <recipe-name>` command,
    dynamically created from an installed recipe, is executed. It determines
    the recipe to run based on the invoked command name (`ctx.command.name`).

    It constructs the appropriate command line for `saturnin-service` or
    `saturnin-bundle` (or a custom executor if specified in the recipe)
    and then executes it using `subprocess.run`.

    If the recipe's execution mode is `DAEMON`, this function utilizes
    `saturnin-daemon start` to launch the recipe as a background process,
    managing its PID file.

    Args:
        ctx: The Typer context, used to get the invoked command name (recipe name).
        section: Optional name of the main configuration section within the recipe file.
                 If not provided, defaults to 'service' or 'bundle' based on the
                 recipe's type.
        config: Optional list of paths to additional .cfg files whose configurations
                will be layered over the recipe's base configuration.
        print_outcome: If True, the final execution outcome of the service(s)
                       will be printed to the console.
        quiet: If True, suppresses most console output from the executed
               service/bundle script.
        main_thread: If True and the recipe is for a single service, the service
                     is run in the main thread of the `saturnin-service` script.
                     This option is ignored for bundle recipes.
    """
    recipe_name = ctx.command.name
    recipe: RecipeInfo = recipe_registry.get(recipe_name)
    if recipe is None:
        console.print_error(f"Recipe '[item]{recipe_name}[/]' not installed.")
        return
    if recipe.recipe_type is RecipeType.BUNDLE:
        cmd = ['saturnin-bundle' if recipe.executor is None else str(recipe.executor)]
    else:
        cmd = ['saturnin-service' if recipe.executor is None else str(recipe.executor)]
        if main_thread:
            cmd.append('--main-thread')
    ## Add logging configuration
    #cmd.extend(['-c', str(directory_scheme.logging_conf)])
    if section:
        cmd.extend(['--section', section])
    if quiet:
        cmd.append('--quiet')
    if print_outcome:
        cmd.append('--outcome')
    if config:
        for cfg_path_str in config:
            cfg_path = Path(cfg_path_str)
            if not cfg_path.is_file():
                console.print_error(f"Additional configuration file not found: [path]{cfg_path}[/]")
                return
            cmd.extend(['-c', str(cfg_path_str)])
    cmd.append(str(recipe.filename))
    # Daemonize
    if recipe.execution_mode is RecipeExecutionMode.DAEMON:
        # For daemon mode, we prepend `saturnin-daemon start -p <pid_file_path>`
        # and ensure the service script runs quietly.
        if not quiet: # If user didn't specify quiet for `run recipe`, add it for daemon script
            daemon_cmd_insert_index = 1 # after 'saturnin-bundle' or 'saturnin-service'
            if '--main-thread' in cmd: # Adjust if --main-thread is present
                daemon_cmd_insert_index +=1
            if not any(q_opt in cmd for q_opt in ['-q', '--quiet']):
                cmd.insert(daemon_cmd_insert_index, '--quiet')
    try:
        if recipe.execution_mode is RecipeExecutionMode.DAEMON:
            with TemporaryDirectory() as tmp_dir:
                temp_pid_file = Path(tmp_dir) / f"{recipe_name}.pid.tmp"
                daemon_cmd_parts = ['saturnin-daemon', 'start', '-p', str(temp_pid_file)]
                full_cmd = daemon_cmd_parts + cmd
                result = subprocess.run(full_cmd, check=False) # Let saturnin-daemon handle its own output
                if result.returncode == 0 and temp_pid_file.exists():
                    pid_str = temp_pid_file.read_text().strip()
                    if pid_str:
                        pid = int(pid_str)
                        final_pid_file = directory_scheme.pids / f'{pid}.pid'
                        final_pid_file.parent.mkdir(parents=True, exist_ok=True)
                        final_pid_file.write_text(recipe_name)
                        console.print(f"Daemon started successfully. PID: [item]{pid}[/]. "
                                      f"PID file: [path]{final_pid_file}[/]")
                    else:
                        console.print_error("Daemonized recipe execution failed: Temporary PID file was empty.")
                elif result.returncode !=0:
                    console.print_error(f"Daemon start command failed with exit code {result.returncode}.")
                else: # result.returncode == 0 but temp_pid_file doesn't exist
                    console.print_error("Daemonized recipe execution failed: Temporary PID file not created by `saturnin-daemon`.")
        else: # Normal execution
            console.print(f"Running recipe: `{' '.join(cmd)}`")
            start_time = datetime.now()
            # For normal execution, we might want to see the output directly
            result = subprocess.run(cmd, check=False)
            console.print(f"Recipe execution time: {datetime.now() - start_time}")
            if result.returncode != 0:
                console.print_error(f"Recipe execution failed with exit code {result.returncode}.")
    except FileNotFoundError as e:
        console.print_error(f"Execution failed: Command '[item]{e.filename}[/]' not found. "
                            "Ensure Saturnin scripts are in your PATH.")
    except Exception as e:
        console.print_error(f"An unexpected error occurred while trying to run the recipe: {e}")
        console.print_exception(show_locals=True) # For debugging
    #with TemporaryDirectory() as tmp_dir:
        #if recipe.execution_mode is RecipeExecutionMode.DAEMON:
            #cmd.insert(1, '-q')
            #pid_file = Path(tmp_dir) / 'pid'
            #cmd.insert(0, str(pid_file))
            #cmd.insert(0, '-p')
            #cmd.insert(0, 'start')
            #cmd.insert(0, 'saturnin-daemon')
        #start = datetime.now()
        #result = subprocess.run(cmd, check=False)
        #console.print(f'Execution time: {datetime.now() - start}')
        #if pid_file:
            #if pid_file.exists():
                #pid = int(pid_file.read_text())
                #pid_file = directory_scheme.pids / f'{pid}.pid'
                #pid_file.write_text(recipe_name)
            #else:
                #console.print_error("Daemonized recipe execution failed [PID file not found]")
    ##result = subprocess.run(cmd, capture_output=True, text=True)
    ##console.print(result.stdout)
    #if result.returncode != 0:
        #console.print_error('Recipe execution failed')

@app.command()
def list_recipes() -> None:
    """Lists all installed Saturnin recipes.

    Displays a table with the recipe name, type (service or bundle),
    execution mode (normal or daemon), whether it's associated with an
    application, and a brief description.
    """
    if not recipe_registry:
        console.print("There are no Saturnin recipes installed.")
        return

    table = Table(title='Installed Saturnin Recipes', box=box.ROUNDED)
    table.add_column('Name', style='green', overflow="fold")
    table.add_column('Type', style='enum')
    table.add_column('Exec. Mode', style='enum')
    table.add_column("It's App?", width=9, justify='center')
    table.add_column('Description', overflow="fold")

    sorted_recipes = sorted(recipe_registry.values(), key=lambda r: r.name)

    recipe: RecipeInfo
    for recipe in sorted_recipes:
        table.add_row(recipe.name,
                      recipe.recipe_type.name.capitalize(),
                      recipe.execution_mode.name.capitalize(),
                      RICH_YES if recipe.application is not None else RICH_NO,
                      get_first_line(recipe.description))
    console.print(table)

@app.command()
def show_recipe(
    recipe_name: Annotated[str, typer.Argument(help="The name of the recipe to display.",
                                               autocompletion=recipe_completer)],
    section: Annotated[str | None, typer.Option(help="Configuration section name within the recipe file "
                                                "to analyze (e.g., for specific service settings in a bundle). "
                                                "Defaults to 'service' or 'bundle'.")]=None,
             *,
             raw: Annotated[bool, typer.Option('--raw',
                                               help="Print recipe file content instead normal output")]=False
             ):
    """Displays detailed information about an installed Saturnin recipe.

    By default, it analyzes the recipe file, showing its metadata (type, execution mode,
    associated application), a description, and a breakdown of its components
    (services within a bundle or the single service) along with their configurations
    as defined in the specified or default section (e.g., 'service' or 'bundle').

    If a recipe contains multiple service/bundle configuration sections (variants),
    use the `--section` option to specify which one to analyze.

    The `--raw` option will instead print the entire content of the recipe
    file with syntax highlighting.
    """
    recipe: RecipeInfo = recipe_registry.get(recipe_name)
    if recipe is None:
        console.print_error(f"Recipe '[item]{recipe_name}[/]' not installed.")
        return

    if raw:
        try:
            content = recipe.filename.read_text(encoding='utf-8')
            console.print(Syntax(content, 'ini', theme=console.std_console.highlighter.theme, line_numbers=True, word_wrap=True))
        except FileNotFoundError:
            console.print_error(f"Recipe file not found: [path]{recipe.filename}[/]")
        except Exception as e:
            console.print_error(f"Error reading recipe file [path]{recipe.filename}[/]: {e}")
        return

    config_parser: ConfigParser = ConfigParser(interpolation=EnvExtendedInterpolation())
    try:
        config_parser.read(recipe.filename, encoding='utf-8')
    except FileNotFoundError:
        console.print_error(f"Recipe file not found: [path]{recipe.filename}[/]")
        return
    except Exception as e:
        console.print_error(f"Error parsing recipe file [path]{recipe.filename}[/]: {e}")
        return

    recipe_meta_config = SaturninRecipe()
    recipe_meta_config.load_config(config_parser) # Loads from [saturnin.recipe]
    recipe_meta_config.validate() # Validate metadata part

    # Display recipe metadata
    meta_table = Table.grid(padding=(0,1))
    meta_table.add_column(style='green', justify="right")
    meta_table.add_column()
    meta_table.add_row('Name:', Text(recipe.name, style='bold cyan'))
    meta_table.add_row('Type:', Text(recipe.recipe_type.name.capitalize(), style='enum'))
    meta_table.add_row('Execution Mode:', Text(recipe.execution_mode.name.capitalize(), style='enum'))
    meta_table.add_row('Executor:', _h(Text('Default' if recipe.executor is None else str(recipe.executor))))

    app_display_name = "Not Associated"
    if recipe.application:
        app_info = application_registry.get(recipe.application)
        app_display_name = f"{app_info.name} ({recipe.application})" if app_info else str(recipe.application)
    meta_table.add_row('Application:', _h(Text(app_display_name)))
    meta_table.add_row('Description:', Markdown(recipe.description.strip()))
    meta_table.add_row('File Path:', Text(str(recipe.filename.resolve()), style='path'))
    console.print(Panel(meta_table, title="[b]Recipe Metadata[/b]", border_style="dim", expand=False))
    console.print()

    # Determine effective section to analyze
    effective_section = section
    if not effective_section:
        effective_section = SECTION_BUNDLE if recipe_meta_config.recipe_type.value is RecipeType.BUNDLE else SECTION_SERVICE

    # Analyze and display components and their configurations
    services_to_display: list[tuple[str, ServiceInfo]] = []
    if config_parser.has_section(effective_section):
        title_section_name = f"'{effective_section}'"
        if recipe_meta_config.recipe_type.value is RecipeType.BUNDLE:
            bundle_cfg: ServiceBundleConfig = ServiceBundleConfig(effective_section)
            bundle_cfg.load_config(config_parser)
            bundle_cfg.validate()
            for agent_config in bundle_cfg.agents.value:
                service_info = service_registry.get(agent_config.agent.value)
                if service_info:
                    services_to_display.append((agent_config.name, service_info))
                else:
                    console.print_error(f"Service with UID [item]{agent_config.agent.value}[/] defined in bundle section "
                                        f"'[item]{effective_section}[/]', config name '[item]{agent_config.name}[/]' not found in registry.")
        else: # Single service
            svc_cfg: ServiceExecConfig = ServiceExecConfig(effective_section)
            svc_cfg.load_config(config_parser)
            svc_cfg.validate()
            service_info = service_registry.get(svc_cfg.agent.value)
            if service_info:
                services_to_display.append((svc_cfg.name or effective_section, service_info)) # Use section name if service exec config has no name
            else:
                console.print_error(f"Service with UID [item]{svc_cfg.agent.value}[/] defined in section "
                                    f"'[item]{effective_section}[/]' not found in registry.")

        if services_to_display:
            components_table = Table(title=f"Components in Section [item]{title_section_name}[/]",
                                     box=box.ROUNDED, title_justify='left')
            components_table.add_column('Config Name', style='bold yellow', overflow="fold")
            components_table.add_column('Service Name', style='green', overflow="fold")
            components_table.add_column('Version', style='cyan')
            components_table.add_column('Description', overflow="fold")
            for cfg_name, svc_info_item in services_to_display:
                components_table.add_row(cfg_name, svc_info_item.name, svc_info_item.version, get_first_line(svc_info_item.description))
            console.print(components_table)
            console.print()

            for cfg_name, svc_info_item in services_to_display:
                config_table = Table(title=f"Configuration for '[item]{cfg_name}[/]' ([italic]{svc_info_item.name}[/italic])",
                                     box=box.ROUNDED, title_justify='left')
                config_table.add_column('Parameter', style='green')
                config_table.add_column('Value', overflow="fold")
                component_config: Config = svc_info_item.descriptor_obj.config() # Get a fresh config instance
                component_config.load_config(config_parser, cfg_name) # Load from the specific section name
                for option in component_config.options:
                    val_str = str(option.get_value()) if option.has_value() and option.get_value() is not None else "Not set (uses default)"
                    config_table.add_row(option.name, _h(Text(val_str))) # Highlight potentially special values
                console.print(config_table)
                console.print()
        elif recipe_meta_config.application.has_value():
            console.print(f"[info]Recipe components for section [item]{title_section_name}[/] are determined dynamically by the associated application.[/info]")
        else:
            console.print_error(f"Recipe section [item]{effective_section}[/] not found or misconfigured.")
    elif section: # User specified a section that doesn't exist
        console.print_error(f"Specified recipe section [item]{section}[/] not found in [path]{recipe.filename}[/path].")
    else: # Default section not found, and no specific section requested
        console.print_error(f"Default recipe section ([item]{effective_section}[/]) not found in [path]{recipe.filename}[/path].")

@app.command()
def edit_recipe(
    recipe_name: Annotated[str, typer.Argument(help="The name of the recipe to edit.",
                                               autocompletion=recipe_completer)]
    ):
    """Opens the specified installed recipe file in an external editor.

    The editor is determined by the `EDITOR` environment variable or Saturnin's
    configured default. After editing, the recipe registry is reloaded.
    """
    recipe: RecipeInfo = recipe_registry.get(recipe_name)
    if recipe is None:
        console.print_error(f"Recipe '[item]{recipe_name}[/]' not installed.")
        raise typer.Exit(code=1)

    editor_to_use = saturnin_config.editor.value or os.getenv('EDITOR')
    if not editor_to_use:
        console.print_error("No editor configured. Set the EDITOR environment variable or the 'editor' option in saturnin.conf.")
        raise typer.Exit(code=1)

    try:
        original_content = recipe.filename.read_text(encoding='utf-8')
    except FileNotFoundError:
        console.print_error(f"Recipe file not found: [path]{recipe.filename}[/]")
        raise typer.Exit(code=1) from None
    except Exception as e:
        console.print_error(f"Error reading recipe file [path]{recipe.filename}[/]: {e}")
        return

    edited_content = typer.edit(original_content, editor=editor_to_use,
                                extension=recipe.filename.suffix)

    if edited_content is not None and edited_content != original_content:
        try:
            recipe.filename.write_text(edited_content, encoding='utf-8')
            console.print(f"Recipe '[item]{recipe_name}[/]' updated.")
            # Reload registry after successful save
            recipe_registry.clear()
            recipe_registry.load_from(directory_scheme.recipes)
            return RESTART
        except Exception as e:
            console.print_error(f"Error writing updated recipe file [path]{recipe.filename}[/]: {e}")
    elif edited_content is None: # Editor likely aborted
        console.print("Edit cancelled, no changes made.")
    else: # Content is identical
        console.print("No changes detected in recipe.")

@app.command()
def install_recipe(
    recipe_file: Annotated[Path | None,
                           typer.Option(help="Name for the installed recipe. If not provided, it's derived "
                 "from the recipe file name (without .cfg) or the application's default recipe name.",
                 dir_okay=False, autocompletion=path_completer)]=None,
    application: Annotated[str | None,
                           typer.Option(help="Install recipe from an installed application (UID or name). "
                                        "Mutually exclusive with --recipe-file.",
                                        autocompletion=application_completer)]=None,
    recipe_name: Annotated[str | None,
                           typer.Option(help="Path to the recipe file to install. "
                                        "Mutually exclusive with --application.")]=None,
    ):
    """Installs a new recipe into the Saturnin environment.

    A recipe can be installed either from an external `.cfg` file (using `--recipe-file`)
    or by generating it from an installed Saturnin application (using `--application`).
    The installed recipe will be copied/created in Saturnin's recipes directory.

    If `recipe_name` is not provided, it's automatically derived:

    - From the filename if `--recipe-file` is used (e.g., `my_service.cfg` becomes `my_service`).

    - From the application's default recipe name if `--application` is used.

    ---

    The command validates that all services and applications required by the recipe
    are currently installed in the Saturnin environment.
    """
    if recipe_file is None and application is None:
        console.print_error("Either `--recipe-file` or `--application` must be specified.")
        return
    if recipe_file is not None and application is not None:
        console.print_error("`--recipe-file` and `--application` are mutually exclusive.")
        return

    app_info: ApplicationInfo | None = None
    if application is not None:
        try:
            app_info = application_registry.get(UUID(application))
        except ValueError: # Not a UUID
            app_info = application_registry.get_by_name(application)
        if app_info is None:
            console.print_error(f"Application '[item]{application}[/]' not registered!")
            return

    effective_recipe_name = recipe_name
    if not effective_recipe_name:
        if app_info:
            effective_recipe_name = app_info.get_recipe_name()
        elif recipe_file: # recipe_file must be non-None here
            effective_recipe_name = recipe_file.stem
        # This case should not be reached due to initial checks, but as a safeguard:
        else:
            console.print_error("Could not determine recipe name.")
            return

    if effective_recipe_name in recipe_registry:
        console.print_error(f"Recipe '[item]{effective_recipe_name}[/]' is already installed.")
        return

    if application_registry.contains(lambda x: x.recipe_factory is None
                                     and x.get_recipe_name() == effective_recipe_name):
        console.print_error(f"Recipe '[item]{effective_recipe_name}[/]' cannot be installed. "
                            "Application of the same name is already installed.")
        return

    target_recipes_dir: Path = directory_scheme.recipes
    target_recipes_dir.mkdir(parents=True, exist_ok=True) # Ensure recipes directory exists

    config_parser: ConfigParser = ConfigParser(interpolation=EnvExtendedInterpolation())
    recipe_content_str: str
    source_description: str

    if recipe_file:
        source_description = f"file [path]{recipe_file}[/path]"
        try:
            recipe_content_str = recipe_file.read_text(encoding='utf-8')
            config_parser.read_string(recipe_content_str)
        except Exception as e:
            console.print_error(f"Error reading or parsing recipe from {source_description}: {e}")
            return
        target_recipe_path = target_recipes_dir / f"{effective_recipe_name}.cfg"
    else: # app_info must be non-None here
        source_description = f"application '[item]{app_info.name}[/]'"
        try:
            config_parser.read_string(app_info.recipe_factory_obj())
        except Exception as e:
            console.print_error(f"Error generating recipe content from {source_description}: {e}")
            return
        target_recipe_path = target_recipes_dir / f"{effective_recipe_name}.cfg"
    # Validate the [saturnin.recipe] section
    recipe_meta_config = SaturninRecipe()
    try:
        recipe_meta_config.load_config(config_parser) # Loads from [saturnin.recipe]
        recipe_meta_config.validate()
    except Exception as e:
        console.print_error(f"Invalid `[saturnin.recipe]` section in recipe from {source_description}: {e}")
        return

    # Check if all required components (services, applications) are installed
    required_app_uid = recipe_meta_config.application.value
    if required_app_uid and required_app_uid not in application_registry:
        node: OIDNode | None = oid_registry.get(required_app_uid)
        app_name_str = node.name if node else str(required_app_uid)
        console.print_error(f"Recipe requires application '[item]{app_name_str}[/]', which is not installed.")
        return

    # Determine the main configuration section (e.g., 'service' or 'bundle')
    main_cfg_section_name = SECTION_BUNDLE if recipe_meta_config.recipe_type.value is RecipeType.BUNDLE else SECTION_SERVICE
    if not config_parser.has_section(main_cfg_section_name):
        # Check if it's an app-driven recipe where the section might be dynamically named or implicit
        if not required_app_uid: # If not app-driven, the main section is expected
            console.print_error(f"Recipe from {source_description} is missing the required main configuration section: '[item]{main_cfg_section_name}[/]'.")
            return

    else: # Main section exists, validate its services
        required_service_uids: list[UUID] = []
        if recipe_meta_config.recipe_type.value is RecipeType.BUNDLE:
            bundle_cfg = ServiceBundleConfig(main_cfg_section_name)
            bundle_cfg.load_config(config_parser)
            bundle_cfg.validate()
            required_service_uids.extend(agent_cfg.agent.value for agent_cfg in bundle_cfg.agents.value)
        else: # Single service
            svc_cfg = ServiceExecConfig(main_cfg_section_name)
            svc_cfg.load_config(config_parser)
            svc_cfg.validate()
            required_service_uids.append(svc_cfg.agent.value)

        missing_services = []
        for svc_uid in required_service_uids:
            if svc_uid not in service_registry:
                node: OIDNode | None = oid_registry.get(svc_uid)
                svc_name_str = node.name if node else str(svc_uid)
                missing_services.append(svc_name_str)
        if missing_services:
            console.print_error("Recipe requires the following service(s) which are not installed:")
            for ms_name in missing_services:
                console.print_error(f"  - [item]{ms_name}[/]")
            return

    # All checks passed, write the recipe file
    try:
        target_recipe_path.write_text(recipe_content_str, encoding='utf-8')
        console.print(f"Recipe '[item]{effective_recipe_name}[/]' installed successfully from {source_description} to [path]{target_recipe_path}[/].")
        recipe_registry.clear()
        recipe_registry.load_from(directory_scheme.recipes) # Reload registry
        return RESTART # Signal CLI restart
    except Exception as e:
        console.print_error(f"Error writing recipe file to [path]{target_recipe_path}[/]: {e}")

@app.command()
def uninstall_recipe(
    recipe_name: Annotated[str | None,
                           typer.Argument(autocompletion=recipe_completer,
                                          help="The name of the recipe to be uninstalled.")]=None,
                 save_to: Annotated[Path | None,
                       typer.Option(dir_okay=False, writable=True,
                                    help="Optional. Path to save the recipe file before uninstalling it.")]=None
    ):
    """Uninstalls a Saturnin recipe from the environment.

    If the `--save-to` option is provided, the content of the recipe file
    will be saved to the specified path before the original recipe file is deleted
    from Saturnin's recipes directory.
    """
    recipe: RecipeInfo = recipe_registry.get(recipe_name)
    if recipe is None:
        console.print_error(f"Recipe '[item]{recipe_name}[/]' not installed.")
        return

    if save_to:
        try:
            save_to.parent.mkdir(parents=True, exist_ok=True) # Ensure destination directory exists
            content_to_save = recipe.filename.read_text(encoding='utf-8')
            save_to.write_text(content_to_save, encoding='utf-8')
            console.print(f"Recipe '[item]{recipe_name}[/]' content saved to [path]{save_to}[/].")
        except Exception as e:
            console.print_error(f"Error saving recipe to [path]{save_to}[/]: {e}")
            # Decide if this should be a fatal error for the uninstall operation
            if not typer.confirm("Proceed with uninstallation despite saving error?", default=False):
                console.print("Uninstallation cancelled.")
                return
    try:
        recipe.filename.unlink()
        console.print(f"Recipe '[item]{recipe_name}[/]' uninstalled successfully.")
        recipe_registry.clear()
        recipe_registry.load_from(directory_scheme.recipes) # Reload registry
        return RESTART # Signal CLI restart
    except FileNotFoundError: # Should not happen if recipe was in registry, but good for robustness
        console.print_warning(f"Recipe file [path]{recipe.filename}[/] already deleted or moved.")
        recipe_registry.clear() # Still reload, as it might be out of sync
        recipe_registry.load_from(directory_scheme.recipes)
        return RESTART
    except Exception as e:
        console.print_error(f"Error uninstalling recipe '[item]{recipe_name}[/]' ([path]{recipe.filename}[/]): {e}")

@app.command()
def create_recipe(
    recipe_name: Annotated[str, typer.Argument(help="A unique name for the new recipe.",
                                               metavar='RECIPE_NAME')],
    components: Annotated[list[str],
                          typer.Argument(help="One or more service UIDs or names to include in the recipe. "
                                         "If multiple services are provided, a 'bundle' recipe is created; "
                                         "otherwise, a 'service' recipe is created.",
                                         autocompletion=service_completer)],
    *,
    plain: Annotated[bool, typer.Option('--plain',
                                        help="Create the recipe template without explanatory comments.")]=False,
           ):
    """Creates a new recipe template file for the specified Saturnin service(s).

    The generated recipe file will contain default configurations for the listed
    services. This template typically requires further modification to suit specific
    needs.

    - If one component is specified, a 'service' type recipe is created.

    - If multiple components are specified, a 'bundle' type recipe is created.

    ---

    After generating the template, it will be opened in an external editor for
    immediate customization. If saved, the new recipe is installed.
    """
    if recipe_name in recipe_registry:
        console.print_error(f"Recipe '{recipe_name}' already exists")
        return None
    #
    if application_registry.contains(lambda x: x.recipe_factory is None
                                     and x.get_recipe_name() == recipe_name):
        console.print_error(f"Recipe '[item]{recipe_name}[/]' cannot be created. "
                            "Application of the same name is already installed.")
        return
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
        except Exception:
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
