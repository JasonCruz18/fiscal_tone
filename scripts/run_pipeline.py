#!/usr/bin/env python
"""
FiscalTone Pipeline Runner - CLI Entry Point

This script provides command-line access to the FiscalTone data processing
pipeline. Run all stages or select specific stages to execute.

Usage:
    # Run the complete pipeline
    python scripts/run_pipeline.py --all

    # Run a single stage
    python scripts/run_pipeline.py --stage collect
    python scripts/run_pipeline.py --stage classify
    python scripts/run_pipeline.py --stage extract
    python scripts/run_pipeline.py --stage clean

    # Run multiple stages
    python scripts/run_pipeline.py --stages collect classify extract

    # List available stages
    python scripts/run_pipeline.py --list

Pipeline Stages:
    1. collect   - Web scraping and PDF download from cf.gob.pe
    2. classify  - PDF classification (editable vs scanned) + metadata enrichment
    3. extract   - Text extraction from PDFs (font-based and OCR)
    4. clean     - Text cleaning and normalization
    5. analyze   - LLM-based fiscal tone classification (coming soon)
"""

import argparse
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fiscal_tone.orchestration.runners import PipelineConfig, PipelineRunner


def main() -> int:
    """Main entry point for the pipeline CLI."""
    parser = argparse.ArgumentParser(
        description="FiscalTone Pipeline Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_pipeline.py --all
  python scripts/run_pipeline.py --stage collect
  python scripts/run_pipeline.py --stages collect classify extract
  python scripts/run_pipeline.py --list
        """,
    )

    # Action arguments (mutually exclusive)
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Run the complete pipeline (all stages)",
    )
    action_group.add_argument(
        "--stage",
        "-s",
        choices=PipelineRunner.STAGES,
        help="Run a single stage",
    )
    action_group.add_argument(
        "--stages",
        nargs="+",
        choices=PipelineRunner.STAGES,
        metavar="STAGE",
        help="Run multiple stages in order",
    )
    action_group.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List available stages and exit",
    )

    # Configuration arguments
    parser.add_argument(
        "--data-dir",
        "-d",
        default="data",
        help="Base data directory (default: data)",
    )
    parser.add_argument(
        "--metadata-dir",
        "-m",
        default="metadata",
        help="Metadata directory (default: metadata)",
    )

    args = parser.parse_args()

    # Handle --list
    if args.list:
        print("\nFiscalTone Pipeline Stages:")
        print("-" * 40)
        stages_info = [
            ("collect", "Web scraping and PDF download"),
            ("classify", "PDF classification + metadata enrichment"),
            ("extract", "Text extraction from PDFs"),
            ("clean", "Text cleaning and normalization"),
            ("analyze", "LLM-based fiscal tone classification"),
        ]
        for i, (name, desc) in enumerate(stages_info, 1):
            print(f"  {i}. {name:12} - {desc}")
        print()
        return 0

    # If no action specified, show help
    if not (args.all or args.stage or args.stages):
        parser.print_help()
        return 1

    # Create pipeline configuration
    config = PipelineConfig(
        data_dir=Path(args.data_dir),
        raw_dir=Path(args.data_dir) / "raw",
        metadata_dir=Path(args.metadata_dir),
        output_dir=Path(args.data_dir) / "output",
    )

    # Create and run pipeline
    runner = PipelineRunner(config)

    try:
        if args.all:
            runner.run_all()
        elif args.stage:
            runner.run_stage(args.stage)
        elif args.stages:
            runner.run_stages(args.stages)

        # Print final status
        print("\nPipeline Status:")
        print("-" * 40)
        status = runner.get_status()
        for stage, state in status.items():
            marker = "[x]" if state == "completed" else "[ ]"
            print(f"  {marker} {stage}")
        print()

        return 0

    except KeyboardInterrupt:
        print("\n\nPipeline interrupted by user.")
        return 130
    except Exception as e:
        print(f"\n[ERROR] Pipeline failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
