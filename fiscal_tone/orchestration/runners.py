"""
Pipeline Orchestration for FiscalTone.

This module provides high-level pipeline runners that coordinate the
execution of multiple processing stages.

Main Classes:
    PipelineRunner: Orchestrates the complete FiscalTone pipeline

Example:
    >>> from fiscal_tone.orchestration.runners import PipelineRunner
    >>> runner = PipelineRunner()
    >>> runner.run_all()  # Run complete pipeline
    >>> runner.run_stage("collect")  # Run single stage
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from timeit import default_timer as timer
from typing import Any, Callable


@dataclass
class PipelineConfig:
    """Configuration for the FiscalTone pipeline.

    Attributes:
        data_dir: Base directory for data files.
        raw_dir: Directory for raw downloaded PDFs.
        metadata_dir: Directory for metadata JSON files.
        output_dir: Directory for final outputs.
    """

    data_dir: Path = field(default_factory=lambda: Path("data"))
    raw_dir: Path = field(default_factory=lambda: Path("data/raw"))
    metadata_dir: Path = field(default_factory=lambda: Path("metadata"))
    output_dir: Path = field(default_factory=lambda: Path("data/output"))

    def __post_init__(self) -> None:
        """Convert string paths to Path objects."""
        self.data_dir = Path(self.data_dir)
        self.raw_dir = Path(self.raw_dir)
        self.metadata_dir = Path(self.metadata_dir)
        self.output_dir = Path(self.output_dir)

    def ensure_directories(self) -> None:
        """Create all required directories."""
        for path in [
            self.data_dir,
            self.raw_dir,
            self.raw_dir / "editable",
            self.raw_dir / "scanned",
            self.metadata_dir,
            self.output_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)


class PipelineRunner:
    """
    Orchestrates the FiscalTone data processing pipeline.

    The pipeline consists of the following stages:
        1. collect: Web scraping and PDF download from cf.gob.pe
        2. classify: PDF classification (editable vs scanned) and metadata enrichment
        3. extract: Text extraction from PDFs
        4. clean: Text cleaning and normalization
        5. analyze: LLM-based fiscal tone classification (not yet implemented)

    Example:
        >>> runner = PipelineRunner()
        >>> runner.run_all()  # Run all stages
        >>> runner.run_stage("collect")  # Run single stage
        >>> runner.run_stages(["collect", "classify"])  # Run multiple stages
    """

    STAGES = ["collect", "classify", "extract", "clean", "analyze"]

    def __init__(self, config: PipelineConfig | None = None) -> None:
        """
        Initialize the pipeline runner.

        Args:
            config: Pipeline configuration. If None, uses default config.
        """
        self.config = config or PipelineConfig()
        self.config.ensure_directories()
        self._results: dict[str, Any] = {}

    def run_all(self) -> dict[str, Any]:
        """
        Run the complete pipeline from collection to analysis.

        Returns:
            Dictionary with results from each stage.
        """
        print("=" * 70)
        print("FISCALTONE PIPELINE - FULL EXECUTION")
        print("=" * 70)
        print()

        t0 = timer()

        for stage in self.STAGES:
            try:
                self.run_stage(stage)
            except Exception as e:
                print(f"\n[ERROR] Stage '{stage}' failed: {e}")
                print("Continuing with remaining stages...")

        print()
        print("=" * 70)
        print("PIPELINE COMPLETE")
        print("=" * 70)
        print(f"Total time: {timer() - t0:.2f} seconds")

        return self._results

    def run_stage(self, stage: str) -> Any:
        """
        Run a single pipeline stage.

        Args:
            stage: Name of the stage to run.
                   One of: collect, classify, extract, clean, analyze

        Returns:
            Results from the stage execution.

        Raises:
            ValueError: If stage name is invalid.
        """
        if stage not in self.STAGES:
            raise ValueError(
                f"Invalid stage: '{stage}'. Valid stages: {self.STAGES}"
            )

        print(f"\n{'='*70}")
        print(f"RUNNING STAGE: {stage.upper()}")
        print("=" * 70)

        t0 = timer()

        if stage == "collect":
            result = self._run_collection()
        elif stage == "classify":
            result = self._run_classification()
        elif stage == "extract":
            result = self._run_extraction()
        elif stage == "clean":
            result = self._run_cleaning()
        elif stage == "analyze":
            result = self._run_analysis()
        else:
            result = None

        self._results[stage] = result
        print(f"\n[DONE] Stage '{stage}' completed in {timer() - t0:.2f} seconds")

        return result

    def run_stages(self, stages: list[str]) -> dict[str, Any]:
        """
        Run multiple pipeline stages in order.

        Args:
            stages: List of stage names to run.

        Returns:
            Dictionary with results from each stage.
        """
        for stage in stages:
            self.run_stage(stage)
        return self._results

    def _run_collection(self) -> Any:
        """Execute the document collection stage."""
        from fiscal_tone.collectors.fc_collector import run_collection_stage

        return run_collection_stage(
            raw_pdf_folder=str(self.config.raw_dir),
            metadata_folder=str(self.config.metadata_dir),
        )

    def _run_classification(self) -> Any:
        """Execute the PDF classification and metadata enrichment stage."""
        from fiscal_tone.processors.pdf_classifier import run_classification_stage

        return run_classification_stage(
            raw_pdf_folder=str(self.config.raw_dir),
            metadata_folder=str(self.config.metadata_dir),
        )

    def _run_extraction(self) -> Any:
        """Execute the text extraction stage."""
        from fiscal_tone.processors.text_extractor import run_extraction_stage

        return run_extraction_stage(
            raw_pdf_folder=str(self.config.raw_dir),
            output_folder=str(self.config.raw_dir),
        )

    def _run_cleaning(self) -> Any:
        """Execute the text cleaning stage."""
        from fiscal_tone.processors.text_cleaner import run_cleaning_stage

        return run_cleaning_stage(
            input_folder=str(self.config.raw_dir),
            output_folder=str(self.config.raw_dir),
        )

    def _run_analysis(self) -> Any:
        """Execute the LLM analysis stage."""
        try:
            from fiscal_tone.analyzers.llm_classifier import run_classification_stage

            return run_classification_stage(
                input_path=str(self.config.metadata_dir / "cf_normalized_paragraphs_cleaned.json"),
                output_dir=str(self.config.output_dir),
            )
        except ImportError as e:
            print(f"[WARN] LLM dependencies not installed: {e}")
            print("       Install with: pip install openai aiolimiter tenacity tqdm")
            print("       Or use llm_with_context.py directly.")
            return None
        except Exception as e:
            print(f"[ERROR] LLM analysis failed: {e}")
            return None

    def get_status(self) -> dict[str, str]:
        """
        Get the status of each pipeline stage.

        Returns:
            Dictionary mapping stage names to status (completed/pending).
        """
        status = {}
        for stage in self.STAGES:
            if stage in self._results:
                status[stage] = "completed"
            else:
                status[stage] = "pending"
        return status


def main() -> None:
    """CLI entry point for the pipeline runner."""
    import argparse

    parser = argparse.ArgumentParser(
        description="FiscalTone Pipeline Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m fiscal_tone.orchestration.runners --all
  python -m fiscal_tone.orchestration.runners --stage collect
  python -m fiscal_tone.orchestration.runners --stages collect classify extract
        """,
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run the complete pipeline",
    )
    parser.add_argument(
        "--stage",
        "-s",
        choices=PipelineRunner.STAGES,
        help="Run a single stage",
    )
    parser.add_argument(
        "--stages",
        nargs="+",
        choices=PipelineRunner.STAGES,
        help="Run multiple stages in order",
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Base data directory (default: data)",
    )
    parser.add_argument(
        "--metadata-dir",
        default="metadata",
        help="Metadata directory (default: metadata)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available stages",
    )

    args = parser.parse_args()

    if args.list:
        print("Available pipeline stages:")
        for i, stage in enumerate(PipelineRunner.STAGES, 1):
            print(f"  {i}. {stage}")
        return

    # Create config
    config = PipelineConfig(
        data_dir=Path(args.data_dir),
        raw_dir=Path(args.data_dir) / "raw",
        metadata_dir=Path(args.metadata_dir),
        output_dir=Path(args.data_dir) / "output",
    )

    runner = PipelineRunner(config)

    if args.all:
        runner.run_all()
    elif args.stage:
        runner.run_stage(args.stage)
    elif args.stages:
        runner.run_stages(args.stages)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
