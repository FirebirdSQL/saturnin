# SPDX-FileCopyrightText: 2020-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/lib/data/console.py
# DESCRIPTION:    Saturnin console manager
# CREATED:        7.12.2020
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
# Copyright (c) 2020 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________

"""Saturnin console manager for terminal configuration and output.

This module leverages the `rich` library to provide styled and formatted
console output. It includes a default theme, a custom highlighter for
Saturnin-specific syntax, and a `ConsoleManager` class to manage
standard and error output streams.
"""

from __future__ import annotations

import os
import sys
from typing import ClassVar

from rich.console import Console
from rich.highlighter import RegexHighlighter
from rich.text import Text
from rich.theme import Theme
from saturnin.base import directory_scheme

#: Default console theme
DEFAULT_THEME: Theme = Theme(
    {'option': 'bold cyan',
     'switch': 'bold green',
     'metavar': 'bold yellow',
     'section': 'bold white',
     'help_require': 'dim',
     'args_and_cmds': 'yellow',
     'path': 'bold cyan',
     'title': 'bold yellow',
     'ok': 'green',
     'important': 'bold yellow',
     'warning': 'bold yellow',
     'error': 'bold red',
     'item': 'green',
     'attrib_equal': 'bold',
     'attrib_name': 'not italic yellow',
     'attrib_value': 'not italic magenta',
     'bool_false': 'italic bright_red',
     'bool_true': 'italic bright_green',
     'brace': 'bold',
     'call': 'bold magenta',
     'comma': 'bold',
     'ellipsis': 'yellow',
     'eui48': 'bold bright_green',
     'eui64': 'bold bright_green',
     'filename': 'bright_magenta',
     'indent': 'dim green',
     'ipv4': 'bold bright_green',
     'ipv6': 'bold bright_green',
     'py_none': 'italic magenta',
     'number': 'bold not italic cyan',
     'number_complex': 'bold not italic cyan',
     'str': 'not bold not italic green',
     'tag_contents': 'default',
     'tag_end': 'bold',
     'tag_name': 'bold bright_magenta',
     'tag_start': 'bold',
     'url': 'not bold not italic underline bright_blue',
     'zmq_address': 'not bold not italic bright_blue',
     'uuid': 'not bold bright_yellow',
     'uuid2': 'not bold bright_yellow',
     'mime': 'bold blue',
     'mime_param': 'italic cyan',
     'enum': 'bold not italic white',
     'email': 'bold magenta',
     'date': 'blue',
     'time': 'magenta',
     'timezone': 'yellow',
     })

#: Use rich terminal or not
FORCE_TERMINAL: bool = True if os.getenv("FORCE_COLOR") or os.getenv("PY_COLORS") else None

#: Standard rich text for YES
RICH_YES: Text = Text('✔', style='ok')
#: Standard rich text for NO
RICH_NO: Text = Text('✖', style='error')
#: Standard rich text for OK
RICH_OK: Text = Text('OK', style='ok')
#: Standard rich text for WARNING
RICH_WARNING: Text = Text('WARNING', style='warning')
#: Standard rich text for ERROR
RICH_ERROR: Text = Text('ERROR', style='error')
#: Standard rich N/A (Not Available/Aplicable)
RICH_NA: Text = Text('N/A', style='dim')

def _combine_regex(*regexes: str) -> str:
    """Combine a number of regexes in to a single regex.

    Returns:
        str: New regex with all regexes ORed together.
    """
    return "|".join(regexes)

class SaturninHighlighter(RegexHighlighter):
    """Custom RegexHighlighter for Saturnin console output, designed to highlight
    command-line options, syntax elements like paths, URLs, UUIDs, dates, times, and other
    Saturnin-specific or common data patterns.
    """
    #: Regular expressions used by `.highlight`.
    highlights: ClassVar[list[str]] = [
        r"(^|\W)(?P<switch>\-\w+)(?![a-zA-Z0-9])",
        r"(^|\W)(?P<option>\-\-[\w\-]+)(?![a-zA-Z0-9])",
        r"(?P<metavar>\<[^\>]+\>)",
        r"(?P<section>\n[A-Z][^:\n]*(:)\s?)",
        #
        # Dates
        #
        # Calendar month (e.g. 2008-08). The hyphen is required
        r"^(?P<year>[0-9]{4})-(?P<month>1[0-2]|0[1-9])$",
        # Calendar date w/o hyphens (e.g. 20080830)
        r"^(?P<date>(?P<year>[0-9]{4})(?P<month>1[0-2]|0[1-9])(?P<day>3[01]|0[1-9]|[12][0-9]))$",
        # Ordinal date (e.g. 2008-243). The hyphen is optional
        r"^(?P<date>(?P<year>[0-9]{4})-?(?P<day>36[0-6]|3[0-5][0-9]|[12][0-9]{2}|0[1-9][0-9]|00[1-9]))$",
        #
        # Weeks
        #
        # Week of the year (e.g., 2008-W35). The hyphen is optional
        r"^(?P<date>(?P<year>[0-9]{4})-?W(?P<week>5[0-3]|[1-4][0-9]|0[1-9]))$",
        # Week date (e.g., 2008-W35-6). The hyphens are optional
        r"^(?P<date>(?P<year>[0-9]{4})-?W(?P<week>5[0-3]|[1-4][0-9]|0[1-9])-?(?P<day>[1-7]))$",
        #
        # Times
        #
        # Hours and minutes (e.g., 17:21). The colon is optional
        r"^(?P<time>(?P<hour>2[0-3]|[01][0-9]):?(?P<minute>[0-5][0-9]))$",
        # Hours, minutes, and seconds w/o colons (e.g., 172159)
        r"^(?P<time>(?P<hour>2[0-3]|[01][0-9])(?P<minute>[0-5][0-9])(?P<second>[0-5][0-9]))$",
        # Time zone designator (e.g., Z, +07 or +07:00). The colons and the minutes are optional
        r"^(?P<timezone>(Z|[+-](?:2[0-3]|[01][0-9])(?::?(?:[0-5][0-9]))?))$",
        # Hours, minutes, and seconds with time zone designator (e.g., 17:21:59+07:00).
        # All the colons are optional. The minutes in the time zone designator are also optional
        r"^(?P<time>(?P<hour>2[0-3]|[01][0-9])(?P<minute>[0-5][0-9])(?P<second>[0-5][0-9]))(?P<timezone>Z|[+-](?:2[0-3]|[01][0-9])(?::?(?:[0-5][0-9]))?)$",
        #
        # Date and Time
        #
        # Calendar date with hours, minutes, and seconds (e.g., 2008-08-30 17:21:59 or 20080830 172159).
        # A space is required between the date and the time. The hyphens and colons are optional.
        # This regex matches dates and times that specify some hyphens or colons but omit others.
        # This does not follow ISO 8601
        r"^(?P<date>(?P<year>[0-9]{4})(?P<hyphen>-)?(?P<month>1[0-2]|0[1-9])(?(hyphen)-)(?P<day>3[01]|0[1-9]|[12][0-9])) (?P<time>(?P<hour>2[0-3]|[01][0-9])(?(hyphen):)(?P<minute>[0-5][0-9])(?(hyphen):)(?P<second>[0-5][0-9]))$",
        #
        # XML Schema dates and times
        #
        # Date, with optional time zone (e.g., 2008-08-30 or 2008-08-30+07:00).
        # Hyphens are required. This is the XML Schema 'date' type
        r"^(?P<date>(?P<year>-?(?:[1-9][0-9]*)?[0-9]{4})-(?P<month>1[0-2]|0[1-9])-(?P<day>3[01]|0[1-9]|[12][0-9]))(?P<timezone>Z|[+-](?:2[0-3]|[01][0-9]):[0-5][0-9])?$",
        # Time, with optional fractional seconds and time zone (e.g., 01:45:36 or 01:45:36.123+07:00).
        # There is no limit on the number of digits for the fractional seconds. This is the XML Schema 'time' type
        r"^(?P<time>(?P<hour>2[0-3]|[01][0-9]):(?P<minute>[0-5][0-9]):(?P<second>[0-5][0-9])(?P<frac>\.[0-9]+)?)(?P<timezone>Z|[+-](?:2[0-3]|[01][0-9]):[0-5][0-9])?$",
        # Date and time, with optional fractional seconds and time zone (e.g., 2008-08-30T01:45:36 or 2008-08-30T01:45:36.123Z).
        # This is the XML Schema 'dateTime' type
        r"^(?P<date>(?P<year>-?(?:[1-9][0-9]*)?[0-9]{4})-(?P<month>1[0-2]|0[1-9])-(?P<day>3[01]|0[1-9]|[12][0-9]))T(?P<time>(?P<hour>2[0-3]|[01][0-9]):(?P<minute>[0-5][0-9]):(?P<second>[0-5][0-9])(?P<ms>\.[0-9]+)?)(?P<timezone>Z|[+-](?:2[0-3]|[01][0-9]):[0-5][0-9])?$",
        # Values
        _combine_regex(
            r"(?P<ipv4>[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})",
            r"(?P<ipv6>([A-Fa-f0-9]{1,4}::?){1,7}[A-Fa-f0-9]{1,4})",
            r"(?P<eui64>(?:[0-9A-Fa-f]{1,2}-){7}[0-9A-Fa-f]{1,2}|(?:[0-9A-Fa-f]{1,2}:){7}[0-9A-Fa-f]{1,2}|(?:[0-9A-Fa-f]{4}\.){3}[0-9A-Fa-f]{4})",
            r"(?P<eui48>(?:[0-9A-Fa-f]{1,2}-){5}[0-9A-Fa-f]{1,2}|(?:[0-9A-Fa-f]{1,2}:){5}[0-9A-Fa-f]{1,2}|(?:[0-9A-Fa-f]{4}\.){2}[0-9A-Fa-f]{4})",
            r"(?P<uuid>[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12})",
            r"(?P<uuid2>[a-fA-F0-9]{32})",
            r"(?P<call>[\w.]*?)\(",
            r"\b(?P<bool_true>True)\b|\b(?P<bool_false>False)\b|\b(?P<py_none>None)\b",
            r"(?P<ellipsis>\.\.\.)",
            r"(?P<number_complex>(?<!\w)(?:\-?[0-9]+\.?[0-9]*(?:e[-+]?\d+?)?)(?:[-+](?:[0-9]+\.?[0-9]*(?:e[-+]?\d+)?))?j)",
            r"(?P<number>(?<!\w)\-?[0-9]+\.?[0-9]*(e[-+]?\d+?)?\b|0x[0-9a-fA-F]*)",
            r"(?P<path>\B(/[-\w._+]+)*\/)(?P<filename>[-\w._+]*)?",
            r"(?<![\\\w])(?P<str>b?'''.*?(?<!\\)'''|b?'.*?(?<!\\)'|b?\"\"\".*?(?<!\\)\"\"\"|b?\".*?(?<!\\)\")",
            r"(?P<url>(file|https|http|ws|wss)://[-0-9a-zA-Z$_+!`(),.?/;:&=%#]*)",
            r"(?P<zmq_address>(inproc|ipc|tcp|pgm|epgm|vmci)://[-0-9a-zA-Z$_+!`(),.?/;:&=%#]*)",
            r"(?P<mime>(application|audio|font|example|image|message|model|multipart|text|video|x-(?:[0-9A-Za-z!#$%&'*+.^_`|~-]+))/([0-9A-Za-z!#$%&'*+.^_`|~-]+))(?P<mime_param>((?:[ \t]*;[ \t]*[0-9A-Za-z!#$%&'*+.^_`|~-]+=(?:[0-9A-Za-z!#$%&'*+.^_`|~-]+|\"(?:[^\"\\\\]|\\.)*\"))*))",
            r"(?P<enum>\b[A-Z_]*\b)",
            r"(?P<email>[.\w-]+@([\w-]+\.)+[\w-]+)",
        )
    ]
    def highlight(self, text: Text) -> Text:
        """Highlight a `~rich.text.Text` object using the defined regular expressions.

        This method iterates through the `highlights` list, applying each
        regex to the input `text` to style matching patterns.

        Arguments:
            text: The `~rich.text.Text` object to be highlighted.
        """
        highlight_regex = text.highlight_regex
        for re_highlight in self.highlights:
            highlight_regex(re_highlight, style_prefix=self.base_style)
        return text

#: Saturnin text highlighter
highlighter: SaturninHighlighter = SaturninHighlighter()
#: Shortcut to `highlighter.highlight`
_h = highlighter.highlight

class ConsoleManager:
    """Manages Rich Console instances for standard output and error streams within Saturnin,
    providing themed and highlighted output capabilities.
    """
    def __init__(self):
        #: Suppress output flag
        self.quiet: bool = False
        #: Verbose output flag
        self.verbose: bool = False
        #: Rich main console
        self.std_console: Console = Console(theme=Theme.read(directory_scheme.theme_file)
                                            if directory_scheme.theme_file.exists()
                                            else DEFAULT_THEME, tab_size=4, #emoji=False,
                                            highlighter=highlighter, highlight=True,
                                            force_terminal=FORCE_TERMINAL)
        if not sys.stdout.isatty():
            self.std_console.width = 5000
        #: Rich error console
        self.err_console: Console = Console(stderr=True, style='bold red', tab_size=4, #emoji=False,
                                            force_terminal=FORCE_TERMINAL)
    def print_info(self, message='') -> None:
        """Prints an informational message to the standard console, styled in yellow.
        Output is conditional on `.verbose` being True and `.quiet` being False.
        """
        if self.verbose and not self.quiet:
            if message:
                self.std_console.print(message, style='yellow')
            else:
                self.std_console.print()
    def print_warning(self, message) -> None:
        "Prints warning message to error console."
        self.err_console.print(message)
    def print_error(self, message) -> None:
        "Prints error message to error console."
        self.err_console.print(message)
    def print_exception(self) -> None:
        "Prints exception to error console."
        self.err_console.print_exception()
    def print(self, message = '', end='\n') -> None:
        """Prints a message to the standard console. Output is suppressed if `.quiet` is
        true. Highlighting is applied by default.
        """
        if not self.quiet:
            self.std_console.print(message, end=end, highlight=True)

#: Saturnin site manager
console: ConsoleManager = ConsoleManager()
