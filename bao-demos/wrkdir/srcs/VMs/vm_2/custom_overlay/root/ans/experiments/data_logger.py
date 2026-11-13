"""
Data Logger & Telemetry Module for ANS Split Inference Experiments
==================================================================
Captures frame-by-frame metrics on the Raspberry Pi client and enables:
1. Local CSV logging on the Raspberry Pi.
2. Real-time telemetry streaming to the edge server.
3. Automatic end-of-experiment file synchronization to the PC.
"""

import csv
import os
import time
from typing import Dict, Any, Optional


class ExperimentLogger:
    def __init__(self, experiment_name: str, output_dir: str = 'experiments/data', total_frames: int = 1000):
        self.experiment_name = experiment_name
        self.output_dir = output_dir
        self.total_frames = total_frames
        os.makedirs(self.output_dir, exist_ok=True)

        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        self.filename = f"{experiment_name}_{timestamp_str}.csv"
        self.filepath = os.path.join(self.output_dir, self.filename)

        self.fieldnames = [
            'frame',
            'timestamp',
            'scenario',
            'phase',
            'attack_type',
            'partition',
            'offload_delay_s',
            'local_delay_s',
            'end_to_end_s',
            'avg_end_to_end_s',
            'is_key_frame',
            'is_forced_sampling'
        ]

        self.csv_file = open(self.filepath, 'w', newline='', encoding='utf-8')
        self.writer = csv.DictWriter(self.csv_file, fieldnames=self.fieldnames)
        self.writer.writeheader()
        self.csv_file.flush()

        self.records = []
        self.total_time = 0.0

    def log_frame(
        self,
        frame: int,
        scenario: str,
        phase: str,
        attack_type: str,
        partition: int,
        offload_delay_s: float,
        local_delay_s: float,
        is_key_frame: bool = False,
        is_forced_sampling: bool = False
    ) -> Dict[str, Any]:
        """Logs a single frame inference record."""
        end_to_end_s = local_delay_s + offload_delay_s
        self.total_time += end_to_end_s
        avg_end_to_end_s = self.total_time / frame

        record = {
            'frame': frame,
            'timestamp': round(time.time(), 4),
            'scenario': scenario,
            'phase': phase,
            'attack_type': attack_type,
            'partition': int(partition),
            'offload_delay_s': round(float(offload_delay_s), 4),
            'local_delay_s': round(float(local_delay_s), 4),
            'end_to_end_s': round(float(end_to_end_s), 4),
            'avg_end_to_end_s': round(float(avg_end_to_end_s), 4),
            'is_key_frame': int(is_key_frame),
            'is_forced_sampling': int(is_forced_sampling)
        }

        self.writer.writerow(record)
        self.csv_file.flush()
        self.records.append(record)
        return record

    def close(self) -> str:
        """Closes the CSV file and returns its content as a string for synchronization."""
        if not self.csv_file.closed:
            self.csv_file.close()

        with open(self.filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        return content
