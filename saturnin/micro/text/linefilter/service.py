#coding:utf-8
#
# PROGRAM/MODULE: Saturnin microservices
# FILE:           saturnin/micro/text/linefilter/service.py
# DESCRIPTION:    Text line filter microservice
# CREATED:        18.12.2019
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
# Copyright (c) 2019 Firebird Project (www.firebirdsql.org)
# All Rights Reserved.
#
# Contributor(s): Pavel Císař (original code)
#                 ______________________________________.

"""Saturnin microservices - Text line filter microservice

This microservice is a DATA_FILTER that reads blocks of text from input data pipe, and
writes lines that meet the specified conditions as blocks of text into output data pipe.
"""

import logging
import typing as t
import re
from saturnin.core.types import ServiceDescriptor, StopError, SaturninError
from saturnin.core.config import MIMEOption
from saturnin.core.micropipes import MicroDataFilterImpl, DataPipe, Session, ErrorCode,\
     END_OF_DATA, BaseService
from .api import TextReaderConfig

# Logger

log = logging.getLogger(__name__)

# Classes

class MicroTextFilterImpl(MicroDataFilterImpl):
    """Implementation of Text line filter microservice."""
    def __init__(self, descriptor: ServiceDescriptor, stop_event: t.Any):
        super().__init__(descriptor, stop_event)
        self.max_chars: int = None
        self.regex = None
        self.filter_func: t.Callable = None
        self.input_lefover = None
        self.output_buffer = []
        self.to_write = 0
    def __regex_match(self, line) -> bool:
        "Helper filter function that check line against defined regex"
        return self.regex.search(line) is not None
    def finish_processing(self, session: Session) -> None:
        """Called to process any remaining input data when input pipe is closed normally.
"""
        buf = ''.join(self.output_buffer)
        self.out_que.append(buf.encode(encoding=session.charset,
                                       errors=session.errors))
    def accept_input(self, pipe: DataPipe, session: Session, data: bytes) -> t.Optional[int]:
        """Called to process next data payload aquired from input pipe.

Important:
    This method must store produced output data into :attr:`out_que`. If there are no more
    data for output, it must store `datapipe.END_OF_DATA` object to the queue.

    If input data are not complete to produce output data, they must be stored into
    :attr:`in_que` for later processing.

Returns:
    a) `None` when data were sucessfuly processed.
    b) FBDP `ErrorCode` if error was encontered.

Raises:
    Exception: For unexpected error conditions. The pipe is closed with code
        ErrorCode.INTERNAL_ERROR.
"""
        try:
            block: str = data.decode(encoding=session.charset, errors=session.errors)
        except Exception:
            return ErrorCode.INVALID_DATA
        if self.input_lefover is not None:
            block = self.input_lefover + block
            self.input_lefover = None
        lines = block.splitlines()
        if block[-1] != '\n':
            self.input_lefover = lines.pop()
        for line in lines:
            if self.filter_func(line):
                line += '\n'
                line_size = len(line)
                if self.to_write - line_size >= 0:
                    self.to_write -= line_size
                    self.output_buffer.append(line)
                else:
                    self.output_buffer.append(line[:self.to_write])
                    buf = ''.join(self.output_buffer)
                    self.out_que.append(buf.encode(encoding=session.charset,
                                                   errors=session.errors))
                    output_leftover = line[self.to_write:]
                    self.output_buffer = [output_leftover]
                    self.to_write = self.max_chars - len(output_leftover)

    def configure_filter(self, config: TextReaderConfig) -> None:
        """Called to configure the data filter.

This method must raise an exception if data format assigned to output or input pipe is invalid.
"""
        # Validate output data format
        if self.out_pipe.mime_type != 'text/plain':
            raise StopError("Only 'text/plain' output format supported",
                            code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        #
        self.max_chars = config.max_chars.value
        if config.regex.value is not None:
            self.regex = re.compile(config.regex.value)
            self.filter_func = self.__regex_match
        elif config.expr.value is not None:
            self.filter_func = config.expr.get_callable('line')
        else:
            self.filter_func = config.func.get_callable()
        #
        self.in_pipe.on_accept_client = self.on_accept_client
        self.in_pipe.on_server_connected = self.on_server_connected
        self.out_pipe.on_accept_client = self.on_accept_client
        self.out_pipe.on_server_connected = self.on_server_connected
    def on_accept_client(self, pipe: DataPipe, session: Session, fmt: MIMEOption) -> int:
        "Either reject client by StopError, or return batch_size we are ready to transmit."
        if __debug__: log.debug('%s.on_accept_client [%s]', self.__class__.__name__, pipe.pipe_id)
        session.mime_type = fmt.mime_type
        if session.mime_type != 'text/plain':
            raise StopError("Only 'text/plain' format supported",
                            code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        mime_params = dict(fmt.mime_params)
        for param in mime_params.keys():
            if param not in ('charset', 'errors'):
                raise StopError("Unknown MIME parameter '%s'" % param,
                                code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        session.charset = mime_params.get('charset', 'ascii')
        session.errors = mime_params.get('errors', 'strict')
        self.to_write = self.max_chars
        return session.batch_size
    def on_server_connected(self, pipe: DataPipe, session: Session) -> None:
        "Store `charset` and `errors` MIME parameters to session."
        session.charset = session.mime_params.get('charset', 'ascii')
        session.errors = session.mime_params.get('errors', 'strict')
        self.to_write = self.max_chars
