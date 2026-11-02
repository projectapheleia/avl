.. _methodology:

AVL Methodology
===============

AVL follows the UVM methodology for verification, but as the intention of AVL is to simplify \
the verification process, the implementation does not enforce a specific flow.

.. toctree::
   :maxdepth: 1
   :caption: Methodology:

   env
   agent
   sequences/sequences
   sequencer
   driver
   vcd_driver
   monitor
   scoreboard

Connecting Sequencers and Drivers
---------------------------------

The variety of ports has been simplified from UVM.

A single :doc:`avl.Port </modules/avl._core.port>` is provides. This implements one-to-many data transfer to each of its connections.

It is recommended to connect an :doc:`avl.Port </modules/avl._core.port>` to an :doc:`avl.List </modules/avl._core.list>` as this provides the blocking mechanism for the consumer.

As the done and response handshaking is built into the :doc:`avl.SequenceItem </modules/avl._core.sequence_item>` class, the sequencer does not need to implement magic \
functions to synchronise with the driver.

.. code-block:: python

    async def connect_phase(self):
        self.sequencer.seq_item_export.connect(self.driver.seq_item_port)
