#coding:utf-8
#
# PROGRAM/MODULE: Saturnin microservices
# FILE:           saturnin/micro/data/filter/service.py
# DESCRIPTION:    Data filter microservice
# CREATED:        20.1.2020
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

"""Saturnin microservices - Data filter microservice

This microservice is a DATA_FILTER:

- INPUT: protobuf messages
- PROCESSING: uses expressions / functions evaluating data from protobuf message to filter data for output
- OUTPUT: protobuf messages
"""

import logging
import typing as t
from saturnin.core.types import MIME_TYPE_PROTO, ServiceDescriptor, \
     StopError
from saturnin.core.config import MIMEOption
from saturnin.core import protobuf
from saturnin.core.micropipes import MicroDataFilterImpl, DataPipe, Session, \
     ErrorCode
from .api import DataFilterConfig

# Logger

log = logging.getLogger(__name__)

# Classes

class MicroPBDataFilterImpl(MicroDataFilterImpl):
    """Implementation of Data filter microservice."""
    def __init__(self, descriptor: ServiceDescriptor, stop_event: t.Any):
        super().__init__(descriptor, stop_event)
        self.data: t.Any = None
        self.include_func: t.Callable = None
        self.exclude_func: t.Callable = None
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
            if self.include_func and not self.include_func(self.data):
                return
            if self.exclude_func and self.exclude_func(self.data):
                return
            self.out_que.append(data)
        except Exception as exc:
            return ErrorCode.INTERNAL_ERROR
    def configure_filter(self, config: DataFilterConfig) -> None:
        """Called to configure the data filter.

This method must raise an exception if data format assigned to output or input pipe is invalid.
"""
        if config.include_expr.value is not None:
            self.include_func = config.include_expr.get_callable('data')
        if config.include_func.value is not None:
            self.include_func = config.include_func.get_callable()
        if config.exclude_expr.value is not None:
            self.exclude_func = config.exclude_expr.get_callable('data')
        if config.exclude_func.value is not None:
            self.exclude_func = config.exclude_func.get_callable()
        #
        proto_class = self.in_pipe.mime_params.get('type')
        if not protobuf.is_msg_registered(proto_class):
            raise StopError(f"Unknown protobuf message type '{proto_class}'",
                            code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        else:
            self.data = protobuf.create_message(proto_class)
        #
        self.out_pipe.on_accept_client = self.on_accept_client
        #self.out_pipe.on_server_connected = self.on_output_server_connected
        self.in_pipe.on_accept_client = self.on_accept_client
    def on_accept_client(self, pipe: DataPipe, session: Session, fmt: MIMEOption) -> int:
        """Either reject client by StopError, or return batch_size we are ready to transmit."""
        if __debug__: log.debug('%s.on_accept_output_client [%s]', self.__class__.__name__, pipe.pipe_id)
        session.mime_type = fmt.mime_type
        if session.mime_type != MIME_TYPE_PROTO:
            raise StopError(f"Only '{MIME_TYPE_PROTO}' output format allowed",
                            code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        proto_class = fmt.get_param('type')
        if self.data.DESCRIPTOR.full_name != proto_class:
            raise StopError(f"Protobuf message type '{proto_class}' not allowed",
                            code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        return session.batch_size
