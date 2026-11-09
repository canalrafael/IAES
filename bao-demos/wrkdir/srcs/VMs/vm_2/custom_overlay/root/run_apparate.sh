#!/bin/sh
# Run the Apparate replay controller on VM2. Usage: run_apparate.sh [ARCH] [DATASET]
ARCH="${1:-resnet18}"; DATASET="${2:-auburn}"
cd /root/apparate-ae/apparate || exit 1
python3 controller.py --dataset video --arch "${ARCH}_${DATASET}" --batch_size 4 \
  --profile_dir ./profile_pickles_bs \
  --bootstrap_pickle_path "../bootstrap_pickles/bootstrap_${DATASET}_${ARCH}.pickle" \
  --data_dir "${DATASET}" --num_classes 2 --model_dir ../models \
  --batching_scheme clockwork \
  --simulation_pickle_path "../simulation_pickles/${DATASET}_${ARCH}.pickle" \
  --batch_decision_path "../batch_decisions/${ARCH}_1_fixed_30.pickle" --slo 1 --qps 30
