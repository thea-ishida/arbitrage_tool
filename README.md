# Cross-Exchange GNN Arbitrageur

A real-time **Lead-Lag prediction engine** for cryptocurrency markets. A Graph Neural Network models multiple exchanges as nodes, detects price movements on leading exchanges (e.g. Binance), and predicts catch-up movements on lagging exchanges (e.g. Kraken) — all with sub-millisecond signal latency on the hot ingest path.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Exchange WebSockets (Binance, Kraken, …)                   │
│         │  L1 Ticker + L2 Order Book                        │
│         ▼                                                   │
│  IngestionManager  ──►  SignalBus (Pub/Sub)                 │
│   BinanceAdapter           │                                │
│   KrakenAdapter            ├──► GNNAlphaEngine              │
│                            │      FeatureBuilder (7-dim OBI) │
│                            │      LeadLagGNN (GATv2)         │
│                            │      ExecutionSimulator          │
│                            │                                │
│                            └──► PluginRegistry              │
│                                   (drop-in modules)         │
└─────────────────────────────────────────────────────────────┘
                             │  ws://localhost:8000/ws
                             ▼
              ┌──────────────────────────┐
              │  Next.js 14 Dashboard    │
              │  Zustand store           │
              │  GNN Alpha Chart         │
              │  Order Book Imbalance    │
              │  Performance Metrics     │
              │  Live Ticker             │
              └──────────────────────────┘
```

**Key design principles:**
- **Zero-copy dispatch** — signal payloads are frozen dataclasses; no allocation on the hot path
- **Bounded queues** — slow subscribers shed load by evicting the oldest item rather than blocking the producer
- **Plugin contract** — any new analytical module subclasses `BasePlugin` and registers itself; no core code changes required
- **Frontend registry** — new dashboard widgets register in one file; the sidebar and overview grid auto-populate

---

## Tech Stack

| Layer | Technology |
|---|---|
| Ingest | Python 3.12 · `asyncio` · `websockets` · `orjson` |
| Signal bus | Custom async Pub/Sub (`asyncio.Queue`, bounded) |
| Feature engineering | `numpy` · 7-dim node vector (OBI, log-return, spread, depth slope) |
| GNN model | PyTorch 2.3 · PyTorch Geometric · GATv2Conv |
| Execution simulator | Custom · Sharpe · Max Drawdown · Information Ratio · maker/taker fees |
| Config | `pydantic-settings` · `.env` |
| Logging | `structlog` |
| Frontend | Next.js 14 (App Router) · React 18 · TypeScript strict |
| State | Zustand |
| Charts | Recharts |
| Styling | Tailwind CSS · `#0B192C` / `#1E3A8A` dark-navy palette |

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | **3.12** (3.13+ breaks pinned PyTorch dependencies) |
| Node.js | 18+ |
| npm | 9+ |

---

## Running the Project

### 1 — Clone and enter the repo

```bash
git clone <your-repo-url>
cd arbi_calculator
```

### 2 — Backend setup

```bash
# Create and activate a virtual environment
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install PyTorch first (CPU build)
pip install torch==2.3.0

# Install PyTorch Geometric compiled extensions
pip install torch-scatter torch-sparse \
  -f https://data.pyg.org/whl/torch-2.3.0+cpu.html

# Install remaining dependencies
pip install -r backend/requirements.txt
```

> **macOS Python 3.14+ SSL note:** If you see `CERTIFICATE_VERIFY_FAILED`, run:
> `pip install certifi` — the adapters already use it automatically.

### 3 — Frontend setup

```bash
cd frontend
npm install
```

### 4 — Environment variables (optional)

All settings have safe defaults for local development. To override, create `backend/.env`:

```bash
# Ingestion
INGEST_SYMBOLS=["BTC/USDT","ETH/USDT"]
INGEST_BOOK_DEPTH=20
INGEST_RECONNECT_DELAY_S=1.0
INGEST_RECONNECT_MAX_S=60.0

# GNN model
GNN_HIDDEN_CHANNELS=64
GNN_NUM_LAYERS=3
GNN_DROPOUT=0.1
GNN_LEARNING_RATE=0.001
GNN_CHECKPOINT_DIR=backend/models/checkpoints

# Execution simulator
EXEC_MAKER_FEE=0.001
EXEC_TAKER_FEE=0.001
EXEC_SLIPPAGE_BPS=1.0
EXEC_CAPITAL_USDT=10000.0

# App
LOG_LEVEL=INFO
WS_PORT=8000
METRICS_PORT=9090
```

For the frontend, create `frontend/.env.local`:

```bash
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
```

### 5 — Run

**Backend** (from the project root):

```bash
source .venv/bin/activate
python -m backend.main
```

**Frontend** (in a separate terminal):

```bash
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

> **No backend? No problem.** The dashboard ships with a mock data feed (`useMockData`) that generates realistic streaming alpha signals, order books, ticker prices, and performance metrics. The dashboard is fully interactive with no backend running. Remove the `useMockData()` call in `DashboardLayout.tsx` before deploying to production.

---

## Dashboard

The default view is the **Overview** — a Bloomberg-style 2×2 grid showing all panels simultaneously.

| Panel | Description |
|---|---|
| **GNN Alpha** | Real-time lead-lag signal (α). Dual-area chart: green above zero (lag rises), red below (lag falls). Conviction badge: NEUTRAL / WEAK / MODERATE / STRONG |
| **Order Book Imbalance** | Cross-exchange OBI bars growing from center. Bid pressure left (green), ask pressure right (red). Sorted by magnitude. Cross-exchange aggregate at bottom |
| **Performance Metrics** | Sharpe Ratio, Max Drawdown, Information Ratio, Win Rate — each color-coded by threshold. Live equity curve sparkline |
| **Live Ticker** | Real-time bid/ask/spread across all exchanges. Per-row price flash animation. Best bid/ask/cross-spread header. Spread in basis points |

Click any item in the sidebar to view that panel full-screen.

---

## Project Structure

```
arbi_calculator/
├── backend/
│   ├── core/
│   │   ├── bus.py          # Async Pub/Sub signal bus
│   │   ├── config.py       # Pydantic-settings config (env-driven)
│   │   └── types.py        # Canonical domain types (Ticker, OrderBook, Signal)
│   ├── ingestion/
│   │   ├── manager.py      # Adapter lifecycle (asyncio.TaskGroup)
│   │   └── adapters/
│   │       ├── base.py     # Abstract adapter + exponential-backoff reconnect
│   │       ├── binance.py  # Binance combined stream (bookTicker + depth20)
│   │       └── kraken.py   # Kraken v2 WebSocket (ticker + book)
│   ├── models/
│   │   ├── features.py     # 7-dim node feature vector (OBI, log-return, spread, slopes)
│   │   └── gnn.py          # GATv2 multi-layer GNN with residual connections
│   ├── execution/
│   │   └── simulator.py    # P&L simulator: Sharpe, MDD, IR, fees, slippage
│   ├── plugins/
│   │   └── base.py         # BasePlugin + PluginRegistry
│   └── main.py             # Entrypoint
├── frontend/
│   └── src/
│       ├── app/            # Next.js 14 App Router
│       ├── components/
│       │   ├── layout/     # DashboardLayout, Sidebar
│       │   └── widgets/    # registry.ts + all widget components
│       ├── hooks/
│       │   ├── useWebSocket.ts   # Singleton WS + latency tracking
│       │   └── useMockData.ts    # Dev mock data feed
│       ├── store/          # Zustand (market / gnn / performance / ui slices)
│       └── types/          # Shared TypeScript types
├── test_binance_ws.py      # Connectivity smoke test
└── .gitignore
```

---

## Extending the System

### Add a new exchange (backend)

```python
# backend/ingestion/adapters/my_exchange.py
from .base import BaseAdapter
from backend.core.types import ExchangeID, Ticker, OrderBook

class MyExchangeAdapter(BaseAdapter):
    @property
    def ws_url(self) -> str: ...
    def build_subscribe_message(self, symbols): ...
    def parse_ticker(self, raw) -> Ticker | None: ...
    def parse_order_book(self, raw) -> OrderBook | None: ...
```

Register it in `backend/ingestion/manager.py` inside `_register_defaults`.

### Add a new analytical module (backend)

```python
# backend/plugins/my_plugin.py
from backend.plugins.base import BasePlugin
from backend.core.types import Signal, SignalTopic

class MyPlugin(BasePlugin):
    name = "my-plugin"
    subscribed_topics = [SignalTopic.GNN_ALPHA]

    async def on_signal(self, signal: Signal) -> None:
        print(signal.payload)
```

Register it in `backend/main.py`:
```python
registry.register(MyPlugin())
```

### Add a new dashboard widget (frontend)

```tsx
// frontend/src/components/widgets/MyWidget.tsx
export function MyWidget({ symbol }: WidgetProps) {
  return <div>...</div>;
}
```

Add one entry to `frontend/src/components/widgets/registry.ts`:
```ts
{
  id: "my-widget", label: "My Tool",
  description: "...", icon: "",
  component: MyWidget,
}
```

The sidebar and overview grid populate automatically. No layout code changes required.

---

## Known Limitations / Roadmap

| Item | Status |
|---|---|
| WebSocket broadcast server (backend → frontend) | Not yet implemented; frontend uses mock data |
| GNN training loop | Architecture complete; `train.py` not yet written |
| Model checkpoint auto-loading on startup | Pending training loop |
| Coinbase and OKX adapters | Enum declared; adapters not implemented |
| Historical data loader for backtesting | Not yet implemented |
| Prometheus metrics server | Config declares port 9090; server not yet started |

---

## Development Scripts

```bash
# Backend — type check
mypy backend/

# Backend — lint
ruff check backend/

# Backend — tests
pytest

# Frontend — type check
cd frontend && npm run type-check

# Frontend — lint
cd frontend && npm run lint

# Frontend — production build
cd frontend && npm run build
```
