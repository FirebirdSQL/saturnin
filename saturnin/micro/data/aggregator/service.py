#coding:utf-8
#
# PROGRAM/MODULE: Saturnin microservices
# FILE:           saturnin/micro/data/aggregator/service.py
# DESCRIPTION:    Data aggregator microservice
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

"""Saturnin microservices - Data aggregator microservice

This microservice is a DATA_FILTER:

- INPUT: protobuf messages
- PROCESSING: uses expressions / functions evaluating data from protobuf message to aggregator data for output
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
from .api import DataAggregatorConfig, AGGREGATE_FORMAT, AGGREGATE_PROTO

# Logger

log = logging.getLogger(__name__)

# Classes

class GroupByItem:
    """GROUP BY item handler"""
    def __init__(self, spec: str):
        if ':' in spec:
            self.name, self.spec = spec.split(':')
        else:
            self.spec = spec
            self.name = spec
        ns = {}
        code = compile(f"def expr(data):\n    return {self.spec}",
                       f"group_by({self.spec})", 'exec')
        eval(code, ns)
        self._func = ns['expr']
    def get_key(self, data: t.Any) -> t.Any:
        """Returns GROUP BY key value"""
        return self._func(data)


class AggregateItem:
    """Aggregate item handler"""
    def __init__(self, spec: str):
        self.__count: int = 0
        self.__value: t.Any = None
        self.spec = spec
        self.aggregate_func, field_spec = spec.split(':', 1)
        if ' as ' in self.aggregate_func:
            self.aggregate_func, self.name = self.aggregate_func.split(' as ')
        else:
            self.name = self.aggregate_func
        ns = {}
        code = compile(f"def expr(data):\n    return {field_spec}",
                       f"{self.aggregate_func}({field_spec})", 'exec')
        eval(code, ns)
        self._func = ns['expr']
    def aggregate(self, data: t.Any) -> None:
        """Process value"""
        self.__count += 1
        if self.aggregate_func == 'count':
            self.__value = self.__count
        elif self.aggregate_func == 'min':
            if self.__value is None:
                self.__value = self._func(data)
            else:
                self.__value = min(self.__value, self._func(data))
        elif self.aggregate_func == 'max':
            if self.__value is None:
                self.__value = self._func(data)
            else:
                self.__value = max(self.__value, self._func(data))
        elif self.aggregate_func in ['sum', 'avg']:
            if self.__value is None:
                self.__value = self._func(data)
            else:
                self.__value += self._func(data)
    def get_result(self) -> t.Any:
        """Returns result of the aggregate"""
        if self.__value is not None and self.aggregate_func == 'avg':
            return self.__value / self.__count
        elif self.__value is None and self.aggregate_func == 'count':
            return 0
        else:
            return self.__value

class MicroDataAggregatorImpl(MicroDataFilterImpl):
    """Implementation of Data aggregator microservice."""
    def __init__(self, descriptor: ServiceDescriptor, stop_event: t.Any):
        super().__init__(descriptor, stop_event)
        self.data: t.Any = None
        self.group_by: t.List[GroupByItem] = []
        self.agg_defs: t.List[str] = []
        self.aggregates: t.Dict[t.Tuple, AggregateItem] = {}
    def finish_processing(self, session: Session) -> None:
        """Called to process any remaining input data when input pipe is closed normally.
"""
        output_data = protobuf.create_message(AGGREGATE_PROTO)
        for key, items in self.aggregates.items():
            output_data.Clear()
            i = 0
            for grp in self.group_by:
                output_data.data[grp.name] = key[i]
                i += 1
            for item in items:
                output_data.data[item.name] = item.get_result()
            self.out_que.append(output_data.SerializeToString())
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
            key = tuple(item.get_key(self.data) for item in self.group_by)
            agg = self.aggregates.get(key)
            if agg is None:
                agg = [AggregateItem(spec) for spec in self.agg_defs]
                self.aggregates[key] = agg
            for item in agg:
                item.aggregate(self.data)
        except Exception:
            return ErrorCode.INTERNAL_ERROR
    def configure_filter(self, config: DataAggregatorConfig) -> None:
        """Called to configure the data filter.

This method must raise an exception if data format assigned to output or input pipe is invalid.
"""
        #
        proto_class = self.in_pipe.mime_params.get('type')
        if not protobuf.is_msg_registered(proto_class):
            raise StopError(f"Unknown protobuf message type '{proto_class}'",
                            code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        else:
            self.data = protobuf.create_message(proto_class)
        #
        for item in config.group_by.value:
            self.group_by.append(GroupByItem(item))
        for item in config.aggregate.value:
            self.agg_defs.append(item)
        #
        self.out_pipe.on_accept_client = self.on_accept_output_client
        #self.out_pipe.on_server_connected = self.on_output_server_connected
        self.in_pipe.on_accept_client = self.on_accept_input_client
    def on_accept_input_client(self, pipe: DataPipe, session: Session, fmt: MIMEOption) -> int:
        """Either reject client by StopError, or return batch_size we are ready to transmit."""
        if __debug__: log.debug('%s.on_accept_output_client [%s]', self.__class__.__name__, pipe.pipe_id)
        session.mime_type = fmt.mime_type
        if session.mime_type != MIME_TYPE_PROTO:
            raise StopError(f"Only '{MIME_TYPE_PROTO}' input format allowed",
                            code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        proto_class = fmt.get_param('type')
        if self.data.DESCRIPTOR.full_name != proto_class:
            raise StopError(f"Protobuf message type '{proto_class}' not allowed",
                            code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        return session.batch_size
    def on_accept_output_client(self, pipe: DataPipe, session: Session, fmt: MIMEOption) -> int:
        """Either reject client by StopError, or return batch_size we are ready to transmit."""
        if __debug__: log.debug('%s.on_accept_input_client [%s]', self.__class__.__name__, pipe.pipe_id)
        session.mime_type = fmt.mime_type
        if fmt.value != AGGREGATE_FORMAT:
            raise StopError(f"Only '{AGGREGATE_FORMAT}' output format supported",
                            code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        return session.batch_size
