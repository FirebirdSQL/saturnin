#coding:utf-8
#
# PROGRAM/MODULE: Saturnin microservices
# FILE:           saturnin/micro/text/reader/service.py
# DESCRIPTION:    Text file reader microservice
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

"""Saturnin microservices - Text file reader microservice

This microservice is a DATA_PROVIDER that sends blocks of text from file to output data pipe.
"""

import logging
import typing as t
from saturnin.core.types import ServiceDescriptor, StopError, SaturninError
from saturnin.core.config import MIMEOption
from saturnin.core.micropipes import MicroDataProviderImpl, DataPipe, Session, ErrorCode,\
     END_OF_DATA, BaseService
from .api import TextReaderConfig

# Logger

log = logging.getLogger(__name__)

# Classes

class MicroTextReaderImpl(MicroDataProviderImpl):
    """Implementation of Text file reader microservice."""
    SYSIO = ('stdin', 'stdout', 'stderr')
    def __init__(self, descriptor: ServiceDescriptor, stop_event: t.Any):
        super().__init__(descriptor, stop_event)
        self.file: t.TextIO = None
        self.filename: str = None
        self.file_format: str = None
        self.file_mime_type: str = None
        self.file_mime_params: t.Dict[str, str] = None
        self.max_chars: int = None
    def _open_file(self):
        "Open the input file."
        self._close_file()
        if self.filename.lower() in self.SYSIO:
            fspec = self.SYSIO.index(self.filename.lower())
            if __debug__:
                log.debug('%s._open_file(fspec:%s)', self.__class__.__name__, fspec)
        else:
            fspec = self.filename
            if __debug__:
                log.debug('%s._open_file(%s)', self.__class__.__name__, self.filename)
        charset = self.file_mime_params.get('charset', 'ascii')
        errors = self.file_mime_params.get('errors', 'strict')
        try:
            self.file = open(fspec, mode='r', encoding=charset, errors=errors,
                                   closefd=self.filename.lower() not in self.SYSIO)
        except Exception as exc:
            raise StopError("Failed to open input file", code = ErrorCode.ERROR) from exc
    def _close_file(self) -> None:
        "Close the input file if necessary"
        if self.file:
            if __debug__:
                log.debug('%s._close_file(%s)', self.__class__.__name__, self.filename)
            self.file.close()
            self.file = None
    def produce_output(self, pipe: DataPipe, session: Session) -> t.Any:
        """Called to aquire next data payload to be send via output pipe.
"""
        if self.file is None:
            self._open_file()
        try:
            buf = self.file.read(self.max_chars)
            if buf:
                result = buf.encode(encoding=session.charset, errors=session.errors)
            else:
                result = END_OF_DATA
        except Exception as exc:
            print(f'Offending data:\n"{buf}"')
            raise SaturninError(str(exc), code=ErrorCode.INVALID_DATA)
        return result
    def configure_provider(self, config: TextReaderConfig) -> None:
        """Called to configure the data provider.

This method must raise an exception if data format assigned to output pipe is invalid.
"""
        # Validate output data format
        if self.out_pipe.mime_type != 'text/plain':
            raise StopError("Only 'text/plain' output format supported",
                            code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        #
        self.max_chars = config.max_chars.value
        self.filename = config.file.value
        self.file_format = config.file_format.value
        self.file_mime_type = config.file_format.mime_type
        self.file_mime_params = dict(config.file_format.mime_params)
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
        # Ready to open the file
        self._open_file()
        return session.batch_size
    def on_server_connected(self, pipe: DataPipe, session: Session) -> None:
        "Store `charset` and `errors` MIME parameters to session."
        session.charset = session.mime_params.get('charset', 'ascii')
        session.errors = session.mime_params.get('errors', 'strict')
    def finalize(self, svc: BaseService) -> None:
        """Service finalization."""
        self._close_file()
        super().finalize(svc)
