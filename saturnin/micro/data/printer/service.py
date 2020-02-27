#coding:utf-8
#
# PROGRAM/MODULE: Saturnin microservices
# FILE:           saturnin/micro/data/printer/service.py
# DESCRIPTION:    Data printer microservice
# CREATED:        5.1.2020
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

"""Saturnin microservices - Data printer microservice

This microservice is a DATA_FILTER:

- INPUT: protobuf messages
- PROCESSING: uses formatting template and data from protobuf message to create text
- OUTPUT: blocks of text
"""

import logging
import typing as t
from saturnin.core.types import MIME_TYPE_TEXT, MIME_TYPE_PROTO, ServiceDescriptor, \
     StopError
from saturnin.core.config import MIMEOption
from saturnin.core import protobuf
from saturnin.core.micropipes import MicroDataFilterImpl, DataPipe, Session, \
     ErrorCode
from .api import DataPrinterConfig

# Logger

log = logging.getLogger(__name__)

# Classes

class TransformationUtilities:
    """Utility class that provides useful data to string conversion methods."""
    LF = '\n'
    def msg_enum_name(self, msg, field_name: str) -> str:
        """Returns name for value of the enum field"""
        return self.enum_name(protobuf.get_enum_field_type(msg, field_name),
                              getattr(msg, field_name))
    def enum_name(self, enum_type_name: str, value: t.Any) -> str:
        """Returns name for the enum value"""
        return protobuf.get_enum_value_name(enum_type_name, value)
    def short_enum_name(self, msg, field_name: str) -> str:
        """Returns name for value of the enum field. If name contains '_', returns
only name part after last underscore.
"""
        name = protobuf.get_enum_value_name(msg, field_name)
        return name.rsplit('_',1)[1] if '_' in name else name
    def value_list(self, values: t.Iterable, separator: str = ',', end = '',
                   indent = ' ') -> str:
        """Returns string with list of values from iterable"""
        return separator.join(f"{indent}{value}" for value in values) + end
    def items_list(self, items: t.ItemsView, separator: str = ',', end = '',
                   indent = ' ') -> str:
        """Returns string with list of key = value pairs from ItemsView"""
        return separator.join(f"{indent}{key} = {value}" for key, value in items) + end
    def formatted(self, fmt: str, context: t.Dict) -> str:
        """Returns `fmt` as f-string evaluated using values from `context` dictionary as locals."""
        if context:
            try:
                result = eval(f'f"""{fmt}"""', globals(), context)
            except Exception as exc:
                raise
            return result
            #return eval(f'f"""{fmt}"""', globals(), context)
        else:
            return fmt

class MicroDataPrinterImpl(MicroDataFilterImpl):
    """Implementation of Data printer microservice."""
    def __init__(self, descriptor: ServiceDescriptor, stop_event: t.Any):
        super().__init__(descriptor, stop_event)
        self.transform_func: t.Callable[[t.Any], str] = None
        self.fmt: str = None
        self.data: t.Any = None
        self.charset = 'ascii'
        self.errors = 'strict'
        self.utils = TransformationUtilities()
    def __format_data(self, data: t.Any, utils: TransformationUtilities) -> str:
        """Uses format specification from configuration to produce text for output."""
        try:
            val = eval(self.fmt, {'data': data, 'utils': utils})
            return val
        except Exception as exc:
            log.error("Data formatting failed: %s", exc)
            raise
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
            self.data.ParseFromString(data)
        except Exception:
            return ErrorCode.INVALID_DATA
        try:
            buf: str = self.transform_func(self.data, self.utils)
        except Exception:
            return ErrorCode.INTERNAL_ERROR
        self.out_que.append(buf.encode(encoding=self.charset,
                                       errors=self.errors))
    def configure_filter(self, config: DataPrinterConfig) -> None:
        """Called to configure the data filter.

This method must raise an exception if data format assigned to output or input pipe is invalid.
"""
        # Validate input/output data formats
        if self.in_pipe.mime_type != MIME_TYPE_PROTO:
            raise StopError(f"Only '{MIME_TYPE_PROTO}' input format allowed",
                            code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        proto_class = self.in_pipe.mime_params.get('type')
        if proto_class:
            if not protobuf.is_msg_registered(proto_class):
                raise StopError(f"Unknown protobuf message type '{proto_class}'",
                                code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
            else:
                self.data = protobuf.create_message(proto_class)
        if self.out_pipe.mime_type != MIME_TYPE_TEXT:
            raise StopError(f"Only '{MIME_TYPE_TEXT}' output format allowed",
                            code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        #
        if config.template.value is not None:
            self.transform_func = self.__format_data
            self.fmt = 'f"""'+config.template.value+'"""'
        else:
            self.transform_func = config.func.get_callable()
        #
        self.out_pipe.on_accept_client = self.on_accept_output_client
        self.out_pipe.on_server_connected = self.on_output_server_connected
        self.in_pipe.on_accept_client = self.on_accept_input_client
    def on_accept_input_client(self, pipe: DataPipe, session: Session, fmt: MIMEOption) -> int:
        """Either reject client by StopError, or return batch_size we are ready to transmit."""
        if __debug__: log.debug('%s.on_accept_output_client [%s]', self.__class__.__name__, pipe.pipe_id)
        session.mime_type = fmt.mime_type
        if session.mime_type != MIME_TYPE_PROTO:
            raise StopError(f"Only '{MIME_TYPE_PROTO}' output format allowed",
                            code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        proto_class = fmt.get_param('type')
        if self.data:
            if self.data.DESCRIPTOR.full_name != proto_class:
                raise StopError(f"Protobuf message type '{proto_class}' not allowed",
                                code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        else:
            if not protobuf.is_msg_registered(proto_class):
                raise StopError(f"Unknown protobuf message type '{proto_class}'",
                                code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
            self.data = protobuf.create_message(proto_class)
        return session.batch_size
    def on_accept_output_client(self, pipe: DataPipe, session: Session, fmt: MIMEOption) -> int:
        """Either reject client by StopError, or return batch_size we are ready to transmit."""
        if __debug__: log.debug('%s.on_accept_input_client [%s]', self.__class__.__name__, pipe.pipe_id)
        session.mime_type = fmt.mime_type
        if session.mime_type != MIME_TYPE_TEXT:
            raise StopError(f"Only '{MIME_TYPE_TEXT}' input format supported",
                            code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        mime_params = dict(fmt.mime_params)
        for param in mime_params.keys():
            if param not in ('charset', 'errors'):
                raise StopError(f"Unknown MIME parameter '{param}'",
                                code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        self.charset = mime_params.get('charset', 'ascii')
        self.errors = mime_params.get('errors', 'strict')
        return session.batch_size
    def on_output_server_connected(self, pipe: DataPipe, session: Session) -> None:
        """Store `charset` and `errors` MIME parameters to session."""
        self.charset = session.mime_params.get('charset', 'ascii')
        self.errors = session.mime_params.get('errors', 'strict')
