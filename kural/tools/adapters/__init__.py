"""kural.tools.adapters — real ChannelCall implementations.

Each adapter exposes a ``from_env()`` that returns a ``ChannelCall`` (or None
when unconfigured) for ``channels.set_channel_client``. Adapters are generic by
contract — saakshe stays ZERO-coupled to any specific platform; the founder's
own delivery system (an autopilot queue, a Zapier hook, a custom worker) is
just configuration.
"""
