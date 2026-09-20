# Hardware Deployment Guide (Raspberry Pi 4)

This guide explains how to run the adversarial split inference experiments using real hardware: your PC acting as the Edge Server, and a Raspberry Pi acting as the edge client.

## 1. Setup the Edge Server (PC)

The Edge Server is the "Cloud/Edge" component that receives intermediate activations and computes the DNN suffix. It must run on your PC.

1. Connect your PC and Raspberry Pi via an Ethernet cable (or to the same Wi-Fi network).
2. Find your PC's IP address on that network:
   - On Windows, open PowerShell and run `ipconfig`. Look for the IPv4 address under your Ethernet adapter (e.g., `192.168.1.x` or `169.254.x.x`).
3. Start the standalone server:
   ```bash
   python -m split_inference.run_hardware_server --port 5005
   ```
   Leave this terminal running.

## 2. Setup the Edge Client (Raspberry Pi)

1. Clone or copy this repository to your Raspberry Pi.
2. Install the necessary dependencies (we recommend setting up a virtual environment):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r split_inference/requirements_pi.txt
   ```

## 3. Running Experiments on the Pi

You can run both the Go/No-Go feasibility test and the full Stage 2 formal sweep directly from the Pi.

### Important Flags
To run in hardware mode, you must pass two key flags:
* `--remote-server`: Tells the script **not** to start its own background server.
* `--hardware-mode`: Disables software emulation (`--rtt 0.0`, `--bw 0.0`, `--slowdown 1.0`) so the controller uses the *real* physical network latency and hardware processing times.
* `--host <PC_IP>`: Connect to the PC.

### Run Go/No-Go Feasibility Test
```bash
python3 -m split_inference.run_gonogo_hardware \
  --host <YOUR_PC_IP_ADDRESS> \
  --port 5005 \
  --workers 4
```

### Run Full Stage 2 Formal Sweep
```bash
python3 -m split_inference.run_stage2_hardware \
  --host <YOUR_PC_IP_ADDRESS> \
  --port 5005 \
  --trials 20 \
  --models resnet18 mobilenetv2 \
  --workers-range 1 8
```

After the sweep finishes, copy the resulting `results/hardware_results_*.csv` file back to your PC and run the `analyze_results.py` script there to generate the PDF figures!
