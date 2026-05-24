"""
WebSocket broadcast server.

Accepts connections from the Next.js frontend at ws://host:<port>/ws and
fans out every signal that passes through the SignalBus to all live clients.

Wire protocol (matches frontend WsMessage<T>)
─────────────────────────────────────────────
  Server → Client:
    {"topic": "ticker"|"order_book"|"gnn_alpha"|"execution",
     "payload": {...},
     "ts": <epoch_float>}

  Client → Server (latency probe):
    {"type": "ping"}  →  {"type": "pong"}

Serialisation contract
──────────────────────
  Ticker      : snake_case fields → camelCase; volume_24h → volume24h
  OrderBook   : PriceLevel tuple[float,float] → {price, qty} objects
  PerformanceReport: snake_case → camelCase for all metric fields
  GNN alpha / other dicts: passed through as-is
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import aiohttp
import orjson
from aiohttp import web

from backend.core.bus import SignalBus
from backend.core.types import OrderBook, Signal, SignalTopic, Ticker
from backend.execution.simulator import PerformanceReport

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


# ── Wire-format serialiser ────────────────────────────────────────────────────

def _to_wire(signal: Signal) -> bytes:
    """Convert a Signal to the JSON bytes expected by the frontend."""
    p = signal.payload

    if isinstance(p, Ticker):
        payload = {
            "exchange":  p.exchange,       # StrEnum serialises as string
            "symbol":    p.symbol,
            "bid":       p.bid,
            "ask":       p.ask,
            "last":      p.last,
            "volume24h": p.volume_24h,     # rename: volume_24h → volume24h
            "ts":        p.ts,
        }

    elif isinstance(p, OrderBook):
        payload = {
            "exchange": p.exchange,
            "symbol":   p.symbol,
            "bids":     [{"price": price, "qty": qty} for price, qty in p.bids],
            "asks":     [{"price": price, "qty": qty} for price, qty in p.asks],
            "ts":       p.ts,
        }

    elif isinstance(p, PerformanceReport):
        payload = {
            "nTrades":          p.n_trades,
            "netPnl":           p.net_pnl,
            "grossPnl":         p.gross_pnl,
            "totalFees":        p.total_fees,
            "sharpeRatio":      p.sharpe_ratio,
            "maxDrawdown":      p.max_drawdown,
            "informationRatio": p.information_ratio,
            "winRate":          p.win_rate,
            "profitFactor":     p.profit_factor,
            "equityCurve":      p.equity_curve,
        }

    else:
        # GNN alpha and any future dict payloads pass through unchanged
        payload = p

    return orjson.dumps({
        "topic":   signal.topic,    # StrEnum → "ticker", "order_book", etc.
        "payload": payload,
        "ts":      signal.ts,
    })


# ── Broadcast server ──────────────────────────────────────────────────────────

class WSBroadcastServer:
    """
    aiohttp-based WebSocket server.

    One instance is created in main.py.  It subscribes to every SignalTopic
    on startup and fans each received signal out to the connected browser clients.
    All clients see every signal — the frontend store filters by topic.
    """

    def __init__(
        self,
        bus:  SignalBus,
        host: str = "0.0.0.0",
        port: int = 8000,
    ) -> None:
        self._bus     = bus
        self._host    = host
        self._port    = port
        self._clients: set[web.WebSocketResponse] = set()
        self._runner:  web.AppRunner | None = None

    # ── Public lifecycle ──────────────────────────────────────────────────────

    async def start(self) -> None:
        """Subscribe to the bus and start the HTTP/WS listener.  Non-blocking."""
        for topic in SignalTopic:
            self._bus.subscribe(
                topic=topic,
                callback=self._on_signal,
                subscriber_id=f"ws-broadcast:{topic}",
            )

        app = web.Application(middlewares=[_cors_middleware])
        app.router.add_get("/ws",     self._ws_handler)
        app.router.add_get("/health", self._health_handler)

        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self._host, self._port)
        await site.start()

        log.info("ws-server: listening on ws://%s:%d/ws", self._host, self._port)

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()
            log.info("ws-server: stopped")

    # ── WebSocket handler ─────────────────────────────────────────────────────

    async def _ws_handler(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)

        self._clients.add(ws)
        client_addr = request.remote
        log.info("ws-server: client connected (%s)  total=%d", client_addr, len(self._clients))

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_client_message(ws, msg.data)
                elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE):
                    break
        except Exception:
            log.exception("ws-server: error on client %s", client_addr)
        finally:
            self._clients.discard(ws)
            log.info("ws-server: client disconnected (%s)  total=%d", client_addr, len(self._clients))

        return ws

    @staticmethod
    async def _health_handler(request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    # ── Client → server message handling ─────────────────────────────────────

    @staticmethod
    async def _handle_client_message(ws: web.WebSocketResponse, raw: str) -> None:
        try:
            msg = orjson.loads(raw)
        except Exception:
            return

        if msg.get("type") == "ping":
            await ws.send_str(orjson.dumps({"type": "pong"}).decode())

    # ── Bus → clients broadcast ───────────────────────────────────────────────

    async def _on_signal(self, signal: Signal) -> None:
        if not self._clients:
            return
        try:
            frame = _to_wire(signal)
        except Exception:
            log.exception("ws-server: serialisation error for topic %s", signal.topic)
            return
        await self._broadcast(frame)

    async def _broadcast(self, frame: bytes) -> None:
        """
        Fan out to all connected clients concurrently.
        Iterate over a frozen snapshot so client adds/removes during the send
        don't mutate the set we're iterating over.
        """
        snapshot = frozenset(self._clients)
        if not snapshot:
            return

        text = frame.decode()
        results = await asyncio.gather(
            *[ws.send_str(text) for ws in snapshot],
            return_exceptions=True,
        )

        for ws, result in zip(snapshot, results):
            if isinstance(result, Exception):
                # Client died mid-send — evict silently
                self._clients.discard(ws)


# ── CORS middleware (dev: allow all origins) ──────────────────────────────────

@web.middleware
async def _cors_middleware(request: web.Request, handler) -> web.Response:
    if request.method == "OPTIONS":
        return web.Response(
            headers={
                "Access-Control-Allow-Origin":  "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
            }
        )
    response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response
