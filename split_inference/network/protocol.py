"""
TCP Streaming Protocol for Split Inference Activations
======================================================
Implements efficient framed socket communication for transferring
intermediate activations (z_k) and classification results between
the edge client and edge server.
"""

import io
import struct
from typing import Tuple
import socket
import torch

MAGIC_HEADER = b"SPLT"
MAGIC_RESP = b"RESP"


def send_exact(sock: socket.socket, data: bytes) -> None:
    """Ensures all bytes in buffer are completely transmitted."""
    total_sent = 0
    while total_sent < len(data):
        sent = sock.send(data[total_sent:])
        if sent == 0:
            raise ConnectionError("Socket connection closed during send.")
        total_sent += sent


def recv_exact(sock: socket.socket, num_bytes: int) -> bytes:
    """Blocks until exactly num_bytes are received."""
    chunks = []
    bytes_recd = 0
    while bytes_recd < num_bytes:
        chunk = sock.recv(min(num_bytes - bytes_recd, 65536))
        if not chunk:
            raise ConnectionError("Socket connection closed during recv.")
        chunks.append(chunk)
        bytes_recd += len(chunk)
    return b"".join(chunks)


def send_activation(sock: socket.socket, tensor: torch.Tensor, k: int) -> int:
    """
    Serializes and sends an activation tensor with split point k.
    Returns the total bytes transmitted over the wire.
    """
    buf = io.BytesIO()
    torch.save(tensor.cpu(), buf)
    payload = buf.getvalue()

    # Header format: [Magic(4B)][PayloadLen(4B)][SplitPoint_k(1B)]
    header = MAGIC_HEADER + struct.pack("!IB", len(payload), k)
    send_exact(sock, header + payload)
    return len(header) + len(payload)


def recv_activation(sock: socket.socket) -> Tuple[torch.Tensor, int, int]:
    """
    Receives and deserializes an activation tensor.
    Returns: (tensor, k, bytes_received)
    """
    header = recv_exact(sock, 9)
    magic = header[:4]
    if magic != MAGIC_HEADER:
        raise ValueError(f"Invalid protocol magic: {magic}")
    
    payload_len, k = struct.unpack("!IB", header[4:9])
    payload = recv_exact(sock, payload_len)
    
    buf = io.BytesIO(payload)
    tensor = torch.load(buf, weights_only=True)
    return tensor, k, 9 + payload_len


def send_prediction(sock: socket.socket, tensor: torch.Tensor) -> int:
    """Sends server classification output back to client."""
    buf = io.BytesIO()
    torch.save(tensor.cpu(), buf)
    payload = buf.getvalue()
    header = MAGIC_RESP + struct.pack("!I", len(payload))
    send_exact(sock, header + payload)
    return len(header) + len(payload)


def recv_prediction(sock: socket.socket) -> Tuple[torch.Tensor, int]:
    """Receives server classification output."""
    header = recv_exact(sock, 8)
    magic = header[:4]
    if magic != MAGIC_RESP:
        raise ValueError(f"Invalid response magic: {magic}")
    
    payload_len, = struct.unpack("!I", header[4:8])
    payload = recv_exact(sock, payload_len)
    
    buf = io.BytesIO(payload)
    tensor = torch.load(buf, weights_only=True)
    return tensor, 8 + payload_len
