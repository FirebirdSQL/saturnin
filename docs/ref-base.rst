
=============
saturnin.base
=============

.. automodule:: saturnin.base
   :no-members:
   :synopsis: Saturnin base types, clasess and modules

The `saturnin.base` module provides next objects imported from other sub-modules:

Constants
=========

`.VERSION`, `.PLATFORM_OID`, `.PLATFORM_UID`, `.PLATFORM_VERSION`, `.VENDOR_OID`, `.VENDOR_UID`,
`.INVALID`, `~saturnin.base.types.TIMEOUT`, `.RESTART`, `~firebird.base.types.MIME`,
`.MIME_TYPE_PROTO`, `.MIME_TYPE_TEXT`, `.SECTION_LOCAL_ADDRESS`, `.SECTION_NET_ADDRESS`,
`.SECTION_NODE_ADDRESS`, `.SECTION_PEER_UID`, `.SECTION_SERVICE_UID`, `.SECTION_BUNDLE`,
`.SECTION_SERVICE`, `.CONFIG_HDR`,
`.PROTO_PEER`, `.INTERNAL_ROUTE`, `~firebird.base.types.DEFAULT`, `~firebird.base.types.UNDEFINED`,
`~firebird.base.types.ANY`.

Types
=====

:external+base:py:class:`~firebird.base.types.ZMQAddress`, `.RoutingID`,
`~saturnin.base.types.Token`, `.TSupplement`, `.Origin`, `.SocketMode`,
`.Direction`, `.SocketType`, `.State`, `.PipeSocket`, `.FileOpenMode`, `.Outcome`,
`.ButlerInterface`, `.TZMQMessage`, `.TMessageHandler`, `.TSocketOptions`.

Exceptions
==========

`~firebird.base.types.Error`, `.InvalidMessageError`, `.ChannelError`, `.ServiceError`,
`.ClientError`, `.StopError`, `RestartError`.

Dataclasses
===========

`.AgentDescriptor`, `.PeerDescriptor`, `.ServiceDescriptor`, `.ApplicationDescriptor`, `.PrioritizedItem`.

Classes
=======

`.ChannelManager`, `.Channel`, `.Message`, `.SimpleMessage`, `.Protocol`, `.Session`,
`.DealerChannel`,  `.RouterChannel`, `.PushChannel`, `.PullChannel`, `.PubChannel`, `.SubChannel`,
`.XPubChannel`, `.XSubChannel`, `.PairChannel`, `.Component`, `.ComponentConfig`,
`.SaturninConfig`, `.SaturninScheme`, `~firebird.base.config.Config` and `~firebird.base.config.ConfigProto`.

Globals
=======

`.directory_scheme`, `~saturnin.base.config.saturnin_config`.

Functions
=========

`~saturnin.base.component.create_config`, `~firebird.base.types.load`, `.is_virtual`, `.venv`.

.. autodata:: VERSION
