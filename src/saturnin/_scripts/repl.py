# SPDX-FileCopyrightText: 2022-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
#   PROGRAM/MODULE: saturnin
#   FILE:           saturnin/_scripts/repl.py
#   DESCRIPTION:    REPL for Typer application
#   CREATED:        05.08.2022
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
# Initial code is based on https://github.com/click-contrib/click-repl
#
# Contributor(s): Pavel Císař (initial code)
#                 ______________________________________
# pylint: disable=W0212

"""REPL for Typer application
"""

from __future__ import annotations
from typing import Dict, Any, List, TextIO, Callable, Optional
from pathlib import Path
from operator import attrgetter
import shlex
import sys
from io import StringIO
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.shortcuts import prompt
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
import click
from click.exceptions import Exit as ClickExit, Abort as ClickAbort
from rich.console import Console
from saturnin.base import RestartError, RESTART, directory_scheme
from saturnin.lib.console import console as cm, FORCE_TERMINAL

EchoCallback = Callable[[str], None]

#: Prompt-toolkit key bindings
kb = KeyBindings()

@kb.add('c-space')
def _(event):
    " Initialize autocompletion, or select the next completion. "
    buff = event.app.current_buffer
    if buff.complete_state:
        buff.complete_next()
    else:
        buff.start_completion(select_first=False)

class CustomClickCompleter(Completer):
    """Custom prompt-toolkit completer.

    It provides command completion for Typer/Click commands and parameters, including
    option/parameter values.

    Arguments:
      cli: Root Typer command group
    """
    def __init__(self, cli):
        self.cli = cli

    def get_completions(self, document, complete_event=None):
        """Yields completion choices.
        """
        # Code analogous to click._bashcomplete.do_complete
        try:
            txt = document.text_before_cursor
            in_help: bool = txt.startswith('?')
            if in_help:
                txt = txt[1:]
            args = shlex.split(txt)
        except ValueError:
            # Invalid command, perhaps caused by missing closing quotation.
            return

        cursor_within_command = (document.text_before_cursor.rstrip()
                                 == document.text_before_cursor)

        if args and cursor_within_command:
            # We've entered some text and no space, give completions for the
            # current word.
            incomplete = args.pop()
        else:
            # We've not entered anything, either at all or for the current
            # command, so give all relevant completions for this context.
            incomplete = ""
        ctx = click.shell_completion._resolve_context(self.cli, {}, "", args)
        if ctx is None:
            return

        last_arg = args[-1] if args else ''

        choices = []
        stop: bool = in_help
        if isinstance(ctx.command, click.MultiCommand):
            # Completion is list of commands at given context level
            if not args:
                choices.append(Completion('quit', -len(incomplete),
                                          display_meta="Quit Saturnin console"))
            for name in ctx.command.list_commands(ctx):
                command = ctx.command.get_command(ctx, name)
                if not command.hidden:
                    choices.append(Completion(str(name),-len(incomplete),
                                              display_meta=command.get_short_help_str()))
            stop = stop or choices
        if not stop:
            # First check whether we're entering value for option.
            for param in ctx.command.params:
                if (isinstance(param, click.Option)
                    and not param.is_flag
                    and (last_arg in param.opts or last_arg in param.secondary_opts)):
                    # Completion are possible values for last option, if applicable
                    if isinstance(param.type, click.Choice):
                        for choice in param.type.choices:
                            choices.append(Completion(str(choice), -len(incomplete)))
                    else:
                        choices.extend(Completion(str(item.value), -len(incomplete),
                                                  display_meta=item.help)
                                       for item in param.shell_complete(args, incomplete))
                    stop = True # Do not continue even if we don't have choices!
            stop = stop or choices
        if not stop:
            # We're looking for possible argument values or option
            # First we build list of already processed options and arguments...
            not_processed_params = []
            for param in ctx.command.params:
                if isinstance(param, click.Option):
                    if ctx.params[param.name] == param.default:
                        not_processed_params.append(param)
            if not incomplete.startswith('-'):
                for param in ctx.command.params:
                    if isinstance(param, click.Argument):
                        if (param.nargs == 1) and (ctx.params[param.name] == param.default):
                            not_processed_params.append(param)
                            break
                        elif param.nargs == -1:
                            not_processed_params.append(param)
                            break
            #
            for param in not_processed_params:
                if isinstance(param, click.Option):
                    # Completion is list of options
                    for options in (param.opts, param.secondary_opts):
                        for opt in options:
                            choices.append(Completion(str(opt), -len(incomplete),
                                                      display_meta=param.help))
                elif isinstance(param, click.Argument):
                    # Completion are values for argument, if applicable
                    if isinstance(param.type, click.Choice):
                        for choice in param.type.choices:
                            choices.append(Completion(str(choice), -len(incomplete),
                                                      display_meta=param.help))
                    else:
                        choices.extend(Completion(str(item.value), -len(incomplete),
                                                  display_meta=item.help if item.help
                                                  else param.help)
                                       for item in param.shell_complete(args, incomplete))
        stop = stop or choices

        choices.sort(key=attrgetter('text'))
        for item in choices:
            if item.text.startswith(incomplete):
                yield item

class IOManager: # pylint: disable=R0902
    """REPL I/O manager.

    Handles command prompt, stdin/stdout redirection etc.

    Arguments:
      context: Current Click context
      echo:    Callback called with command line before it's executed.
      console: Costom Rich console for output. If not provided, Saturnin standard console
               is used.
    """
    def __init__(self, context, *, echo: Optional[EchoCallback]=None, console: Console=None):
        self.console: Console = cm.std_console if console is None else console
        self.html_output: bool = False
        self.output_file: TextIO = None
        self.output_filename: Path = None
        self.echo: Optional[EchoCallback] = echo
        self.run_commands: List[str] = []
        self.isatty: bool = sys.stdin.isatty()
        self.saved_stdin = sys.stdin
        self.saved_stdout = sys.stdout
        self.pipe_in = StringIO()
        self.pipe_out = StringIO()
        self.prompt_kwargs: Dict[str, Any] = {}
        group_ctx = context.parent or context
        defaults = {
            'history': FileHistory(str(directory_scheme.history_file)),
            'completer': CustomClickCompleter(group_ctx.command),
            'message': '> ',
            'key_bindings': kb,
            'auto_suggest': AutoSuggestFromHistory()
        }
        for key, default_value in defaults.items():
            if key not in self.prompt_kwargs:
                self.prompt_kwargs[key] = default_value
        #
        self.cmd_queue = []
    def __enter__(self) -> IOManager:
        return self
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        sys.stdin = self.saved_stdin
        sys.stdout = self.saved_stdout
        self.restore_console()
    def _is_internal_cmd(self, cmd: str) -> bool:
        cmd = cmd.rstrip().split(' ')[0]
        if cmd.lower() in ['help', 'quit']:
            return True
        if cmd.startswith('?'):
            return True
        return False
    def _get_next_cmd(self) -> str:
        command = self.cmd_queue.pop(0)
        self.pipe_in = self.pipe_out
        self.pipe_in.seek(0)
        sys.stdin = self.pipe_in
        if self.cmd_queue:
            self.pipe_out = StringIO()
            sys.stdout = self.pipe_out
        else:
            sys.stdout = self.saved_stdout
        return command
    def _get_command(self) -> str:
        "Returns next command fetched from queue, stdin or console prompt."
        sys.stdin = self.saved_stdin
        sys.stdout = self.saved_stdout
        self.pipe_out = StringIO()
        if self.run_commands:
            command = self.run_commands.pop(0)
        elif not self.isatty:
            command = sys.stdin.readline()
        else:
            command = prompt(**self.prompt_kwargs)
        return command
    def get_command(self) -> str:
        "Returns next command."
        if self.cmd_queue:
            return self._get_next_cmd()
        command = self._get_command()
        if self.echo and command.strip():
            self.echo(command)
        sys.stdin = self.saved_stdin
        sys.stdout = self.saved_stdout
        return command
    def reset_queue(self) -> None:
        "Clear command queue"
        i = len(self.cmd_queue)
        self.cmd_queue.clear()
        sys.stdin = self.saved_stdin
        sys.stdout = self.saved_stdout
        if i > 0:
            self.console.print(f'Remaining {i} command(s) not executed')
    def redirect_console(self, filename: Path) -> None:
        """Redirects console output to file.

        Arguments:
          filename: File for console output.
        """
        if self.output_file is not None:
            self.output_file.close()
        self.output_file = filename.open(mode='w', encoding='utf8')
        self.output_filename = filename
        self.html_output = filename.suffix.startswith('.htm')
        self.console = Console(file=self.output_file, width=5000, force_terminal=FORCE_TERMINAL,
                               emoji=False, record=self.html_output)
    def restore_console(self) -> None:
        "Closes the output file and restores output to console."
        if self.output_file is not None:
            self.output_file.close()
            self.output_file = None
            if self.html_output:
                self.console.save_html(self.output_filename)
        self.console = cm.std_console

def repl(context, ioman: IOManager) -> bool: # pylint: disable=R0912
    """
    Start an interactive shell. All subcommands are available in it.

    Arguments:
      context: Current Click context.
      ioman:   IOManager instance.

    Returns:
       True if REPL should be restarted, otherwise returns False.

    If stdin is not a TTY, no prompt will be printed, but commands are read
    from stdin.
    """
    group_ctx = context.parent or context
    group_ctx.info_name = ''
    group = group_ctx.command
    group.params.clear()
    while True:
        try:
            command = ioman.get_command()
        except KeyboardInterrupt:
            continue
        except EOFError:
            break
        if not command:
            if ioman.isatty:
                continue
            break
        # Internal commands
        if ioman._is_internal_cmd(command):
            cmd = command.rstrip()
            if cmd.lower() == 'help':
                command = '--help'
            elif cmd.startswith('?'):
                command = cmd[1:] + ' --help'
            elif cmd.lower() == 'quit':
                break
        # Special commands
        for cmd in ('pip ', 'install package ', 'uninstall package '):
            if command.startswith(cmd):
                command = command[:len(cmd)] + ' -- ' + command[len(cmd):]
                break
        try:
            args = shlex.split(command)
            ctx = click.shell_completion._resolve_context(group, {}, "", args)
        except ValueError as exc:
            ioman.console.print(f"{type(exc).__name__}: {exc}")
            continue
        try:
            with group.make_context(None, args, parent=group_ctx) as ctx:
                result = group.invoke(ctx)
                #ctx.exit()
                if result is RESTART:
                    raise RestartError
        except click.ClickException as exc:
            exc.show()
            ioman.reset_queue()
        except ClickExit as exc:
            pass
            #sys.exit(exc.exit_code)
        except ClickAbort as exc:
            cm.print_error("Aborted!")
            sys.exit(1)
        except SystemExit:
            pass
        except RestartError:
            return True
        except Exception as exc: # pylint: disable=W0703
            cm.print_error(f"{exc.__class__.__name__}:{exc!s}")
    return False
