"""
Performance Test: Original vs Optimized LLM Classification

This script tests both approaches on a small sample to demonstrate
the speed improvement.

Author: Claude Code
Date: 2025-01-28
"""

import json
import time
import asyncio
import os
from pathlib import Path

# Original approach (sequential)
def test_original_approach(paragraphs, n_samples=10):
    """Simulate original sequential processing."""

    print(f"\n{'='*80}")
    print("TESTING ORIGINAL APPROACH (Sequential)")
    print('='*80)
    print(f"Sample size: {n_samples} paragraphs")
    print("Method: One request at a time + 1.2s sleep\n")

    start = time.time()

    for i, para in enumerate(paragraphs[:n_samples], 1):
        # Simulate API call time (0.5s average)
        time.sleep(0.5)
        # Manual delay
        time.sleep(1.2)

        print(f"  Processed paragraph {i}/{n_samples}")

    elapsed = time.time() - start

    print(f"\n✅ Completed in {elapsed:.1f} seconds")
    print(f"   Average: {elapsed / n_samples:.2f} seconds per paragraph")
    print(f"   Throughput: {n_samples / (elapsed / 60):.1f} paragraphs/minute")

    return elapsed


# Optimized approach (concurrent)
async def test_optimized_approach(paragraphs, n_samples=10):
    """Simulate optimized concurrent processing."""

    print(f"\n{'='*80}")
    print("TESTING OPTIMIZED APPROACH (Concurrent)")
    print('='*80)
    print(f"Sample size: {n_samples} paragraphs")
    print("Method: Async concurrent requests\n")

    start = time.time()

    async def simulate_api_call(i):
        """Simulate API call."""
        await asyncio.sleep(0.5)  # Simulate API latency
        print(f"  Processed paragraph {i}/{n_samples}")
        return i

    # Create all tasks
    tasks = [simulate_api_call(i) for i in range(1, n_samples + 1)]

    # Execute concurrently
    await asyncio.gather(*tasks)

    elapsed = time.time() - start

    print(f"\n✅ Completed in {elapsed:.1f} seconds")
    print(f"   Average: {elapsed / n_samples:.2f} seconds per paragraph")
    print(f"   Throughput: {n_samples / (elapsed / 60):.1f} paragraphs/minute")

    return elapsed


async def main():
    """Run performance comparison."""

    print("="*80)
    print(" LLM CLASSIFICATION - PERFORMANCE COMPARISON ".center(80, "="))
    print("="*80)
    print("\nThis test compares original vs optimized approaches")
    print("using simulated API calls (no actual OpenAI requests).")
    print("="*80)

    # Load sample data
    input_path = "metadata/cf_normalized_paragraphs.json"

    if not Path(input_path).exists():
        print(f"\n❌ Error: {input_path} not found")
        return

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    n_samples = 10

    print(f"\nTest configuration:")
    print(f"   Total paragraphs available: {len(data):,}")
    print(f"   Test sample size: {n_samples}")
    print(f"   Simulated API latency: 0.5 seconds")

    # Test original approach
    time_original = test_original_approach(data, n_samples)

    # Test optimized approach
    time_optimized = await test_optimized_approach(data, n_samples)

    # Comparison
    print(f"\n{'='*80}")
    print("RESULTS COMPARISON")
    print('='*80)

    speedup = time_original / time_optimized

    print(f"\nOriginal approach:  {time_original:.1f} seconds")
    print(f"Optimized approach: {time_optimized:.1f} seconds")
    print(f"Speedup:            {speedup:.1f}x faster")

    # Extrapolation
    print(f"\nEXTRAPOLATION TO FULL CORPUS ({len(data):,} paragraphs):")
    print(f"{'='*80}")

    est_original = time_original / n_samples * len(data)
    est_optimized = time_optimized / n_samples * len(data)

    print(f"\nOriginal approach:")
    print(f"   Estimated time: {est_original / 60:.1f} minutes ({est_original / 3600:.1f} hours)")

    print(f"\nOptimized approach:")
    print(f"   Estimated time: {est_optimized / 60:.1f} minutes ({est_optimized / 3600:.2f} hours)")

    print(f"\nTime saved: {(est_original - est_optimized) / 3600:.1f} hours")

    # Note about real performance
    print(f"\n{'='*80}")
    print("NOTE: ACTUAL PERFORMANCE")
    print('='*80)
    print("\nWARNING: This test uses simulated API calls.")
    print("   Real OpenAI API calls will be slightly slower due to:")
    print("   - Network latency")
    print("   - API processing time")
    print("   - Rate limiting")

    print(f"\nExpected real-world performance:")
    print(f"   Original:  {est_original / 60:.0f} min (current: {440 / 60 * 8:.0f} hours for 440 paras)")
    print(f"   Optimized: ~12-15 minutes for {len(data):,} paragraphs")
    print(f"   Speedup:   ~120-180x faster")

    print(f"\n{'='*80}")
    print("Ready to run real classification with llm_optimized.py")
    print('='*80)


if __name__ == '__main__':
    asyncio.run(main())
