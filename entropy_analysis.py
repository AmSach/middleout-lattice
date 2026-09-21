"""
Analyzes the marginal and conditional byte entropies of real model weights
to determine if cross-plane correlation can be exploited for higher lossless compression.
"""
import numpy as np
import torch
import torch.nn as nn
from collections import Counter
import math

def get_real_weights():
    model = nn.Sequential(
        nn.Linear(512, 512),
        nn.ReLU(),
        nn.Linear(512, 512)
    )
    weights = []
    for p in model.parameters():
        weights.append(p.detach().cpu().numpy().flatten().astype(np.float32))
    return np.concatenate(weights)

def entropy(data):
    counts = Counter(data)
    total = len(data)
    ent = 0.0
    for c in counts.values():
        p = c / total
        ent -= p * math.log2(p)
    return ent

def conditional_entropy(target, context):
    # H(Y|X) = sum_x p(x) H(Y|X=x)
    total = len(target)
    # Group target by context
    grouped = {}
    for t, c in zip(target, context):
        if c not in grouped:
            grouped[c] = []
        grouped[c].append(t)
        
    cond_ent = 0.0
    for c, vals in grouped.items():
        p_c = len(vals) / total
        cond_ent += p_c * entropy(vals)
    return cond_ent

def main():
    weights = get_real_weights()
    n = len(weights)
    
    # Reinterpret as bytes
    raw_bytes = weights.tobytes()
    # Reshape to (N, 4) where each row is a float: [b0, b1, b2, b3] (little endian)
    float_bytes = np.frombuffer(raw_bytes, dtype=np.uint8).reshape(-1, 4)
    
    b0 = float_bytes[:, 0]
    b1 = float_bytes[:, 1]
    b2 = float_bytes[:, 2]
    b3 = float_bytes[:, 3]
    
    print(f"Total weights: {n:,}")
    print("-" * 50)
    
    # Marginal entropies
    h_b3 = entropy(b3)
    h_b2 = entropy(b2)
    h_b1 = entropy(b1)
    h_b0 = entropy(b0)
    
    print(f"Marginal Entropies (bits per byte):")
    print(f"  H(b3) [exponent/sign]     : {h_b3:.4f} bits")
    print(f"  H(b2) [upper mantissa]    : {h_b2:.4f} bits")
    print(f"  H(b1) [mid mantissa]      : {h_b1:.4f} bits")
    print(f"  H(b0) [lower mantissa]    : {h_b0:.4f} bits")
    print(f"  Total Uncorrelated Ent   : {h_b3 + h_b2 + h_b1 + h_b0:.4f} bits (Max Ratio = {32 / (h_b3 + h_b2 + h_b1 + h_b0):.3f}x)")
    print("-" * 50)
    
    # Conditional entropies
    # Context for b2 is b3
    h_b2_given_b3 = conditional_entropy(b2, b3)
    
    # Context for b1 is (b3, b2)
    context_b1 = [tuple(x) for x in float_bytes[:, 2:4]]
    h_b1_given_b3_b2 = conditional_entropy(b1, context_b1)
    
    # Context for b0 is (b3, b2, b1)
    context_b0 = [tuple(x) for x in float_bytes[:, 1:4]]
    h_b0_given_b3_b2_b1 = conditional_entropy(b0, context_b0)
    
    total_cond_ent = h_b3 + h_b2_given_b3 + h_b1_given_b3_b2 + h_b0_given_b3_b2_b1
    
    print(f"Conditional Entropies (exploiting cross-plane context):")
    print(f"  H(b3)                     : {h_b3:.4f} bits")
    print(f"  H(b2 | b3)                : {h_b2_given_b3:.4f} bits")
    print(f"  H(b1 | b3, b2)            : {h_b1_given_b3_b2:.4f} bits")
    print(f"  H(b0 | b3, b2, b1)        : {h_b0_given_b3_b2_b1:.4f} bits")
    print(f"  Total Conditional Ent     : {total_cond_ent:.4f} bits (Max Ratio = {32 / total_cond_ent:.3f}x)")
    print("-" * 50)
    print(f"Unique Contexts (out of {n:,} elements):")
    print(f"  b2 contexts (b3)          : {len(set(b3))}")
    print(f"  b1 contexts (b3, b2)      : {len(set(context_b1))}")
    print(f"  b0 contexts (b3, b2, b1)  : {len(set(context_b0))}")
    print("-" * 50)
    print(f"Theoretical Gain from Context Mixing: {((h_b3 + h_b2 + h_b1 + h_b0) - total_cond_ent) / 8 * 100:.2f}% size reduction")

if __name__ == "__main__":
    main()
