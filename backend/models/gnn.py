"""
Lead-Lag Graph Neural Network.

Graph topology
──────────────
  Nodes  : one per exchange (e.g., Binance=0, Kraken=1, Coinbase=2).
  Edges  : fully connected directed graph — every node can attend to every
           other node.  Edge weights are learned, encoding lead-lag strength.

Forward pass
────────────
  1. Node features [N, F_dim] → GATv2Conv layers → contextualised embeddings.
  2. Global graph-level readout (mean pooling) → MLP → alpha signal scalar.
     alpha > 0  → predict lag exchange will rise (long lag / short lead).
     alpha < 0  → predict lag exchange will fall (short both or flat).

Why GATv2?
──────────
  Standard GAT computes attention weights that depend only on the *static*
  combination of source + target features, making them input-dependent only
  through a fixed linear map.  GATv2 computes a dynamic, data-dependent
  softmax that is strictly more expressive — important when the lead-lag
  relationship itself is non-stationary.
"""

from __future__ import annotations

from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    from torch_geometric.nn import GATv2Conv, global_mean_pool
    from torch_geometric.data import Data, Batch
    _PYG_AVAILABLE = True
except ImportError:
    _PYG_AVAILABLE = False


class LeadLagGNN(nn.Module):
    """
    Args:
        num_nodes:       Number of exchange nodes (graph size).
        in_channels:     Node feature dimension (F_dim from FeatureBuilder).
        hidden_channels: GATv2 hidden dimension.
        num_layers:      Number of message-passing layers.
        heads:           Multi-head attention heads per GATv2 layer.
        dropout:         Dropout applied after each layer.
        out_dim:         Prediction head output size (1 = scalar alpha).
    """

    def __init__(
        self,
        num_nodes:       int   = 4,
        in_channels:     int   = 7,
        hidden_channels: int   = 64,
        num_layers:      int   = 3,
        heads:           int   = 4,
        dropout:         float = 0.1,
        out_dim:         int   = 1,
    ) -> None:
        super().__init__()

        if not _PYG_AVAILABLE:
            raise ImportError(
                "torch_geometric is not installed.  "
                "Run: pip install torch-geometric torch-scatter torch-sparse"
            )

        self.num_nodes       = num_nodes
        self.hidden_channels = hidden_channels
        self.dropout         = dropout

        # Input projection — avoids the in_channels × heads mismatch on layer 2+
        self.input_proj = nn.Linear(in_channels, hidden_channels)

        # GATv2 stack — each layer's output dim = hidden_channels (concat then proj)
        self.convs = nn.ModuleList()
        for _ in range(num_layers):
            self.convs.append(
                GATv2Conv(
                    in_channels=hidden_channels,
                    out_channels=hidden_channels // heads,
                    heads=heads,
                    dropout=dropout,
                    concat=True,   # output dim = (hidden // heads) * heads = hidden
                )
            )

        # Batch norm after each conv for training stability on non-stationary data
        self.norms = nn.ModuleList(
            [nn.LayerNorm(hidden_channels) for _ in range(num_layers)]
        )

        # Prediction head: graph-pooled embedding → alpha scalar
        self.head = nn.Sequential(
            nn.Linear(hidden_channels, hidden_channels // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_channels // 2, out_dim),
        )

        # Fully-connected edge index (no self-loops for directed attention)
        self.register_buffer(
            "edge_index", _fully_connected_edges(num_nodes), persistent=False
        )

    # ── Forward ───────────────────────────────────────────────────────────────

    def forward(
        self,
        x:          torch.Tensor,                    # [N_nodes, F_dim] or [B*N, F_dim]
        batch:      Optional[torch.Tensor] = None,   # PyG batch vector
        edge_index: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Returns: alpha tensor of shape [1] (single graph) or [B] (batched).
        """
        ei = edge_index if edge_index is not None else self.edge_index

        x = self.input_proj(x)
        x = F.gelu(x)

        for conv, norm in zip(self.convs, self.norms):
            residual = x
            x = conv(x, ei)
            x = norm(x)
            x = F.gelu(x)
            x = x + residual                         # residual connection
            x = F.dropout(x, p=self.dropout, training=self.training)

        # Graph-level readout
        if batch is None:
            # Single graph: simple mean over nodes
            x = x.mean(dim=0, keepdim=True)          # [1, H]
        else:
            x = global_mean_pool(x, batch)            # [B, H]

        return self.head(x).squeeze(-1)              # [1] or [B]

    # ── Inference helper ──────────────────────────────────────────────────────

    @torch.no_grad()
    def predict(self, node_features: torch.Tensor) -> float:
        """Convenience wrapper for single-graph online inference."""
        self.eval()
        alpha = self(node_features)
        return float(alpha.item())

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: str) -> None:
        torch.save(self.state_dict(), path)

    def load(self, path: str, map_location: str = "cpu") -> None:
        self.load_state_dict(torch.load(path, map_location=map_location))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fully_connected_edges(n: int) -> torch.Tensor:
    """Returns edge_index [2, N*(N-1)] for a directed complete graph."""
    src, dst = [], []
    for i in range(n):
        for j in range(n):
            if i != j:
                src.append(i)
                dst.append(j)
    return torch.tensor([src, dst], dtype=torch.long)
