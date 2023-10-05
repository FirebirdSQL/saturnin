# SPDX-FileCopyrightText: 2019-present The Firebird Projects <www.firebirdsql.org>
#
# SPDX-License-Identifier: MIT
#
# PROGRAM/MODULE: saturnin
# FILE:           saturnin/base/__init__.py
# DESCRIPTION:    Saturnin (Firebird Butler Development Platform) base package
# CREATED:        21.2.2019
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

"Saturnin (Firebird Butler Development Platform) base package"

import uuid
from firebird.base.types import Error, ZMQAddress, DEFAULT, UNDEFINED, ANY, load
from firebird.base.config import Config, ConfigProto
from .types import (PLATFORM_OID, PLATFORM_UID, PLATFORM_VERSION, VENDOR_OID, VENDOR_UID,
     RoutingID, Token, TSupplement, INVALID, TIMEOUT, RESTART,
     InvalidMessageError, ChannelError, ServiceError, ClientError, StopError, RestartError,
     Origin, SocketMode, Direction, SocketType, State,  PipeSocket, FileOpenMode, Outcome,
     ButlerInterface, AgentDescriptor, PeerDescriptor, ServiceDescriptor,
     ApplicationDescriptor, PrioritizedItem,
     MIME, MIME_TYPE_PROTO, MIME_TYPE_TEXT, PROTO_PEER, SECTION_LOCAL_ADDRESS,
     SECTION_NET_ADDRESS, SECTION_NODE_ADDRESS, SECTION_PEER_UID, SECTION_SERVICE_UID,
     SECTION_BUNDLE, SECTION_SERVICE)
from .transport import (ChannelManager, Channel, Message, SimpleMessage, Protocol, Session,
     DealerChannel, RouterChannel, PushChannel, PullChannel, PubChannel, SubChannel,
     XPubChannel, XSubChannel, PairChannel,
     TZMQMessage, TMessageHandler, TSocketOptions, INTERNAL_ROUTE)
from .component import Component, ComponentConfig, create_config
from .config import (SaturninConfig, SaturninScheme, CONFIG_HDR,
                     directory_scheme, saturnin_config, venv, is_virtual)

#: Saturnin version
VERSION = '0.9.0'
