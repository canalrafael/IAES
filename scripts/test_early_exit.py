#!/usr/bin/env python3
"""
scripts/test_early_exit.py
=========================================
Trains and evaluates an Early-Exit Neural Network (EENN) on the 3-core PMU dataset.
Simulates confidence-based early exits to analyze computation savings vs. detection accuracy.
Saves evaluation plots and exports C-style weights in `results_early_exit/`.
Uses GPU (CUDA) acceleration when available.
"""

import os
import glob
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import recall_score, confusion_matrix, f1_score
import matplotlib.pyplot as plt
import seaborn as sns

# Config
DATA_DIR = "/home/canal/github/IAES/dataset/3 cores"
RESULTS_DIR = "results_early_exit"
os.makedirs(RESULTS_DIR, exist_ok=True)

WINDOW_SIZE = 10
FEATURES = ['IPC', 'MPKI', 'L2_PRESSURE', 'BRANCH_MISS_RATE']
FEAT_COLS = [f'{sig}_{stat}' for sig in FEATURES for stat in ['mean', 'std', 'delta']]

# Cycle estimates from detector.c
CYCLES_EXIT1 = 110
CYCLES_EXIT2 = 240

# Device selection
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# 1. Feature Engineering
def engineer_features(df):
    eps = 1e-9
    df = df.copy()
    
    # Compute base ratio signals
    df['IPC'] = df['INSTRUCTIONS'] / (df['CPU_CYCLES'] + eps)
    df['MPKI'] = (df['CACHE_MISSES'] * 1000) / (df['INSTRUCTIONS'] + eps)
    df['L2_PRESSURE'] = df['L2_CACHE_ACCESS'] / (df['CPU_CYCLES'] + eps)
    df['BRANCH_MISS_RATE'] = df['BRANCH_MISSES'] / (df['INSTRUCTIONS'] + eps)
    
    # Process rolling stats per core to avoid mixed timelines
    engineered_list = []
    cores = sorted(df['CORE_ID'].unique())
    for core in cores:
        core_df = df[df['CORE_ID'] == core].copy()
        for f in FEATURES:
            core_df[f'{f}_mean'] = core_df[f].rolling(window=WINDOW_SIZE).mean()
            core_df[f'{f}_std'] = core_df[f].rolling(window=WINDOW_SIZE).std()
            core_df[f'{f}_delta'] = core_df[f].diff(periods=WINDOW_SIZE-1)
        engineered_list.append(core_df.dropna())
        
    return pd.concat(engineered_list).sort_index()

# 2. Load Datasets
def load_all_data():
    all_files = sorted(glob.glob(os.path.join(DATA_DIR, "data_new*.csv")))
    # Exclude 20 and 21 for validation baseline parity
    files = [f for f in all_files if "20" not in f and "21" not in f]
    
    print(f"Loading and processing {len(files)} files...")
    dfs = []
    for f in files:
        df_raw = pd.read_csv(f)
        df_active = df_raw[df_raw['CPU_CYCLES'] > 100000].copy()
        if not df_active.empty:
            dfs.append(engineer_features(df_active))
            
    df_all = pd.concat(dfs, ignore_index=True)
    print(f"Loaded {len(df_all):,} samples after feature engineering.")
    return df_all

# 3. Model Definition
class EarlyExitMLP(nn.Module):
    def __init__(self, in_dim=12, h1_dim=16, h2_dim=16):
        super().__init__()
        # Layer 1
        self.layer1 = nn.Linear(in_dim, h1_dim)
        self.relu1 = nn.ReLU()
        
        # Exit 1 (Early Exit)
        self.exit1 = nn.Linear(h1_dim, 1)
        
        # Layer 2
        self.layer2 = nn.Linear(h1_dim, h2_dim)
        self.relu2 = nn.ReLU()
        
        # Exit 2 (Final Exit)
        self.exit2 = nn.Linear(h2_dim, 1)
        
    def forward(self, x):
        h1 = self.relu1(self.layer1(x))
        logit1 = self.exit1(h1)
        
        h2 = self.relu2(self.layer2(h1))
        logit2 = self.exit2(h2)
        
        return logit1, logit2

# 4. Joint Training
def train_model(model, train_loader, val_loader, epochs=150, lr=0.001):
    # pos_weight to suppress False Positives
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([0.1]).to(device))
    optimizer = optim.Adam(model.parameters(), lr=lr)
    
    best_loss = float('inf')
    best_state = None
    
    for epoch in range(epochs):
        model.train()
        running_loss = 0.0
        for inputs, labels in train_loader:
            inputs, labels = inputs.to(device), labels.to(device)
            optimizer.zero_grad()
            logit1, logit2 = model(inputs)
            
            loss_exit1 = criterion(logit1, labels)
            loss_exit2 = criterion(logit2, labels)
            
            # Joint loss with equal weights
            loss = 0.5 * loss_exit1 + 0.5 * loss_exit2
            
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * inputs.size(0)
            
        # Validation
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for inputs, labels in val_loader:
                inputs, labels = inputs.to(device), labels.to(device)
                logit1, logit2 = model(inputs)
                loss_exit1 = criterion(logit1, labels)
                loss_exit2 = criterion(logit2, labels)
                val_loss += (0.5 * loss_exit1 + 0.5 * loss_exit2).item() * inputs.size(0)
                
        epoch_loss = running_loss / len(train_loader.dataset)
        epoch_val_loss = val_loss / len(val_loader.dataset)
        
        if epoch_val_loss < best_loss:
            best_loss = epoch_val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            
        if epoch % 10 == 0 or epoch == epochs - 1:
            print(f"Epoch {epoch}/{epochs} | Train Loss: {epoch_loss:.4f} | Val Loss: {epoch_val_loss:.4f}")
            
    if best_state:
        model.load_state_dict(best_state)
    return model

# 5. Export to C Header
def export_c_header(model, scaler, path):
    # Retrieve weights back to CPU
    state = model.state_dict()
    w1 = state['layer1.weight'].cpu().numpy()
    b1 = state['layer1.bias'].cpu().numpy()
    w_exit1 = state['exit1.weight'].cpu().numpy().flatten()
    b_exit1 = state['exit1.bias'].cpu().item()
    w2 = state['layer2.weight'].cpu().numpy()
    b2 = state['layer2.bias'].cpu().numpy()
    w3 = state['exit2.weight'].cpu().numpy()
    b3 = state['exit2.bias'].cpu().numpy()
    
    with open(path, 'w') as f:
        f.write("/* EARLY EXIT NEURAL NETWORK WEIGHTS */\n")
        f.write("#ifndef MODEL_WEIGHTS_H\n#define MODEL_WEIGHTS_H\n\n")
        f.write("#define MDL_N_FEATURES 12\n#define MDL_N_H1 16\n#define MDL_N_H2 16\n#define MDL_N_OUT 1\n")
        f.write(f"#define MDL_WINDOW_SIZE {WINDOW_SIZE}\n#define MDL_TEMPERATURE 1.0f\n#define MDL_THRESHOLD 0.5f\n\n")
        
        def write_arr(name, arr):
            f.write(f"static const float {name}[{len(arr)}] = {{{', '.join([f'{x}f' for x in arr])}}};\n")
            
        write_arr("MDL_FEAT_MEAN", scaler.mean_)
        write_arr("MDL_FEAT_STD", scaler.scale_)
        
        f.write(f"\nstatic const float MDL_W1[16][12] = {{\n")
        for row in w1: f.write(f"    {{{', '.join([f'{x}f' for x in row])}}},\n")
        f.write("};\n")
        write_arr("MDL_B1", b1)
        
        f.write("\n/* Early Exit (Exit 1) Weights and Bias */\n")
        write_arr("MDL_W_EXIT1", w_exit1)
        f.write(f"static const float MDL_B_EXIT1 = {b_exit1}f;\n")
        
        f.write(f"\nstatic const float MDL_W2[16][16] = {{\n")
        for row in w2: f.write(f"    {{{', '.join([f'{x}f' for x in row])}}},\n")
        f.write("};\n")
        write_arr("MDL_B2", b2)
        
        f.write(f"\nstatic const float MDL_W3[1][16] = {{\n")
        for row in w3: f.write(f"    {{{', '.join([f'{x}f' for x in row])}}},\n")
        f.write("};\n")
        write_arr("MDL_B3", b3)
        
        f.write("\n#endif\n")
    print(f"Exported C-style weights to {path}")

def main():
    print("=" * 64)
    print(f"  Early-Exit Neural Network (EENN) PyTorch Simulation ({device.type.upper()})")
    print("=" * 64)
    
    # 1. Load Data
    df = load_all_data()
    
    # Extract features & labels
    X = df[FEAT_COLS].values.astype(np.float32)
    y = df['LABEL'].isin([1, 2, 3]).values.astype(np.float32)
    
    print(f"Class Balance: {int(y.sum()):,} Attacks ({(y.sum()/len(y))*100:.2f}%) vs {len(y) - int(y.sum()):,} Benign")
    
    # Split
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
    
    # Normalize
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_val = scaler.transform(X_val)
    
    # Loader
    train_dataset = TensorDataset(torch.FloatTensor(X_train), torch.FloatTensor(y_train).view(-1, 1))
    val_dataset = TensorDataset(torch.FloatTensor(X_val), torch.FloatTensor(y_val).view(-1, 1))
    
    train_loader = DataLoader(train_dataset, batch_size=4096, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=4096, shuffle=False)
    
    # Train
    model = EarlyExitMLP().to(device)
    model = train_model(model, train_loader, val_loader, epochs=120)
    
    # Export weights
    export_c_header(model, scaler, os.path.join(RESULTS_DIR, "model_weights_eenn.h"))
    
    # 6. Evaluation Sweep
    print("\nSweeping Confidence Thresholds...")
    model.eval()
    with torch.no_grad():
        inputs = torch.FloatTensor(X_val).to(device)
        logit1, logit2 = model(inputs)
        
        p_exit1 = torch.sigmoid(logit1).cpu()
        p_exit2 = torch.sigmoid(logit2).cpu()
        
    thresholds = np.linspace(0.0, 1.0, 51)
    recalls = []
    fprs = []
    f1s = []
    early_exit_ratios = []
    avg_cycles = []
    
    # Target decision boundary for the chosen prediction
    DECISION_BOUND = 0.5
    
    for theta in thresholds:
        # Confidence is 2 * |p - 0.5|, ranges [0, 1]
        confidence = 2.0 * torch.abs(p_exit1 - DECISION_BOUND)
        
        # Decide if we exit early
        exit_early_mask = confidence >= theta
        
        # Assemble final prediction probabilities and exit paths
        pred_p = torch.where(exit_early_mask, p_exit1, p_exit2)
        preds = (pred_p >= DECISION_BOUND).float().numpy()
        
        # Compute metrics
        rec = recall_score(y_val, preds, zero_division=0)
        
        cm = confusion_matrix(y_val, preds)
        tn, fp, fn, tp = cm.ravel()
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        
        f1 = f1_score(y_val, preds, zero_division=0)
        
        early_exit_ratio = exit_early_mask.float().mean().item()
        
        cycles = torch.where(exit_early_mask, float(CYCLES_EXIT1), float(CYCLES_EXIT2))
        avg_cyc = cycles.mean().item()
        
        recalls.append(rec)
        fprs.append(fpr)
        f1s.append(f1)
        early_exit_ratios.append(early_exit_ratio)
        avg_cycles.append(avg_cyc)
        
    # Print a summary table
    print("\nSweep Summary:")
    print(f"{'Threshold (theta)':<18} | {'Recall':<8} | {'FPR':<8} | {'F1':<8} | {'Early Exit %':<12} | {'Avg Cycles':<10}")
    print("-" * 75)
    for idx in [0, 10, 20, 25, 30, 40, 50]: # Show representative samples
        print(f"{thresholds[idx]:<18.2f} | {recalls[idx]:<8.4f} | {fprs[idx]:<8.4f} | {f1s[idx]:<8.4f} | {early_exit_ratios[idx]*100:<11.1f}% | {avg_cycles[idx]:<10.1f}")
        
    # 7. Visualization
    sns.set_theme(style='whitegrid')
    plt.rcParams.update({'font.size': 11})
    
    # Plot 1: Trade-off Curves
    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax2 = ax1.twinx()
    
    line1, = ax1.plot(thresholds, recalls, color='steelblue', lw=2.5, label='Recall (TPR)')
    line2, = ax1.plot(thresholds, fprs, color='crimson', lw=2.5, label='False Positive Rate (FPR)')
    line3, = ax2.plot(thresholds, np.array(early_exit_ratios) * 100, color='forestgreen', lw=2.2, ls='--', label='Early Exit Ratio (%)')
    
    ax1.set_xlabel('Confidence Threshold (theta)', fontsize=12)
    ax1.set_ylabel('Performance Metrics', fontsize=12)
    ax2.set_ylabel('Early Exit Ratio (%)', color='forestgreen', fontsize=12)
    
    # Target annotations
    ax1.axhline(0.99, color='steelblue', ls=':', alpha=0.5)
    ax1.axhline(0.01, color='crimson', ls=':', alpha=0.5)
    
    lines = [line1, line2, line3]
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='lower left')
    
    plt.title('EENN Confidence Threshold Sweep (TPR / FPR vs. Early Exit Ratio)', fontsize=13)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, 'eenn_tradeoffs.png'), dpi=150)
    plt.close()
    
    # Plot 2: CPU Cycles Saved vs Threshold
    plt.figure(figsize=(9, 5.5))
    plt.plot(thresholds, avg_cycles, color='purple', lw=3, label='Estimated CPU Cycles')
    plt.axhline(CYCLES_EXIT2, color='black', ls=':', label='Baseline MLP (No Early Exit)')
    plt.xlabel('Confidence Threshold (theta)', fontsize=12)
    plt.ylabel('Average Cycles Per Sample', fontsize=12)
    plt.title('EENN CPU Inference Cost vs. Confidence Threshold', fontsize=13)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, 'eenn_computation_savings.png'), dpi=150)
    plt.close()
    
    # Plot 3: Pareto curve of Recall vs CPU Cycles
    plt.figure(figsize=(9, 5.5))
    plt.scatter(avg_cycles, recalls, c=thresholds, cmap='viridis', s=60, edgecolor='black', zorder=3)
    plt.colorbar(label='Threshold (theta)')
    plt.plot(avg_cycles, recalls, color='grey', alpha=0.5, ls='-')
    plt.xlabel('Estimated Avg Cycles Per Inference (Computational Cost)', fontsize=12)
    plt.ylabel('Recall (Detection Rate)', fontsize=12)
    plt.title('EENN Pareto Frontier: Recall vs. Computational Cost', fontsize=13)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, 'eenn_pareto_recall_cycles.png'), dpi=150)
    plt.close()
    
    print(f"\nAll plots and weight files saved to '{RESULTS_DIR}/' directory.")
    print("Done!")

if __name__ == "__main__":
    main()
