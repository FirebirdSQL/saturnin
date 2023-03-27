
=======================
saturnin.base.transport
=======================

.. automodule:: saturnin.base.transport
   :no-members:
   :synopsis: Saturnin ZeroMQ messaging - base classes and other definitions

Types for type hints
====================

.. autodata:: TZMQMessage
.. autodata:: TMessageFactory
.. autodata:: TSocketOptions
.. autodata:: TMessageHandler

Constants
=========

.. autodata:: INTERNAL_ROUTE

Classes
=======

.. autoclass:: ChannelManager
.. autoclass:: Message
.. autoclass:: SimpleMessage
.. autoclass:: Session
.. autoclass:: Protocol
.. autoclass:: Channel

Channels for individual 0MQ socket types
========================================

.. autoclass:: DealerChannel
.. autoclass:: PushChannel
.. autoclass:: PullChannel
.. autoclass:: PubChannel
.. autoclass:: SubChannel
.. autoclass:: XPubChannel
.. autoclass:: XSubChannel
.. autoclass:: PairChannel
.. autoclass:: RouterChannel

