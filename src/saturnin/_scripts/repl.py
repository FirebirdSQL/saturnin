#coding:utf-8
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
# Based on code from https://github.com/click-contrib/click-repl

"""REPL for Typer application
"""

from __future__ import annotations
from typing import Dict, Any, List, TextIO, Callable, Optional
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.shortcuts import prompt
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from pathlib import Path
import click
import shlex
import sys
from io import StringIO
from click.exceptions import Exit as ClickExit
from rich.console import Console
from saturnin.base._site import site, FORCE_TERMINAL

EchoCallback = Callable[[str], None]

kb = KeyBindings()

@kb.add('c-space')
def _(event):
    " Initialize autocompletion, or select the next completion. "
    buff = event.app.current_buffer
    if buff.complete_state:
        buff.complete_next()
    else:
        buff.start_completion(select_first=False)

class ClickCompleter(Completer):
    def __init__(self, cli):
        self.cli = cli

    def get_completions(self, document, complete_event=None):
        # Code analogous to click._bashcomplete.do_complete

        try:
            txt = document.text_before_cursor
            i = txt.rfind('|')
            if i >= 0:
                txt = txt[i+1:].lstrip()
            if txt.startswith('?'):
                txt = txt[1:]
            args = shlex.split(txt)
        except ValueError:
            # Invalid command, perhaps caused by missing closing quotation.
            return

        cursor_within_command = (
            document.text_before_cursor.rstrip() == document.text_before_cursor
        )

        if args and cursor_within_command:
            # We've entered some text and no space, give completions for the
            # current word.
            incomplete = args.pop()
        else:
            # We've not entered anything, either at all or for the current
            # command, so give all relevant completions for this context.
            incomplete = ""
        ctx = click.shell_completion._resolve_context(self.cli, {}, "", args)
        last_arg = args[-1] if args else ''

        if ctx is None:
            return

        choices = []
        for param in ctx.command.params:
            if isinstance(param, click.Option):
                if isinstance(param.type, click.Choice) and (last_arg in param.opts or last_arg in param.secondary_opts):
                    for choice in param.type.choices:
                        choices.append(Completion(str(choice), -len(incomplete)))
        if not choices:
            for param in ctx.command.params:
                if isinstance(param, click.Option):
                    for options in (param.opts, param.secondary_opts):
                        for o in options:
                            choices.append(Completion(str(o), -len(incomplete), display_meta=param.help))
                elif isinstance(param, click.Argument):
                    if isinstance(param.type, click.Choice):
                        for choice in param.type.choices:
                            choices.append(Completion(str(choice), -len(incomplete)))

            if isinstance(ctx.command, click.MultiCommand):
                for name in ctx.command.list_commands(ctx):
                    command = ctx.command.get_command(ctx, name)
                    if not command.hidden:
                        choices.append(Completion(str(name),-len(incomplete),
                                                  display_meta=getattr(command, "short_help")))

        for item in choices:
            if item.text.startswith(incomplete):
                yield item

class IOManager:
    """
    """
    def __init__(self, old_ctx, *, echo: Optional[EchoCallback]=None, database: str='',
                 add_report: bool=False, report_cmds: List[str]=None, console: Console=None):
        self.console: Console = site.console if console is None else console
        self.html_output: bool = False
        self.output_file: TextIO = None
        self.output_filename: Path = None
        self.echo: Optional[EchoCallback] = echo
        self.database: str = database
        self.add_report: bool = add_report
        self.report_cmds: List[str] = [] if report_cmds is None else [x.lower() for x in report_cmds]
        self.run_commands: List[str] = []
        self.isatty: bool = sys.stdin.isatty()
        self.saved_stdin = sys.stdin
        self.saved_stdout = sys.stdout
        self.pipe_in = StringIO()
        self.pipe_out = StringIO()
        self.prompt_kwargs: Dict[str, Any] = {}
        group_ctx = old_ctx.parent or old_ctx
        defaults = {
            'history': InMemoryHistory(),
            'completer': ClickCompleter(group_ctx.command),
            'message': '> ',
            'key_bindings': kb,
            'auto_suggest': AutoSuggestFromHistory()
        }
        for key in defaults:
            default_value = defaults[key]
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
        elif cmd.startswith('?'):
            return True
        return False
    def _is_report_cmd(self, cmd: str) -> bool:
        return cmd.rstrip().lower().split(' ')[0] in self.report_cmds
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
        if self.cmd_queue:
            return self._get_next_cmd()
        command = self._get_command()
        if self.echo and command.strip():
            self.echo(command)
        if self.add_report and self._is_report_cmd(command) and not '--help' in command:
            command += f'| report {self.database}'
        if '|' in command:
            self.cmd_queue = [cmd.strip() for cmd in command.split('|')]
            return self._get_next_cmd()
        sys.stdin = self.saved_stdin
        sys.stdout = self.saved_stdout
        return command
    def reset_queue(self) -> None:
        i = len(self.cmd_queue)
        self.cmd_queue.clear()
        sys.stdin = self.saved_stdin
        sys.stdout = self.saved_stdout
        cnt = 1 if self.add_report else 0
        if i > cnt:
            self.console.print(f'Remaining {i} command(s) not executed')
    def redirect_console(self, filename: Path) -> None:
        if self.output_file is not None:
            self.output_file.close()
        self.output_file = filename.open(mode='w', encoding='utf8')
        self.output_filename = filename
        self.html_output = filename.suffix.startswith('.htm')
        self.console = Console(file=self.output_file, width=5000, force_terminal=FORCE_TERMINAL,
                               emoji=False, record=self.html_output)
    def restore_console(self) -> None:
        if self.output_file is not None:
            self.output_file.close()
            self.output_file = None
            if self.html_output:
                self.console.save_html(self.output_filename)
        self.console = site.console

def repl(old_ctx, ioman: IOManager):
    """
    Start an interactive shell. All subcommands are available in it.

    Arguments:
    old_ctx:     Current Click context.
    ioman:  IOManager instance.

    If stdin is not a TTY, no prompt will be printed, but commands are read
    from stdin.
    """

    group_ctx = old_ctx.parent or old_ctx
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
            else:
                break
        # Special commands
        if command.startswith('pip '):
            command = command[:4] + ' -- ' + command[4:]
        # Internal commands
        if ioman._is_internal_cmd(command):
            cmd = command.rstrip()
            if cmd.lower() == 'help':
                command = '--help'
            elif cmd.startswith('?'):
                command = cmd[1:] + ' --help'
            elif cmd.lower() == 'quit':
                break
        try:
            args = shlex.split(command)
            ctx = click.shell_completion._resolve_context(group, {}, "", args)
        except ValueError as e:
            ioman.console.print("{}: {}".format(type(e).__name__, e))
            continue
        try:
            with group.make_context(None, args, parent=group_ctx) as ctx:
                group.invoke(ctx)
                ctx.exit()
        except click.ClickException as e:
            e.show()
            ioman.reset_queue()
        except ClickExit:
            pass
        except SystemExit:
            pass
