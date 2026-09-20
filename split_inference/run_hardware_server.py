"""
Standalone Hardware Server for Split Inference
==============================================
Runs the EdgeInferenceServer indefinitely on the PC to listen for incoming 
activations from a physically separate Raspberry Pi edge device.

Usage:
    python -m split_inference.run_hardware_server --port 5005
"""

import argparse
import time

from split_inference.network.server import EdgeInferenceServer

def main():
    parser = argparse.ArgumentParser(description="Standalone Edge Server for Hardware Deployment")
    parser.add_argument("--port", type=int, default=5005, help="Port to listen on")
    args = parser.parse_args()

    print("=" * 80)
    print(f"STARTING EDGE INFERENCE SERVER ON PORT {args.port}")
    print("Listening on 0.0.0.0 (all network interfaces)...")
    print("=" * 80)
    print("Keep this terminal open while running experiments on the Raspberry Pi.")
    
    # 0.0.0.0 allows it to accept connections from the Pi over Ethernet
    server = EdgeInferenceServer(host="0.0.0.0", port=args.port)
    server.start(background=False)  # Blocking run
    
if __name__ == "__main__":
    main()
