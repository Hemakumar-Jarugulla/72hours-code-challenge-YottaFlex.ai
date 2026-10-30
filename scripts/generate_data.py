"""
CLI Script for Synthetic Data Generation.
Supports both 'starter' (fast interactive demo) and 'full' (10,000 loans, 30,000 installments) scale profiles.
Exports to SQLite, CSV, JSON, and manifest with SHA256 checksums.
"""

import os
import sys
import argparse
import time

# Add workspace to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database.db import get_db_connection, init_database
from generator.synthetic_generator import SyntheticDataGenerator
from generator.config import DEFAULT_SEED


def main():
    parser = argparse.ArgumentParser(description="Synthetic Data Generator for Fair Collections Engine")
    parser.add_argument("--profile", choices=["starter", "full"], default="starter",
                        help="Scale profile: 'starter' (500 loans) or 'full' (10,000 loans, 30,000 installments)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help=f"Random seed (default: {DEFAULT_SEED})")
    parser.add_argument("--export-dir", type=str, default=None, help="Custom export directory")
    parser.add_argument("--skip-db", action="store_true", help="Skip writing to SQLite database")
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print(f"STARTING SYNTHETIC DATA GENERATION: Profile='{args.profile}', Seed={args.seed}")
    print("=" * 70)

    start_time = time.time()
    generator = SyntheticDataGenerator(seed=args.seed, profile_name=args.profile)
    counts = generator.generate_all()

    elapsed = time.time() - start_time
    print(f"\n[OK] Generated entities in {elapsed:.2f} seconds:")
    for entity, count in counts.items():
        print(f"    - {entity:<25}: {count:>8,}")

    # Determine export directory
    base_dir = os.path.dirname(os.path.dirname(__file__))
    out_dir = args.export_dir or os.path.join(base_dir, "exports", args.profile)
    print(f"\n[+] Exporting CSVs, JSON, and Manifest to: {out_dir}")
    checksums = generator.export_to_files(out_dir)
    print(f"[OK] Export complete ({len(checksums)} files with SHA256 hashes generated).")

    # Write to SQLite
    if not args.skip_db:
        db_path = os.path.join(base_dir, "collections_engine.db")
        print(f"[+] Initializing and loading SQLite database at: {db_path}")
        init_database(db_path, drop_existing=True)
        conn = get_db_connection(db_path)
        generator.export_to_sqlite(conn)
        conn.close()
        print("[OK] SQLite database successfully loaded and indexed.")

    print("\n" + "=" * 70)
    print("DATA GENERATION COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
