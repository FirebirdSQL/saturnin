#coding:utf-8
#
# PROGRAM/MODULE: Saturnin microservices
# FILE:           saturnin/micro/text/writer/service.py
# DESCRIPTION:    Text file writer microservice
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

"""Saturnin microservices - Text file writer microservice

This microservice is a DATA_CONSUMER that wites blocks of text from input data pipe to file.
"""

import logging
import typing as t
import os
from saturnin.core.types import ServiceDescriptor, StopError, FileOpenMode
from saturnin.core.config import MIMEOption
from saturnin.core.protobuf import create_message, is_msg_registered
from saturnin.core.micropipes import MicroDataConsumerImpl, DataPipe, Session, ErrorCode, \
     BaseService
from .api import TextWriterConfig

# Logger

log = logging.getLogger(__name__)

# Functions

# Classes

class MicroTextWriterImpl(MicroDataConsumerImpl):
    """Implementation of Text file writer microservice."""
    SYSIO = ('stdin', 'stdout', 'stderr')
    MIME_TEXT = 'text/plain'
    MIME_PROTO = 'application/x.fb.proto'
    SUPPORTED_MIME = (MIME_TEXT, MIME_PROTO)
    def __init__(self, descriptor: ServiceDescriptor, stop_event: t.Any):
        super().__init__(descriptor, stop_event)
        self.file: t.TextIO = None
        self.filename: str = None
        self.file_format: str = None
        self.file_mime_type: str = None
        self.file_mime_params: t.Dict[str, str] = None
        self.file_mode: FileOpenMode = None
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
        if self.file_mode == FileOpenMode.CREATE:
            file_mode = 'x'
        elif self.file_mode == FileOpenMode.WRITE:
            file_mode = 'w'
        elif self.file_mode == FileOpenMode.RENAME:
            file_mode = 'w'
            if isinstance(fspec, str) and os.path.isfile(self.filename):
                i = 1
                dest = '%s.%s' % (self.filename, i)
                while os.path.isfile(dest):
                    i += 1
                    dest = '%s.%s' % (self.filename, i)
                try:
                    os.rename(self.filename, dest)
                except Exception as exc:
                    raise StopError("File rename failed") from exc
        elif self.file_mode == FileOpenMode.APPEND:
            file_mode = 'a'
        charset = self.file_mime_params.get('charset', 'ascii')
        errors = self.file_mime_params.get('errors', 'strict')
        try:
            self.file = open(fspec, mode=file_mode, encoding=charset, errors=errors,
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
    def accept_input(self, pipe: DataPipe, session: Session, data: bytes) -> t.Optional[int]:
        """Called to process next data payload aquired from input pipe.

Returns:
    a) `None` when data were sucessfuly processed.
    b) FBDP `ErrorCode` if error was encontered.

Raises:
    Exception: For unexpected error conditions. The pipe is closed with code
        ErrorCode.INTERNAL_ERROR.
"""
        if self.file is None:
            self._open_file()
        if session.mime_type == self.MIME_PROTO:
            try:
                session.proto.ParseFromString(data)
            except Exception:
                log.exception("Error while parsing protobuf data from pipe")
                return ErrorCode.INVALID_DATA
            self.file.write(str(session.proto))
        else:
            try:
                self.file.write(data.decode(encoding=session.charset, errors=session.errors))
            except UnicodeError:
                return ErrorCode.INVALID_DATA
            except Exception:
                log.exception("Unexpected error while processing data from pipe")
                return ErrorCode.INTERNAL_ERROR
    def configure_consumer(self, config: TextWriterConfig) -> None:
        """Called to configure the data provider.

This method must raise an exception if data format assigned to input pipe is invalid.
"""
        # Validate input data format
        if self.in_pipe.mime_type not in self.SUPPORTED_MIME:
            raise StopError("MIME type '%s' is not a valid input format" % self.in_pipe.mime_type,
                            code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        if self.in_pipe.mime_type == self.MIME_PROTO:
            proto_class = self.in_pipe.mime_params.get('type')
            if not is_msg_registered(proto_class):
                raise StopError("Unknown protobuf message type '%s'" % proto_class,
                                code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        #
        self.filename = config.file.value
        self.file_format = config.file_format.value
        self.file_mime_type = config.file_format.mime_type
        self.file_mime_params = dict(config.file_format.mime_params)
        self.file_mode = config.file_mode.value
        self.in_pipe.on_accept_client = self.on_accept_client
        self.in_pipe.on_server_connected = self.on_server_connected
    def on_accept_client(self, pipe: DataPipe, session: Session, fmt: MIMEOption) -> int:
        "Either reject client by StopError, or return batch_size we are ready to transmit."
        if __debug__: log.debug('%s.on_accept_client [%s]', self.__class__.__name__, pipe.pipe_id)
        session.mime_type = fmt.mime_type
        if session.mime_type not in self.SUPPORTED_MIME:
            raise StopError("MIME type '%s' is not a valid input format" % session.mime_type,
                            code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
        mime_params = dict(fmt.mime_params)
        if session.mime_type == self.MIME_TEXT:
            for param in mime_params.keys():
                if param not in ('charset', 'errors'):
                    raise StopError("Unknown MIME parameter '%s'" % param,
                                    code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
            session.charset = mime_params.get('charset', 'ascii')
            session.errors = mime_params.get('errors', 'strict')
        elif session.mime_type == self.MIME_PROTO:
            for param in mime_params.keys():
                if param != 'type':
                    raise StopError("Unknown MIME parameter '%s'" % param,
                                    code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
            proto_class = mime_params.get('type')
            if not is_msg_registered(proto_class):
                raise StopError("Unknown protobuf message type '%s'" % proto_class,
                                code = ErrorCode.DATA_FORMAT_NOT_SUPPORTED)
            session.proto = create_message(proto_class)
        # Ready to open the file
        self._open_file()
        return session.batch_size
    def on_server_connected(self, pipe: DataPipe, session: Session) -> None:
        "Store `charset` and `errors` MIME parameters to session."
        if session.mime_type == self.MIME_TEXT:
            session.charset = session.mime_params.get('charset', 'ascii')
            session.errors = session.mime_params.get('errors', 'strict')
        elif session.mime_type == self.MIME_PROTO:
            session.proto = create_message(session.mime_params.get('type'))
    def finalize(self, svc: BaseService) -> None:
        """Service finalization."""
        self._close_file()
        super().finalize(svc)
