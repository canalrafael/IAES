"""
Edge Server Daemon for Split Inference
======================================
Listens for incoming activation tensors from the edge client,
executes the remaining suffix G_k(z_k), and transmits predictions back.
"""

import socket
import threading
import time
from typing import Optional
import torch

from split_inference.model.models import PartitionedResNet18
from split_inference.network.protocol import recv_activation, send_prediction


class EdgeInferenceServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 5005, device: str = "cpu"):
        self.host = host
        self.port = port
        self.device = torch.device(device)
        self.model = PartitionedResNet18().to(self.device)
        self.model.eval()

        self._server_sock: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.total_inferences = 0

    def start(self, background: bool = True) -> None:
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.host, self.port))
        self._server_sock.listen(5)
        self._running = True

        if background:
            self._thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()
        else:
            self._listen_loop()

    def _listen_loop(self) -> None:
        self._server_sock.settimeout(1.0)
        while self._running:
            try:
                conn, _ = self._server_sock.accept()
            except (socket.timeout, OSError):
                continue

            # Handle client connection
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            try:
                self._handle_client(conn)
            except Exception:
                pass
            finally:
                conn.close()

    def _handle_client(self, conn: socket.socket) -> None:
        with torch.no_grad():
            while self._running:
                try:
                    z, k, _ = recv_activation(conn)
                except (ConnectionError, EOFError):
                    break

                z = z.to(self.device)
                t0 = time.perf_counter()
                out = self.model.forward_suffix(z, k)
                t_suffix = time.perf_counter() - t0

                send_prediction(conn, out)
                self.total_inferences += 1

    def stop(self) -> None:
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Split Inference Edge Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host IP to bind")
    parser.add_argument("--port", type=int, default=5005, help="Port to listen on")
    args = parser.parse_args()

    print(f"Starting Edge Inference Server on {args.host}:{args.port}...")
    server = EdgeInferenceServer(host=args.host, port=args.port)
    try:
        server.start(background=False)
    except KeyboardInterrupt:
        print("Stopping server...")
        server.stop()
