"""
Stage 2 Formal Sweep: Hardware Deployment
=========================================
Executes the sweep on the physical Raspberry Pi. 
Sweeps over models and contention workers ONLY.
Network RTT and BW are dictated purely by the physical Ethernet connection.
"""

import argparse
import csv
import os
import time
from datetime import datetime
from typing import Dict, List

from split_inference.run_gonogo_hardware import run_single_trial

DEFAULT_WORKERS = [1, 2, 4, 6, 8]
DEFAULT_MODELS = ["resnet18", "mobilenetv2"]
RESULTS_DIR = "results"

CSV_FIELDS = [
    "model", "workers", "trial",
    "k_0", "k_a", "decision_changed",
    "J_k0_benign_ms", "J_k0_attacked_ms", "J_ka_benign_ms",
    "delta_phys_ms", "delta_probe_ctrl_ms",
]

def run_cell(
    model_name: str,
    workers: int,
    n_trials: int,
    server_host: str,
    server_port: int,
) -> List[Dict]:
    """Runs n_trials trials for one parameter cell."""
    cell_results = []
    for t in range(n_trials):
        trial = run_single_trial(
            server_host=server_host,
            server_port=server_port,
            stressor_workers=workers,
            nominal_rounds=40,
            attack_burst_rounds=12,
            eval_samples=15
        )
        trial.update({
            "model": model_name,
            "workers": workers,
            "trial": t + 1,
        })
        cell_results.append(trial)
    return cell_results

def main():
    parser = argparse.ArgumentParser(description="Stage 2 Sweep for Hardware Deployment")
    parser.add_argument("--host", type=str, required=True, help="IP address of the Edge Server (PC)")
    parser.add_argument("--port", type=int, default=5005, help="Edge Server port")
    parser.add_argument("--trials", type=int, default=20, help="Trials per cell (default 20)")
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS, choices=["resnet18", "mobilenetv2"])
    parser.add_argument("--workers-range", nargs=2, type=int, default=None, metavar=("MIN", "MAX"))
    parser.add_argument("--quick", action="store_true", help="Smoke test: 3 trials, workers=[2,6]")
    args = parser.parse_args()

    # Build parameter lists
    if args.quick:
        workers_list = [2, 6]
        n_trials = 3
    else:
        if args.workers_range:
            workers_list = list(range(args.workers_range[0], args.workers_range[1] + 1))
        else:
            workers_list = DEFAULT_WORKERS
        n_trials = args.trials

    # Build full grid
    grid = [(model, w) for model in args.models for w in workers_list]
    total_cells = len(grid)
    total_trials = total_cells * n_trials

    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(RESULTS_DIR, f"hardware_results_{timestamp}.csv")

    print("=" * 80)
    print("STAGE 2: HARDWARE CAMPAIGN SWEEP")
    print(f"  Connecting to PC: {args.host}:{args.port}")
    print(f"  Models:  {args.models}")
    print(f"  Workers: {workers_list}")
    print(f"  Trials per cell: {n_trials}")
    print(f"  Total cells: {total_cells}  |  Total trials: {total_trials}")
    print(f"  Results: {csv_path}")
    print("=" * 80)

    all_results: List[Dict] = []
    
    with open(csv_path, mode="w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()

        for cell_idx, (model_name, workers) in enumerate(grid):
            print(f"\n[Cell {cell_idx+1}/{total_cells}] model={model_name} workers={workers}")
            cell_rows = run_cell(
                model_name=model_name,
                workers=workers,
                n_trials=n_trials,
                server_host=args.host,
                server_port=args.port,
            )
            all_results.extend(cell_rows)
            for row in cell_rows:
                writer.writerow({k: row.get(k, "") for k in CSV_FIELDS})
            f.flush()

    print("\n" + "=" * 80)
    print("SWEEP COMPLETE")
    print(f"  Results saved to: {csv_path}")
    print("=" * 80)

if __name__ == "__main__":
    main()
