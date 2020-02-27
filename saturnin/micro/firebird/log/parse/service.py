#coding:utf-8
#
# PROGRAM/MODULE: Saturnin microservices
# FILE:           saturnin/micro/firebird/log/parse/service.py
# DESCRIPTION:    Firebird log parser microservice
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

"""Saturnin microservices - Firebird log parser microservice

This microservice is a DATA_FILTER that reads blocks of Firebird log text from input data
pipe, and sends parsed Firebird log entries into output data pipe.
"""

import logging
import typing as t
from datetime import datetime
from saturnin.core.types import MIME_TYPE_PROTO, MIME_TYPE_TEXT, ServiceDescriptor, StopError
from saturnin.core.config import MIMEOption
from saturnin.core.micropipes import MicroDataFilterImpl, DataPipe, Session, ErrorCode,\
     END_OF_DATA, BaseService
from saturnin.core.protobuf import create_message
from .api import FbLogParserConfig, LOG_FORMAT, LOG_PROTO
from .msgs import identify_msg

# Logger

log = logging.getLogger(__name__)

# Classes

class FbLogParserImpl(MicroDataFilterImpl):
    """Implementation of Firebird log parser microservice."""
    def __init__(self, descriptor: ServiceDescriptor, stop_event: t.Any):
        super().__init__(descriptor, stop_event)
        self.input_buffer = None
        self.output_buffer = []
        self.proto = create_message(LOG_PROTO)
        self.entry_buf: t.List[str] = []
    def __parse(self) -> None:
        "Parse input queue and store result into send queue."
        try:
            data = self.entry_buf[0]
            origin, timestamp = self.entry_buf.pop(0)
        except Exception as exc:
            print(exc)
        self.proto.Clear()
        self.proto.origin = origin
        self.proto.timestamp.FromDatetime(timestamp)
        msg = '\n'.join(self.entry_buf).strip()
        #
        found = identify_msg(msg)
        if found is not None:
            log_msg, params, without_optional = found
            params = found[1]
            self.proto.code = log_msg.msg_id
            self.proto.level = log_msg.severity
            self.proto.facility = log_msg.facility
            self.proto.message = log_msg.get_pattern(without_optional)
            for key, value in params.items():
                self.proto.params[key] = value
        else:
            self.proto.message = msg
        #
        self.out_que.append(self.proto.SerializeToString())
        self.entry_buf.clear()
    def __accept_log_line(self, line: str) -> None:
        ""
        line = line.strip()
        if line:
            items = line.split()
            if len(items) >= 6:
                # potential new entry
                new_entry = False
                try:
                    timestamp = datetime.strptime(' '.join(items[len(items)-5:]),
                                                  '%a %b %d %H:%M:%S %Y')
                    new_entry = True
                except ValueError:
                    pass
                if new_entry:
                    if self.entry_buf:
                        self.__parse()
                    origin = ' '.join(items[:len(items)-5])
                    self.entry_buf.append((origin, timestamp))
                else:
                    self.entry_buf.append(line)
            else:
                self.entry_buf.append(line)
        else:
            if self.entry_buf:
                self.entry_buf.append(line)
    def finish_processing(self, session: Session) -> None:
        """Called to process any remaining input data when input pipe is closed normally.
"""
        if self.entry_buf:
            self.__parse()
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
        if self.input_buffer is not None:
            block = self.input_buffer + block
            self.input_buffer = None
        lines = block.splitlines()
        if block[-1] != '\n':
            self.input_buffer = lines.pop()
        for line in lines:
            self.__accept_log_line(line)
    def configure_filter(self, config: FbLogParserConfig) -> None:
        """Called to configure the data filter.

This method must raise an exception if data format assigned to output or input pipe is invalid.
"""
        # Validate input/output data formats
        if self.in_pipe.mime_type != MIME_TYPE_TEXT:
            raise StopError("Only '%s' input format supported" % MIME_TYPE_TEXT,
                            code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        if self.out_pipe.mime_type != MIME_TYPE_PROTO:
            raise StopError("Only '%s' output format supported" % LOG_FORMAT,
                            code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        #
        self.in_pipe.on_accept_client = self.on_accept_input_client
        self.in_pipe.on_server_connected = self.on_server_connected
        self.out_pipe.on_accept_client = self.on_accept_output_client
    def on_accept_output_client(self, pipe: DataPipe, session: Session, fmt: MIMEOption) -> int:
        "Either reject client by StopError, or return batch_size we are ready to transmit."
        if __debug__: log.debug('%s.on_accept_output_client [%s]', self.__class__.__name__, pipe.pipe_id)
        session.mime_type = fmt.mime_type
        if session.mime_type != MIME_TYPE_PROTO:
            raise StopError("Only '%s' output format supported" % MIME_TYPE_PROTO,
                            code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        proto_class = fmt.get_param('type')
        if proto_class != LOG_PROTO:
            raise StopError("Unsupported protobuf type '%s'" % proto_class,
                            code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        return session.batch_size
    def on_accept_input_client(self, pipe: DataPipe, session: Session, fmt: MIMEOption) -> int:
        "Either reject client by StopError, or return batch_size we are ready to transmit."
        if __debug__: log.debug('%s.on_accept_input_client [%s]', self.__class__.__name__, pipe.pipe_id)
        session.mime_type = fmt.mime_type
        if session.mime_type != MIME_TYPE_TEXT:
            raise StopError("Only '%s' input format supported" % MIME_TYPE_TEXT,
                            code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        mime_params = dict(fmt.mime_params)
        for param in mime_params.keys():
            if param not in ('charset', 'errors'):
                raise StopError("Unknown MIME parameter '%s'" % param,
                                code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        session.charset = mime_params.get('charset', 'ascii')
        session.errors = mime_params.get('errors', 'strict')
        return session.batch_size
    def on_server_connected(self, pipe: DataPipe, session: Session) -> None:
        "Store `charset` and `errors` MIME parameters to session."
        session.charset = session.mime_params.get('charset', 'ascii')
        session.errors = session.mime_params.get('errors', 'strict')
