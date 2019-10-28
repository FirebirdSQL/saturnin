#coding:utf-8
#
# PROGRAM/MODULE: Saturnin - Firebird log microservice
# FILE:           saturnin/micro/fblog/service.py
# DESCRIPTION:    FBLOG microservice (classic version)
# CREATED:        13.9.2019
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

"""Saturnin - FBLOG microservice

The FBLOG microservice can perform the following operations with Firebird Server log,
depending on the configuration:

LOG_FROM_SERVER - Pipe OUTPUT: Text log obtained from Firebird server via FB service manager
PARSE_LOG       - Pipe INPUT: Text log, Pipe OUTPUT: Parsed log
FILTER_PARSED   - Pipe INPUT: Parsed log, Pipe OUTPUT: Filtered parsed log
PRINT_PARSED    - Pipe INPUT: Parsed log, Pipe OUTPUT: Text log
"""


import logging
import typing as t
from datetime import datetime
from saturnin.sdk.types import SocketMode, ServiceDescriptor, StopError
from saturnin.sdk.config import MIMEOption
from saturnin.sdk.base import DealerChannel
from saturnin.sdk.service import MicroserviceImpl, BaseService
from saturnin.sdk.datapipe import END_OF_DATA, DataPipe, InputPipe, OutputPipe, \
     Session, ErrorCode, Message
from .api import FbLogConfig, FbLogOperation
from . import fblog_pb2 as pb

# Logger

log = logging.getLogger(__name__)

LOG_FORMAT = 'application/x.fb.proto;type=saturnin.micro.fblog.FirebirdLogEntry'

# Classes

class FbLogServiceImpl(MicroserviceImpl):
    """Implementation of FBLOG microservice.

Attributes:
    :in_pipe:       Input data pipe
    :out_pipe:      Output data pipe
    :in_chn:        Input data pipe channel
    :out_chn:       Output data pipe channel
    :stop_on_close: Whether microservice should stop when data pipe is closed
    :operation:     Operation this fblog instance should perform
    :in_que:        Input data queue
    :send_que:      Output data queue
    :proto:         protobuf message for log entry
    :post_process:  callable for processing accumulated input when input queue is closed
                    normally, used by PARSE_LOG
    :print_format:  format string for PRINT_PARSED
    :filter_expr:   filter expression for FILTER_PARSED
    :print_cnt:     line counter for PRINT_PARSED
    :svc:           Firebird service instance
"""
    def __init__(self, descriptor: ServiceDescriptor, stop_event: t.Any):
        super().__init__(descriptor, stop_event)
        self.in_pipe: InputPipe = InputPipe(self.on_pipe_closed)
        self.out_pipe: OutputPipe = OutputPipe(self.on_pipe_closed)
        self.in_chn: DealerChannel = None
        self.out_chn: DealerChannel = None
        self.stop_on_close = True
        self.operation: FbLogOperation = None
        self.in_que: t.List = []
        self.send_que: t.List = []
        self.proto: pb.FirebirdLogEntry = pb.FirebirdLogEntry()
        #self.ready = False
        self.post_process = None
        self.print_format: str = None
        self.filter_expr: str = None
        self.print_cnt: int = 0
        self.svc = None
        #
    def __parse(self) -> None:
        "Parse input queue and store result into send queue."
        origin, timestamp = self.in_que.pop(0)
        self.proto.Clear()
        self.proto.origin = origin
        self.proto.timestamp.FromDatetime(timestamp)
        self.proto.message = ' '.join(self.in_que)
        self.send_que.append(self.proto.SerializeToString())
        self.in_que.clear()
    def on_accept_client(self, pipe: DataPipe, session: Session, fmt: MIMEOption) -> int:
        "Either reject client by StopError, or return batch_size we are ready to transmit."
        if __debug__: log.debug('%s.on_accept_client [%s]', self.__class__.__name__, pipe.pipe_id)
        other: DataPipe = self.out_pipe if pipe is self.in_pipe else self.in_pipe
        result = 0
        if other.active():
            result = min(pipe.batch_size, other.batch_size, session.batch_size)
        return result
    def on_server_ready(self, pipe: DataPipe, session: Session, batch_size: int) -> int:
        "Default callback that returns batch_size if < session.batch_size, else session.batch_size."
        if __debug__: log.debug('%s.on_server_ready [%s]', self.__class__.__name__, pipe.pipe_id)
        # session.ready is None for first READY from server
        if session.ready is None:
            other: DataPipe = self.out_pipe if pipe is self.in_pipe else self.in_pipe
            result = 0
            if other.active():
                result = min(pipe.batch_size, other.batch_size, session.batch_size)
            return result
        return min(batch_size, session.batch_size)
    def accept_print_entry(self, pipe: DataPipe, session: Session, data: bytes) -> t.Optional[int]:
        "Process parsed log entry"
        if __debug__: log.debug('%s.accept_print_entry [%s]', self.__class__.__name__, pipe.pipe_id)
        assert self.print_format
        self.proto.Clear()
        self.print_cnt += 1
        try:
            self.proto.ParseFromString(data)
            self.send_que.append(bytes(self.print_format
                                       % {'lineno': self.print_cnt,
                                          'origin': self.proto.origin,
                                          'timestamp': self.proto.timestamp.ToDatetime(),
                                          'level': self.proto.level,
                                          'code': self.proto.code,
                                          'message': self.proto.message},
                                       self.out_pipe.mime_params.get('charset', 'utf-8'),
                                       self.out_pipe.mime_params.get('errors', 'strict')))
        except:
            return ErrorCode.INVALID_DATA
    def accept_filter_entry(self, pipe: DataPipe, session: Session, data: bytes) -> t.Optional[int]:
        "Process parsed log entry"
        if __debug__: log.debug('%s.accept_filter_entry [%s]', self.__class__.__name__, pipe.pipe_id)
        assert self.filter_expr
        self.proto.Clear()
        try:
            # Filter entry
            self.proto.ParseFromString(data)
            _locals = {'origin': self.proto.origin, 'code': self.proto.code,
                       'timestamp': self.proto.timestamp.ToDatetime(),
                       'level': self.proto.level, 'message': self.proto.message}
            _locals.update(self.proto.params)
            if eval(self.filter_expr, None, _locals):
                self.send_que.append(data)
        except:
            log.exception("FILTER ERROR:")
            return ErrorCode.INVALID_DATA
    def accept_log_line(self, pipe: DataPipe, session: Session, data: bytes) -> t.Optional[int]:
        "Process text log line"
        if __debug__: log.debug('%s.accept_log_line [%s]', self.__class__.__name__, pipe.pipe_id)
        try:
            line = data.decode(encoding=pipe.mime_params.get('charset', 'utf-8'),
                               errors=pipe.mime_params.get('errors', 'strict')).strip()
        except:
            return ErrorCode.INVALID_DATA
        #
        if not line:
            if self.in_que:
                self.__parse()
            return
        if not self.in_que:
            items = line.split()
            try:
                timestamp = datetime.strptime(' '.join(items[len(items)-5:]),
                                              '%a %b %d %H:%M:%S %Y')
            except ValueError:
                return ErrorCode.INVALID_DATA
            origin = ' '.join(items[:len(items)-5])
            self.in_que.append((origin, timestamp))
        else:
            self.in_que.append(line)
    def produce_output(self, pipe: DataPipe, session: Session) -> pb.FirebirdLogEntry:
        "Return entry from queue or None"
        if __debug__: log.debug('%s.produce_output [%s]', self.__class__.__name__, pipe.pipe_id)
        data = None
        if self.operation == FbLogOperation.LOG_FROM_SERVER:
            data = self.svc.readline()
            if data is None:
                data = END_OF_DATA
            else:
                data = bytes(data, self.out_pipe.mime_params.get('charset', 'utf-8'),
                             self.out_pipe.mime_params.get('errors', 'strict'))
        else:
            if self.send_que:
                data = self.send_que.pop(0)
        if data is END_OF_DATA:
            raise StopError("EOF")
        return data
    def on_pipe_closed(self, pipe: DataPipe, session: Session, msg: Message) -> None:
        "General callback that logs info(OK) or error, and closes the input file."
        if __debug__: log.debug('%s.on_pipe_closed [%s]', self.__class__.__name__, pipe.pipe_id)
        # If output was closed, close input as well
        if pipe is self.out_pipe:
            if self.in_pipe.hnd.is_active():
                self.in_pipe.close()
            self.send_que.clear() # clear the out queue, we may wait for another consumer
            self.print_cnt = 0
            self.filter_expr = None
        elif pipe is self.in_pipe:
            # if we still have data in input queue and pipe was closed normally, process them
            if self.in_que and msg.type_data == ErrorCode.OK:
                # this can turn out any way, so ignore errors
                try:
                    assert self.post_process
                    self.post_process()
                except:
                    pass
            self.in_que.clear() # clear the in queue, we may wait for another producer
            # If we have active output, signal end of data
            if self.out_pipe.hnd.is_active():
                self.send_que.append(END_OF_DATA)
        if (not self.in_pipe.hnd.is_active() and
            not self.out_pipe.hnd.is_active() and self.stop_on_close):
            self.stop_event.set()
    def initialize(self, svc: BaseService):
        super().initialize(svc)
        self.in_chn = DealerChannel(b'%s-in' % self.instance_id.hex().encode('ascii'),
                                      sock_opts=self.get('in_sock_opts', None))
        self.out_chn = DealerChannel(b'%s-out' % self.instance_id.hex().encode('ascii'),
                                      sock_opts=self.get('out_sock_opts', None))
        self.in_pipe.set_channel(self.in_chn)
        self.out_pipe.set_channel(self.out_chn)
        self.mngr.add(self.in_chn)
        self.mngr.add(self.out_chn)
    def configure(self, svc: BaseService, config: FbLogConfig) -> None:
        """Service configuration."""
        config.validate() # Fail early
        #
        self.operation = config.operation.value
        self.stop_on_close = config.stop_on_close.value
        #
        self.in_pipe.pipe_id = config.input_pipe.value
        self.in_pipe.address = config.input_address.value
        self.in_pipe.set_mode(config.input_mode.value)
        self.in_pipe.batch_size = config.input_batch_size.value
        #
        self.out_pipe.pipe_id = config.output_pipe.value
        self.out_pipe.address = config.output_address.value
        self.out_pipe.set_mode(config.output_mode.value)
        self.out_pipe.batch_size = config.output_batch_size.value
        # TODO: Validate data format specifications for pipes
        # Prepare selected operation
        if self.operation == FbLogOperation.LOG_FROM_SERVER:
            self.out_pipe.set_format(config.output_format, 'text/plain;charset=utf-8')
            from fdb.services import connect
            self.svc = connect(user=config.user.value, password=config.password.value)
            self.svc.get_log()
            self.out_pipe.on_produce_data = self.produce_output
        elif self.operation == FbLogOperation.PARSE_LOG:
            self.in_pipe.set_format(config.input_format, 'text/plain;charset=utf-8')
            self.out_pipe.set_format(config.output_format, LOG_FORMAT)
            #
            self.in_pipe.on_accept_data = self.accept_log_line
            self.post_process = self.__parse
            self.out_pipe.on_produce_data = self.produce_output
            #
        elif self.operation == FbLogOperation.FILTER_PARSED:
            self.in_pipe.set_format(config.input_format, LOG_FORMAT)
            self.out_pipe.set_format(config.output_format, LOG_FORMAT)
            #
            self.in_pipe.on_accept_data = self.accept_filter_entry
            try:
                self.filter_expr = compile(config.filter_expr.value, '<filter_expr>', 'eval',
                                           optimize=2)
            except Exception as exc:
                raise StopError("Error in filter expression", exc) from None
            self.out_pipe.on_produce_data = self.produce_output
        elif self.operation == FbLogOperation.PRINT_PARSED:
            self.in_pipe.set_format(config.input_format, LOG_FORMAT)
            self.out_pipe.set_format(config.output_format, 'text/plain;charset=utf-8')
            #
            self.in_pipe.on_accept_data = self.accept_print_entry
            self.print_format = config.print_format.value
            if not self.print_format.endswith('\n'):
                self.print_format += '\n'
            self.out_pipe.on_produce_data = self.produce_output
            #
        else:
            raise StopError("Operation '%s' not implemented" % self.operation.name)
        # Open pipes
        for pipe in (self.in_pipe, self.out_pipe):
            if pipe.pipe_id:
                if pipe.mode == SocketMode.BIND:
                    pipe.open()
                else:
                    self.mngr.defer(pipe.open)
        #
    def finalize(self, svc: BaseService) -> None:
        """Service finalization."""
        for pipe in (self.in_pipe, self.out_pipe):
            pipe.close()
        if self.svc:
            self.svc.close()
        super().finalize(svc)
