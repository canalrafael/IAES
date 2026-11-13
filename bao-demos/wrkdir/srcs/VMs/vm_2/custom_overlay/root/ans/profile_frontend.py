#!/usr/bin/env python3
import time
import pickle
import torch
import torchvision.transforms as transforms
from PIL import Image
from models.vgg16 import vgg16

def profile_vgg16(num_trials=30, image_path='models/Golden_Retriever_Hund_Dog.jpg'):
    print('=== ANS VGG-16 Frontend Delay Profiler (Native Bao VM2) ===')
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print('Target device:', device)

    # 22 partition points (0 to 21 intermediate, 22 full local)
    total_actions = 23
    delays = [0.0] * total_actions

    print('Loading VGG-16 model...')
    model = vgg16(pretrained=False) # architecture only
    model.eval()
    model.to(device)

    # Transform input
    transform = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    raw_img = Image.open(image_path)
    input_tensor = transform(raw_img).unsqueeze(0).to(device)

    print(f'Starting profiling across {total_actions} split points ({num_trials} trials each)...')

    # Warmup
    for _ in range(5):
        _ = model(input_tensor, server=False, partition=5)

    # Split 0 is pure offload (0 ms local prefix computation)
    delays[0] = 0.0

    for action in range(1, total_actions):
        trial_times = []
        for _ in range(num_trials):
            t0 = time.time()
            if action == total_actions - 1:
                _ = model(input_tensor)
            else:
                _ = model(input_tensor, server=False, partition=action)
            t1 = time.time()
            trial_times.append(t1 - t0)

        # Drop first 5 as warmup, take mean of remaining
        steady_times = trial_times[5:] if len(trial_times) > 5 else trial_times
        avg_delay = sum(steady_times) / len(steady_times)
        delays[action] = avg_delay
        print(f'Partition {action:2d}: {avg_delay*1000:6.2f} ms')

    output_path = 'models/vgg16FrontEndDelay.pkl'
    with open(output_path, 'wb') as f:
        pickle.dump(delays, f)
    print(f'Done! Saved calibrated profiles directly to {output_path}')

if __name__ == '__main__':
    profile_vgg16()
