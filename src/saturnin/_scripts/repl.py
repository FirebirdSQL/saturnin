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

"""Read-Eval-Print Loop (REPL) implementation for Typer applications.

This module provides the core functionality for an interactive command-line
interface, leveraging `prompt-toolkit` for advanced features like command
history, auto-suggestion, and custom key bindings. It includes a custom
completer (`.CustomClickCompleter`) that integrates with Click/Typer's
command structure to offer context-aware command and parameter completion.
The `.IOManager` class handles input/output redirection and console management
within the REPL environment.
"""

from __future__ import annotations

import shlex
import sys
from collections.abc import Callable
from io import StringIO
from operator import attrgetter
from pathlib import Path
from typing import Any, Self, TextIO

import click
from click.exceptions import Abort as ClickAbort
from click.exceptions import Exit as ClickExit
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import prompt
from rich.console import Console
from saturnin.base import RESTART, RestartError, directory_scheme
from saturnin.lib.console import FORCE_TERMINAL
from saturnin.lib.console import console as cm

EchoCallback = Callable[[str], None]

#: Prompt-toolkit key bindings instance.
kb = KeyBindings()

@kb.add('c-space')
def _(event):
    """Key binding handler for `Ctrl+Space`.

    Initializes autocompletion if not active, or selects the next
    completion if autocompletion is already active.
    """
    buff = event.app.current_buffer
    if buff.complete_state:
        buff.complete_next()
    else:
        buff.start_completion(select_first=False)

class CustomClickCompleter(Completer):
    """Custom `prompt-toolkit` completer for Click/Typer applications.

    This completer integrates with the Click command structure to provide
    context-aware completions for commands, subcommands, options, and
    argument values. It adapts Click's internal shell completion logic
    for use with `prompt-toolkit`.

    Arguments:
      cli: The root Click/Typer command group object.
    """
    def __init__(self, cli):
        self.cli = cli

    def get_completions(self, document, complete_event=None): # noqa: ARG002
        """Yields completion suggestions based on the current input document.

        This method parses the current command line input, resolves the Click
        context, and generates a list of relevant completions. Completions can
        include:

        - Subcommands of the current command group.
        - Options available for the current command.
        - Values for options (e.g., choices from `click.Choice`).
        - Values for arguments (e.g., choices or shell-completed values).
        - Special commands like 'quit'.

        It handles partial input by filtering suggestions that start with the
        incomplete word at the cursor.

        Arguments:
            document: The `prompt_toolkit.document.Document` representing the
                      current state of the input buffer.
            complete_event: The `prompt_toolkit.completion.CompleteEvent`
                            triggering the completion (not directly used here).

        Yields:
            `prompt_toolkit.completion.Completion`:
                Completion objects for `prompt-toolkit` to display.
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

class IOManager:
    """Manages I/O operations and state for the REPL.

    This class handles command prompting, input sources (stdin or queued commands),
    output redirection (to console or file), and maintains the REPL's
    interaction state. It also configures `prompt-toolkit` settings like
    history and autocompletion.

    Arguments:
      context: The current Click context.
      echo:    Optional callback invoked with the command line string before it's executed.
      console: Custom Rich console for output. If `None`, Saturnin's standard console
               (`cm.std_console`) is used.
    """
    def __init__(self, context, *, echo: EchoCallback | None=None, console: Console | None=None):
        #: The Rich console instance for REPL output.
        self.console: Console = cm.std_console if console is None else console
        #: Flag indicating if output is being recorded as HTML.
        self.html_output: bool = False
        #: File object if output is redirected, else None.
        self.output_file: TextIO | None = None
        #: Path to the output file if redirected.
        self.output_filename: Path | None = None
        #: Optional callback for echoing executed commands.
        self.echo: EchoCallback | None = echo
        #: List of commands to run non-interactively.
        self.run_commands: list[str] = []
        #: True if stdin is a TTY, False otherwise.
        self.isatty: bool = sys.stdin.isatty()
        self.saved_stdin = sys.stdin
        self.saved_stdout = sys.stdout
        self.pipe_in = StringIO()
        self.pipe_out = StringIO()
        #: Arguments passed to `prompt_toolkit.prompt`.
        self.prompt_kwargs: dict[str, Any] = {}
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
        #: Queue for pipelined commands.
        self.cmd_queue = []
    def __enter__(self) -> Self:
        """Enters the context, returning self."""
        return self
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Exits the context, restoring stdin/stdout and the console."""
        sys.stdin = self.saved_stdin
        sys.stdout = self.saved_stdout
        self.restore_console()
    def _is_internal_cmd(self, cmd: str) -> bool:
        """Checks if a command string is an internal REPL command.

        Internal commands include 'help', 'quit', and commands starting with '?'.

        Arguments:
            cmd: The command string to check.

        Returns:
            True if the command is internal, False otherwise.
        """
        cmd = cmd.rstrip().split(' ')[0]
        if cmd.lower() in ['help', 'quit']:
            return True
        if cmd.startswith('?'):
            return True
        return False
    def _get_next_cmd(self) -> str:
        """Retrieves the next command from the internal `cmd_queue`.

        This method also handles redirection of stdin/stdout for piped commands
        within the queue.

        Returns:
            The next command from the queue.
        """
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
        """Fetches the next command string.

        Reads from `.run_commands` list first, then from `sys.stdin` if not a TTY,
        otherwise prompts the user using `prompt-toolkit`.

        Returns:
            The command string entered by the user or read from input.
        """
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
        """Returns the next command to be executed.

        Prioritizes commands from the internal queue (`.cmd_queue`). If the
        queue is empty, it fetches a command using `._get_command`.
        If an `echo` callback is set, it's invoked with the command.

        Returns:
            The command string.
        """
        if self.cmd_queue:
            return self._get_next_cmd()
        command = self._get_command()
        if self.echo and command.strip():
            self.echo(command)
        sys.stdin = self.saved_stdin
        sys.stdout = self.saved_stdout
        return command
    def reset_queue(self) -> None:
        """Clears the internal command queue (`.cmd_queue`).

        If commands were in the queue, a message is printed to the console.
        stdin and stdout are restored to their saved states.
        """
        i = len(self.cmd_queue)
        self.cmd_queue.clear()
        sys.stdin = self.saved_stdin
        sys.stdout = self.saved_stdout
        if i > 0:
            self.console.print(f'Remaining {i} command(s) not executed')
    def redirect_console(self, filename: Path) -> None:
        """Redirects REPL console output to the specified file.

        If the filename has an HTML-like suffix (e.g., '.html', '.htm'),
        the output will be recorded for saving as HTML.

        Arguments:
          filename: The path to the file for console output.
        """
        if self.output_file is not None:
            self.output_file.close()
        self.output_file = filename.open(mode='w', encoding='utf8')
        self.output_filename = filename
        self.html_output = filename.suffix.startswith('.htm')
        self.console = Console(file=self.output_file, width=5000, force_terminal=FORCE_TERMINAL,
                               emoji=False, record=self.html_output)
    def restore_console(self) -> None:
        """Restores console output to the original Rich console (`cm.std_console`).

        If output was being redirected to a file, the file is closed.
        If HTML recording was active, `console.save_html()` is called.
        """
        if self.output_file is not None:
            self.output_file.close()
            self.output_file = None
            if self.html_output:
                self.console.save_html(self.output_filename)
        self.console = cm.std_console

def repl(context, ioman: IOManager) -> bool:
    """Runs the main Read-Eval-Print Loop.

    This function continuously prompts for commands, executes them using the
    Click/Typer application context, and handles exceptions and special
    REPL commands (like 'quit', 'help', '?').

    Arguments:
      context: The current Click context for the REPL.
      ioman: The `IOManager` instance managing REPL I/O.

    Returns:
       bool: True if the REPL should be restarted (e.g., due to `RestartError`),
             False otherwise for a normal exit.

    Behavior:

    - If stdin is not a TTY, commands are read from stdin without a prompt.
    - Handles `KeyboardInterrupt` by continuing the loop.
    - Handles `EOFError` (e.g., Ctrl+D) by exiting the loop.
    - Internal commands ('quit', 'help', '?<cmd>') are processed specially.
    - Other commands are parsed and invoked via the Click application group.
    - Catches and displays Click exceptions, `SystemExit`, and `RestartError`.
    """
    group_ctx = context.parent or context
    group_ctx.info_name = '' # Reset info_name for REPL context
    group = group_ctx.command
    # Clear params that might have been inherited from a direct CLI invocation
    # This ensures a clean state for each command entered in the REPL.
    if hasattr(group, 'params') and isinstance(group.params, list):
         # This check might be overly cautious; Click groups usually don't have params manipulated this way
         # but it's safer if some custom group behavior exists.
         # A more standard Click approach would be to ensure the context passed to `make_context` is clean.
         # However, modifying group.params directly as done in the original code isn't standard.
         # Let's assume `group.params.clear()` was intended if `params` was a mutable sequence.
         # For safety, we ensure it's a list before trying to clear.
        if isinstance(getattr(group, 'params', None), list):
            group.params.clear()

    while True:
        try:
            command = ioman.get_command()
        except KeyboardInterrupt:
            # Handle Ctrl+C: print newline and continue
            ioman.console.print() # Ensures the next prompt is on a new line
            continue
        except EOFError:
            # Handle Ctrl+D: exit REPL gracefully
            ioman.console.print() # Newline before exiting
            break
        if not command:
            if ioman.isatty:
                # Empty command in TTY, just loop
                continue
            # Empty command from non-TTY (e.g., end of script), exit
            break
        # Internal commands
        if ioman._is_internal_cmd(command):
            cmd = command.rstrip()
            if cmd.lower() == 'help':
                command = '--help'
            elif cmd.startswith('?'):
                command = cmd[1:] + ' --help' # Transform '?foo' to 'foo --help'
            elif cmd.lower() == 'quit':
                break
        # Special commands (example for 'pip' might need adjustment based on actual commands)
        # This block seems specific and might need to be generalized or made more robust
        # if more "special" prefix commands are expected.
        for cmd_prefix in ('pip ', 'install package ', 'uninstall package '):
            if command.startswith(cmd_prefix):
                # Insert '--' to stop option parsing for arguments passed to the subcommand
                command = command[:len(cmd_prefix)] + '-- ' + command[len(cmd_prefix):]
                break
        try:
            args = shlex.split(command)
            # `_resolve_context` is internal; using it might be brittle.
            # However, it's often used in such REPL integrations with Click.
            # A more public way isn't readily available for this specific pre-resolution.
            # click.shell_completion._resolve_context(group, {}, "", args) # This was for completion context
        except ValueError as exc:
            # Handle errors from shlex.split (e.g., unmatched quotes)
            ioman.console.print(f"[error]{type(exc).__name__}: {exc}[/error]")
            continue
        try:
            # Create a new context for each command invocation
            with group.make_context(info_name=group_ctx.info_name or sys.argv[0], args=args, parent=group_ctx) as ctx:
                result = group.invoke(ctx)
                if result is RESTART:
                    raise RestartError # Propagate restart request
        except click.ClickException as exc:
            # Click-specific exceptions (e.g., UsageError) have their own show method
            exc.show()
            ioman.reset_queue() # Clear any pipelined commands if current one failed
        except ClickExit:
            # Click's way of signaling a clean exit, usually via ctx.exit()
            # In a REPL, we typically don't want the REPL itself to exit from this.
            pass
        except ClickAbort:
            # User aborted (e.g. Ctrl+C during a prompt within a command)
            cm.print_error("Aborted!")
            # sys.exit(1) # Exiting the whole REPL on abort might be too drastic
            ioman.reset_queue()
        except SystemExit:
            # General sys.exit() call from within a command
            # Similar to ClickExit, we might not want the REPL to terminate.
            pass
        except RestartError:
            # Signal that the REPL needs to be restarted
            return True
        except Exception as exc:
            # Catch-all for other exceptions from command execution
            cm.print_error(f"{exc.__class__.__name__}: {exc!s}")
            ioman.reset_queue() # Clear queue on general error
    return False # Normal exit from REPL
