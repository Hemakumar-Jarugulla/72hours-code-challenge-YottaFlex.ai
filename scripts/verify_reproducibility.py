"""
Reproducibility Verification Script (Step 10 Requirement).
Generates the dataset twice using identical fixed seed (20261022),
computes SHA256 checksums across all tables/files,
and proves 100% deterministic reproducibility.
"""

import os
import sys
import shutil
import tempfile
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from generator.synthetic_generator import SyntheticDataGenerator
from generator.config import DEFAULT_SEED


def verify_reproducibility(seed: int = DEFAULT_SEED, profile: str = "starter") -> bool:
    print("\n" + "=" * 80)
    print(f"STEP 10 -- DETERMINISTIC REPRODUCIBILITY VERIFICATION")
    print(f"Fixed Seed: {seed} | Scale Profile: '{profile}'")
    print("=" * 80)

    temp_dir_a = tempfile.mkdtemp(prefix="repro_run_a_")
    temp_dir_b = tempfile.mkdtemp(prefix="repro_run_b_")

    try:
        # Run 1
        print("[+] Executing Generation Run A (First Pass)...")
        gen_a = SyntheticDataGenerator(seed=seed, profile_name=profile)
        gen_a.generate_all()
        checksums_a = gen_a.export_to_files(temp_dir_a)

        # Run 2
        print("[+] Executing Generation Run B (Second Pass with same seed)...")
        gen_b = SyntheticDataGenerator(seed=seed, profile_name=profile)
        gen_b.generate_all()
        checksums_b = gen_b.export_to_files(temp_dir_b)

        print("\n" + "-" * 80)
        print(f"{'Filename / Entity':<28} | {'Run A SHA256 (prefix)':<22} | {'Run B SHA256 (prefix)':<22} | Status")
        print("-" * 80)

        all_matched = True
        for fname in sorted(checksums_a.keys()):
            hash_a = checksums_a[fname]
            hash_b = checksums_b.get(fname, "")
            is_match = (hash_a == hash_b)
            if not is_match:
                all_matched = False
            status_str = "MATCH [OK]" if is_match else "MISMATCH [FAIL]"
            print(f"{fname:<28} | {hash_a[:20]}... | {hash_b[:20]}... | {status_str}")

        print("-" * 80)
        if all_matched:
            print("REPRODUCIBILITY VERIFICATION: 100% SUCCESS")
            print("Both runs produced identical records and SHA256 checksums.")
        else:
            print("REPRODUCIBILITY VERIFICATION: FAILED")
        print("=" * 80 + "\n")
        return all_matched

    finally:
        shutil.rmtree(temp_dir_a, ignore_errors=True)
        shutil.rmtree(temp_dir_b, ignore_errors=True)


if __name__ == "__main__":
    success = verify_reproducibility()
    sys.exit(0 if success else 1)
