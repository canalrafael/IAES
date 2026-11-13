"""
ANS 1000-Frame Stress & Adaptation Experiment Harness (Bao Hypervisor Edition)
=============================================================================
Features:
  - Dataset support: cycles through ImageNet validation images (or fallback sample).
  - Accuracy tracking: evaluates Top-1 and Top-5 accuracy across nominal/attack/recovery.
  - Inter-VM IPC synchronization: triggers memory contention on VM3 via Bao shared memory (0x70020000).
  - Telemetry & auto-sync: writes local CSV and uploads directly to PC edge server at completion.
"""

import argparse
import os
import sys
import time
import subprocess
import torch

from muLinUCB import muLinUCB
from communication import clientCommunication
from models.vgg16 import vgg16
from client_camera_main import partitionInfo, load_obj
from experiments.data_logger import ExperimentLogger
from dataset_evaluator import DatasetEvaluator


def parse_args():
    parser = argparse.ArgumentParser(description="ANS Split Inference Experiment on Bao Hypervisor")
    parser.add_argument('--scenario', type=str, default='scenario_a', choices=['scenario_a', 'scenario_b', 'scenario_c'],
                        help="Attack profile scenario (a: 500-250-250, b: 200-600-200, c: 200-200-600)")
    parser.add_argument('--total_frames', type=int, default=1000, help="Total frames to execute (default: 1000)")
    parser.add_argument('--host', type=str, default='192.168.2.1', help="Edge server IP address")
    parser.add_argument('--port', type=int, default=5005, help="Edge server port")
    parser.add_argument('--dataset_dir', type=str, default='models/dataset', help="Directory containing ImageNet validation images")
    parser.add_argument('--use_ipc', action='store_true', default=True, help="Trigger VM3 memory contention via Bao IPC")
    return parser.parse_args()


def set_vm3_contention_ipc(enable: bool):
    """Signals VM3 via Bao IPC Channel 2 (mapped at 0x70020000 on VM2)."""
    val = "1" if enable else "0"
    ipc_tool = "/root/ipc_signal"
    if os.path.exists(ipc_tool):
        try:
            # write offset 0 value (1=start, 0=stop)
            subprocess.run([ipc_tool, "write", "0", val], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"[IPC-SIGNAL] Set VM3 contention trigger = {val}")
        except Exception as e:
            print(f"[IPC-SIGNAL WARNING] Could not write to IPC: {e}")


def sync_to_server(host: str, port: int, filename: str, content: str):
    """Sends synchronization packet to edge server to save CSV directly on the PC."""
    print(f"\n[SYNC] Uploading {filename} to Edge Server ({host}:{port})...")
    try:
        comm = clientCommunication(host, port)
        sync_packet = {
            'type': 'SYNC_FILE',
            'filename': filename,
            'content': content
        }
        comm.send_msg(sync_packet)
        ack = comm.receive_msg()
        comm.close_channel()
        print(f"[SYNC] Successfully synchronized to PC! Server reply: {ack}")
        return True
    except Exception as e:
        print(f"[SYNC WARNING] Could not auto-sync to PC server ({e}). Data remains safely saved locally on Raspberry Pi.")
        return False


def get_phase_info(scenario: str, frame_idx: int):
    if scenario == 'scenario_a':
        if frame_idx < 500:
            return "Phase 1 - Nominal", False
        elif frame_idx < 750:
            return "Phase 2 - Attack", True
        else:
            return "Phase 3 - Recovery", False
    elif scenario == 'scenario_b':
        if frame_idx < 200:
            return "Phase 1 - Nominal", False
        elif frame_idx < 800:
            return "Phase 2 - Attack", True
        else:
            return "Phase 3 - Recovery", False
    elif scenario == 'scenario_c':
        if frame_idx < 200:
            return "Phase 1 - Nominal", False
        elif frame_idx < 400:
            return "Phase 2 - Attack", True
        else:
            return "Phase 3 - Recovery", False
    return "Phase 1 - Nominal", False


def main():
    args = parse_args()
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print("==================================================")
    print(f"ANS Split Inference on Bao Hypervisor (VM2)")
    print(f"Target Server: {args.host}:{args.port}")
    print(f"Scenario: {args.scenario} | Total Frames: {args.total_frames}")
    print(f"Execution Device: {device}")
    print("==================================================")

    # Initialize model
    model = vgg16(pretrained=False)
    model.eval()
    model.to(device)

    # Load calibrated frontend delay profile
    frontEndDelay = load_obj('models/vgg16FrontEndDelay')
    mu_controller = muLinUCB(mu=0.25, layerInfo=partitionInfo, frontDelay=frontEndDelay)

    # Initialize dataset evaluator
    evaluator = DatasetEvaluator(dataset_dir=args.dataset_dir)
    print(f"[DATASET] Loaded {len(evaluator.image_files)} evaluation images.")

    # Initialize data logger
    exp_name = f"ans_bao_memory_{args.scenario}"
    logger = ExperimentLogger(experiment_name=exp_name, total_frames=args.total_frames)
    print(f"[LOGGER] Local CSV output: {logger.filepath}")

    attack_active_last = False
    current_doubling_frame = 0

    try:
        for frame_idx in range(1, args.total_frames + 1):
            phase_name, should_attack = get_phase_info(args.scenario, frame_idx)

            # Inter-VM IPC Phase transitions
            if should_attack and not attack_active_last:
                print(f"\n>>> [TRANSITION] Entering {phase_name} at frame {frame_idx}! Triggering VM3 MEMHOG via IPC... <<<")
                if args.use_ipc:
                    set_vm3_contention_ipc(True)
                attack_active_last = True
            elif not should_attack and attack_active_last:
                print(f"\n>>> [TRANSITION] Entering {phase_name} at frame {frame_idx}! Stopping VM3 MEMHOG via IPC... <<<")
                if args.use_ipc:
                    set_vm3_contention_ipc(False)
                attack_active_last = False

            # Doubling trick
            current_doubling_frame += 1
            if mu_controller.updateDoublingTrickFrameNum(current_doubling_frame):
                current_doubling_frame = 0

            # Get frame from dataset
            input_tensor, ground_truth, img_path = evaluator.get_frame(frame_idx)

            # Controller selects partition point
            is_key_frame = True # evaluate keyframe path
            partition = mu_controller.getEstimationAction(is_key_frame, current_doubling_frame)
            is_forced = (current_doubling_frame % mu_controller.forceSampleFrame == 0)

            # Local frontend execution
            t_local_start = time.time()
            if partition == len(partitionInfo) - 1:
                # Full local inference
                intermediate_output = model(input_tensor.to(device))
                t_local_end = time.time()
                local_delay = t_local_end - t_local_start
                offload_delay = 0.0
                res = intermediate_output
            else:
                intermediate_output = model(input_tensor.to(device), server=False, partition=partition)
                t_local_end = time.time()
                local_delay = t_local_end - t_local_start

                # Send intermediate tensor to edge server
                data_to_server = [partition, intermediate_output.data.cpu()]
                del intermediate_output

                t_offload_start = time.time()
                communication = clientCommunication(args.host, args.port)
                communication.send_msg(data_to_server)
                res = communication.receive_msg()
                communication.close_channel()
                t_offload_end = time.time()
                offload_delay = t_offload_end - t_offload_start

            # Update bandit parameters
            mu_controller.updateA_b(partition, offload_delay)

            # Track classification accuracy
            if isinstance(res, torch.Tensor):
                is_top1, is_top5, top1_acc, top5_acc = evaluator.update_accuracy(res, ground_truth)
            else:
                top1_acc, top5_acc = 0.0, 0.0

            # Log frame metrics
            record = logger.log_frame(
                frame=frame_idx,
                scenario=args.scenario,
                phase=phase_name,
                attack_type="memory_contention_vm3",
                partition=partition,
                offload_delay_s=offload_delay,
                local_delay_s=local_delay,
                is_key_frame=is_key_frame,
                is_forced_sampling=is_forced
            )

            if frame_idx % 25 == 0 or frame_idx == 1:
                print(f"[{phase_name[:7]}] Frame {frame_idx:4d}/{args.total_frames} | Split: {partition:2d} | "
                      f"Local: {local_delay*1000:6.1f}ms | Net+Srv: {offload_delay*1000:6.1f}ms | "
                      f"Total: {(local_delay+offload_delay)*1000:6.1f}ms | Top1-Acc: {top1_acc:.1f}%")

    except KeyboardInterrupt:
        print("\n[STOP] Experiment interrupted by user.")
    finally:
        # Guarantee VM3 contention is turned off
        if args.use_ipc:
            set_vm3_contention_ipc(False)

        csv_text = logger.close()
        print(f"\n[DONE] Saved {len(logger.records)} frame records to local CSV: {logger.filepath}")

        # Automatically sync full CSV to PC
        sync_to_server(args.host, args.port, logger.filename, csv_text)


if __name__ == '__main__':
    main()
