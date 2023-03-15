
===================
saturnin.base.types
===================

.. automodule:: saturnin.base.types
   :no-members:
   :synopsis: Saturnin base types

Types for annotations
=====================

.. autodata:: TSupplement
.. autodata:: Token
.. autodata:: RoutingID

Constants
=========

.. autodata:: PLATFORM_OID
.. autodata:: PLATFORM_UID
.. autodata:: PLATFORM_VERSION
.. autodata:: VENDOR_OID
.. autodata:: VENDOR_UID
.. autodata:: MIME_TYPE_PROTO
.. autodata:: MIME_TYPE_TEXT
.. autodata:: MIME_TYPE_BINARY
.. autodata:: SECTION_LOCAL_ADDRESS
.. autodata:: SECTION_NODE_ADDRESS
.. autodata:: SECTION_NET_ADDRESS
.. autodata:: SECTION_SERVICE_UID
.. autodata:: SECTION_PEER_UID
.. autodata:: SECTION_BUNDLE
.. autodata:: SECTION_SERVICE
.. autodata:: PROTO_PEER

Exceptions
==========

.. autoexception:: InvalidMessageError
.. autoexception:: ChannelError
.. autoexception:: ServiceError
.. autoexception:: ClientError
.. autoexception:: StopError
.. autoexception:: RestartError

Sentinels
=========

.. autodata:: INVALID
.. autodata:: TIMEOUT
.. autodata:: RESTART

Enums
=====

.. autoclass:: Origin
.. autoclass:: SocketMode
.. autoclass:: Direction
.. autoclass:: SocketType
.. autoclass:: State
.. autoclass:: PipeSocket
.. autoclass:: FileOpenMode
.. autoclass:: Outcome
.. autoclass:: ButlerInterface

Dataclasses
===========

.. autoclass:: AgentDescriptor
.. autoclass:: PeerDescriptor
.. autoclass:: ServiceDescriptor
.. autoclass:: ApplicationDescriptor
.. autoclass:: PrioritizedItem

