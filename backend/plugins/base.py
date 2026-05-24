"""
Plugin system — the extensibility backbone of the pipeline.

How to add a new analytical module
────────────────────────────────────
1. Create a file in `backend/plugins/`, e.g. `funding_rate_arb.py`.
2. Define a class that inherits from `BasePlugin`.
3. Implement `subscribed_topics` and `on_signal`.
4. Register it in `main.py` via `registry.register(FundingRateArbPlugin())`.

The registry wires each plugin to the SignalBus automatically.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.core.bus import SignalBus
from backend.core.types import Signal, SignalTopic


class BasePlugin(ABC):
    """
    Minimal interface every analytical plugin must satisfy.

    Plugins are isolated: they share only the bus.  They must not import
    from each other to prevent coupling that breaks the plug-in contract.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique human-readable plugin identifier."""

    @property
    @abstractmethod
    def subscribed_topics(self) -> list[SignalTopic]:
        """Topics this plugin wants to receive from the bus."""

    @abstractmethod
    async def on_signal(self, signal: Signal) -> None:
        """Process a single signal.  Must not block."""

    async def startup(self) -> None:
        """Optional hook called once before the main loop starts."""

    async def shutdown(self) -> None:
        """Optional hook called on graceful teardown."""


class PluginRegistry:
    """
    Owns the lifecycle of all registered plugins and wires them to the bus.

    Design note: the registry is intentionally kept small.  It does not
    maintain a dependency graph — plugins are independent by design.
    """

    def __init__(self, bus: SignalBus) -> None:
        self._bus     = bus
        self._plugins: dict[str, BasePlugin] = {}

    def register(self, plugin: BasePlugin) -> None:
        if plugin.name in self._plugins:
            raise ValueError(f"Plugin '{plugin.name}' is already registered.")
        self._plugins[plugin.name] = plugin
        for topic in plugin.subscribed_topics:
            self._bus.subscribe(
                topic=topic,
                callback=plugin.on_signal,
                subscriber_id=f"plugin:{plugin.name}",
            )

    async def startup_all(self) -> None:
        for plugin in self._plugins.values():
            await plugin.startup()

    async def shutdown_all(self) -> None:
        for plugin in self._plugins.values():
            await plugin.shutdown()

    def __len__(self) -> int:
        return len(self._plugins)

    def __repr__(self) -> str:
        return f"PluginRegistry(plugins={list(self._plugins)})"
