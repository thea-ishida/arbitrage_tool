"use client";

import { useEffect, useRef } from "react";
import { useAppStore } from "@/store";
import type { GNNAlpha, OrderBook, PerformanceReport, Ticker, WsMessage } from "@/types";

const WS_URL         = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";
const RECONNECT_BASE = 1_000;
const RECONNECT_MAX  = 30_000;

let _socket:      WebSocket | null = null;
let _retryDelay                    = RECONNECT_BASE;
let _retryTimer:  ReturnType<typeof setTimeout> | null = null;
let _pingTimer:   ReturnType<typeof setInterval> | null = null;
let _pingTs:      number | null = null;

function connect(
  onStatus:  (s: "connecting" | "connected" | "disconnected") => void,
  onLatency: (ms: number) => void,
  dispatch:  (msg: WsMessage) => void,
): void {
  if (_socket && _socket.readyState < WebSocket.CLOSING) return;

  onStatus("connecting");
  _socket = new WebSocket(WS_URL);

  _socket.onopen = () => {
    _retryDelay = RECONNECT_BASE;
    onStatus("connected");

    // Measure round-trip latency every 5s via a ping/pong
    _pingTimer = setInterval(() => {
      if (_socket?.readyState === WebSocket.OPEN) {
        _pingTs = performance.now();
        _socket.send(JSON.stringify({ type: "ping" }));
      }
    }, 5_000);
  };

  _socket.onmessage = (ev: MessageEvent<string>) => {
    try {
      const msg: WsMessage = JSON.parse(ev.data);

      // Handle pong for latency measurement
      if ((msg as unknown as { type: string }).type === "pong" && _pingTs !== null) {
        onLatency(Math.round(performance.now() - _pingTs));
        _pingTs = null;
        return;
      }

      dispatch(msg);
    } catch {
      // Malformed frame — discard
    }
  };

  _socket.onclose = () => {
    if (_pingTimer) clearInterval(_pingTimer);
    onStatus("disconnected");
    _retryTimer = setTimeout(() => {
      _retryDelay = Math.min(_retryDelay * 2, RECONNECT_MAX);
      connect(onStatus, onLatency, dispatch);
    }, _retryDelay);
  };

  _socket.onerror = () => {
    _socket?.close();
  };
}

export function useWebSocket(): void {
  const { setTicker, setOrderBook, pushAlpha, setReport, setWsStatus, setLatency } =
    useAppStore();

  const dispatchRef = useRef((msg: WsMessage) => {
    switch (msg.topic) {
      case "ticker":
        setTicker(msg.payload as Ticker);
        break;
      case "order_book":
        setOrderBook(msg.payload as OrderBook);
        break;
      case "gnn_alpha":
        pushAlpha(msg.payload as GNNAlpha);
        break;
      case "execution":
        setReport(msg.payload as PerformanceReport);
        break;
    }
  });

  useEffect(() => {
    connect(setWsStatus, setLatency, dispatchRef.current);
    return () => {
      if (_retryTimer) clearTimeout(_retryTimer);
    };
  }, [setWsStatus, setLatency]);
}
