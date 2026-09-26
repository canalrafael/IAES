"""
Split Inference Edge Client with Unmodified ANS muLinUCB Controller
===================================================================
Executes local prefix F_k(x), offloads intermediate activations z_k to
the server via TCP streaming, measures fine-grained latency components,
and updates the unmodified muLinUCB bandit controller on the fly.

Network Emulation:
  Since Stage 1 runs on a single machine (loopback), we inject a
  realistic network delay model (RTT + bandwidth cap) into the client.
  This reproduces the latency landscape of a real Raspberry Pi 4 <->
  PC edge setup over 100 Mbps Ethernet or 20 Mbps Wi-Fi/4G.
  All measured latencies (local + simulated network) are fed unmodified
  to the ANS muLinUCB controller, preserving its zero-modification guarantee.
"""

from dataclasses import dataclass
import socket
import time
from typing import Dict, Optional, Tuple
import torch

from split_inference.controller.muLinUCB import muLinUCB
from split_inference.model.models import PartitionedResNet18, get_resnet18_layer_info
from split_inference.network.protocol import send_activation, recv_prediction


@dataclass
class InferenceRecord:
    frame_idx: int
    split_point: int
    local_latency_ms: float
    comm_server_latency_ms: float
    total_latency_ms: float
    bytes_transmitted: int


class SplitInferenceClient:
    def __init__(
        self,
        server_host: str = "127.0.0.1",
        server_port: int = 5005,
        device: str = "cpu",
        mu_rate: float = 0.25,
        layer_info: Optional[Dict] = None,
        network_rtt_ms: float = 5.0,
        network_bw_mbps: float = 100.0,
        edge_slowdown_factor: float = 4.0
    ):
        """
        Args:
            network_rtt_ms: One-way RTT for the emulated edge network (ms).
                            Defaults to 5 ms (Ethernet Pi-to-PC).
                            Use 50 ms for Wi-Fi, 100+ ms for 4G.
            network_bw_mbps: Emulated uplink bandwidth in Mbps.
                             Defaults to 100 Mbps (Ethernet).
                             Use 20 Mbps for Wi-Fi/4G.
            edge_slowdown_factor: Multiplier applied to local inference time
                             to emulate an edge device (e.g., Raspberry Pi 4).
                             Raspberry Pi 4 is ~4-5x slower than a modern PC
                             for ResNet-18 inference. Set to 1.0 to disable.
        """
        self.server_host = server_host
        self.server_port = server_port
        self.device = torch.device(device)
        self.model = PartitionedResNet18().to(self.device)
        self.model.eval()

        # Network & edge emulation parameters
        self.network_rtt_ms = network_rtt_ms
        self.network_bw_mbps = network_bw_mbps
        self.edge_slowdown_factor = edge_slowdown_factor

        self.layer_info = layer_info if layer_info is not None else get_resnet18_layer_info()
        self.num_actions = len(self.layer_info)

        # Initialize unmodified ANS muLinUCB controller
        front_delay = [0.0 for _ in range(self.num_actions)]
        self.controller = muLinUCB(mu_rate, self.layer_info, front_delay)

        self._sock: Optional[socket.socket] = None
        self.frame_idx = 0

    def _simulate_network_latency(self, tensor: torch.Tensor) -> float:
        """Returns the emulated transfer time in seconds for the given tensor.
        Returns 0.0 when network_bw_mbps=0.0 (hardware mode — no emulation).
        """
        if self.network_bw_mbps <= 0.0:
            return 0.0
        num_bytes = tensor.nelement() * tensor.element_size()
        transfer_time_s = (num_bytes * 8) / (self.network_bw_mbps * 1e6)
        rtt_s = self.network_rtt_ms / 1000.0
        return rtt_s + transfer_time_s

    def connect(self) -> None:
        """Establishes TCP connection to the edge server."""
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._sock.connect((self.server_host, self.server_port))

    def close(self) -> None:
        """Closes connection to the edge server."""
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def run_inference(
        self,
        x: torch.Tensor,
        forced_k: Optional[int] = None,
        update_controller: bool = True,
        is_key_frame: bool = True
    ) -> Tuple[torch.Tensor, InferenceRecord]:
        """
        Executes one collaborative inference.
        
        Args:
            x: Input tensor [1, 3, 224, 224]
            forced_k: If provided, bypasses controller and forces split point k
            update_controller: If True, feeds observed latency back into muLinUCB
            is_key_frame: Flag for muLinUCB confidence weighting
        """
        self.frame_idx += 1
        current_frame = self.frame_idx

        # 1. Split Decision
        if forced_k is not None:
            k = forced_k
        else:
            self.controller.updateDoublingTrickFrameNum(current_frame)
            k = self.controller.getEstimationAction(key_frame=is_key_frame, current_frame=current_frame)

        x = x.to(self.device)

        # 2. Local Prefix Computation F_k(x)
        t_loc_start = time.perf_counter()
        with torch.no_grad():
            z = self.model.forward_prefix(x, k)
        t_loc = time.perf_counter() - t_loc_start

        # Edge slowdown emulation: sleep to simulate the Pi 4 being ~4x slower
        # than the PC. This is added AFTER the measurement so t_loc itself is
        # the "extra" Pi latency above the actual PC compute.
        if self.edge_slowdown_factor > 1.0:
            extra_sleep = t_loc * (self.edge_slowdown_factor - 1.0)
            time.sleep(extra_sleep)
            t_loc *= self.edge_slowdown_factor

        bytes_sent = 0
        t_comm_server = 0.0

        # 3. Offload or Local Evaluation
        if k == 0:
            # Full local: z is already the final logits
            pred = z
        else:
            # Inject emulated network delay (RTT + bandwidth) BEFORE
            # actual socket transfer — this makes the controller see
            # the realistic total cost of offloading, as it would on
            # a real Raspberry Pi 4 connected via Ethernet to a server.
            # In hardware mode (network_bw_mbps=0.0), this returns 0.0
            # and the sleep is skipped — real physical latency is used.
            emulated_net_delay = self._simulate_network_latency(z)
            if emulated_net_delay > 0.0:
                time.sleep(emulated_net_delay)

            # Actual socket transfer
            if self._sock is None:
                self.connect()

            t_comm_start = time.perf_counter()
            bytes_sent = send_activation(self._sock, z, k)
            pred, _ = recv_prediction(self._sock)
            t_comm_server = time.perf_counter() - t_comm_start + emulated_net_delay

        total_latency = t_loc + t_comm_server

        # 4. Online Bandit Update (Zero offline profiling - pure online feedback)
        if update_controller:
            self.controller.updateA_b(k, total_latency)

        record = InferenceRecord(
            frame_idx=current_frame,
            split_point=k,
            local_latency_ms=t_loc * 1000.0,
            comm_server_latency_ms=t_comm_server * 1000.0,
            total_latency_ms=total_latency * 1000.0,
            bytes_transmitted=bytes_sent
        )

        return pred, record
