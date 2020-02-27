#coding:utf-8
#
# PROGRAM/MODULE: Saturnin microservices
# FILE:           saturnin/micro/firebird/log/fromsrv/service.py
# DESCRIPTION:    Firebird log provider microservice
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

"""Saturnin microservices - Firebird log provider microservice

This microservice is a DATA_PROVIDER that fetches Firebird log from Firebird server via
services and send it as lines of text to output data pipe.
"""
import logging
import typing as t
from saturnin.core.types import ServiceDescriptor, StopError, SaturninError
from saturnin.core.config import MIMEOption
from saturnin.core.micropipes import MicroDataProviderImpl, DataPipe, Session, ErrorCode,\
     END_OF_DATA, BaseService
from fdb.services import connect
from .api import FbLogFromSrvConfig

# Logger

log = logging.getLogger(__name__)

# Classes

class FbLogFromSrvImpl(MicroDataProviderImpl):
    """Implementation of Firebird log provider microservice."""
    def __init__(self, descriptor: ServiceDescriptor, stop_event: t.Any):
        super().__init__(descriptor, stop_event)
        self.svc = None
        self.host = None
        self.user = None
        self.password = None
        self.max_chars: int = None
        self.in_buffer: str = ''
    def __read(self) -> str:
        "Read `max_chars` characters from service"
        to_read = self.max_chars - len(self.in_buffer)
        eof = False
        lines = []
        if self.in_buffer:
            lines.append(self.in_buffer)
            self.in_buffer = ''
        while not eof and to_read > 0:
            line = self.svc.readline()
            eof = line is None
            if not eof:
                line += '\n'
                line_size = len(line)
                if to_read - line_size >= 0:
                    to_read -= line_size
                    lines.append(line)
                else:
                    lines.append(line[:to_read])
                    self.in_buffer = line[to_read:]
                    to_read = 0
        if lines:
            return ''.join(lines)
        return None
    def produce_output(self, pipe: DataPipe, session: Session) -> t.Any:
        """Called to aquire next data payload to be send via output pipe.
"""
        if self.svc is None:
            self._connect_service()
        try:
            buf = self.__read()
            if buf:
                result = buf.encode(encoding=session.charset, errors=session.errors)
            else:
                result = END_OF_DATA
        except Exception as exc:
            raise SaturninError(str(exc), code=ErrorCode.INVALID_DATA)
        return result
    def _close_service(self):
        "Detach from Firebird server services"
        if self.svc:
            self.svc.close()
            self.svc = None
    def _connect_service(self):
        "Attach to Firebird server services"
        self._close_service()
        if self.host:
            self.svc = connect(host=self.host, user=self.user, password=self.password)
        else:
            self.svc = connect(user=self.user, password=self.password)
        self.svc.get_log()
    def configure_provider(self, config: FbLogFromSrvConfig) -> None:
        """Called to configure the data provider.

This method must use `self.out_pipe.set_format()` to assign the data format, or raise
an exception if format could not be set.
"""
        # Validate output data format
        if self.out_pipe.mime_type != 'text/plain':
            raise StopError("Only 'text/plain' output format supported",
                            code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        #
        self.max_chars = config.max_chars.value
        self.host = config.host.value
        self.user = config.user.value
        self.password = config.password.value
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
                raise StopError("Unknown MIME parameter '%s'" % param)
        session.charset = mime_params.get('charset', 'ascii')
        session.errors = mime_params.get('errors', 'strict')
        # Ready to connect the service
        self._connect_service()
        return session.batch_size
    def on_server_connected(self, pipe: DataPipe, session: Session) -> None:
        "Store `charset` and `errors` MIME parameters to session."
        session.charset = session.mime_params.get('charset', 'ascii')
        session.errors = session.mime_params.get('errors', 'strict')
    def finalize(self, svc: BaseService) -> None:
        """Service finalization."""
        self._close_service()
        super().finalize(svc)
