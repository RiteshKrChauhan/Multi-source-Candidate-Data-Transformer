from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from pydantic import ValidationError

from config import ProjectionConfig
from pipeline import CandidatePipeline, PipelineError
from projection import ProjectionError
from utils import atomic_write_json
from validator import ValidationFailure


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="candidate-pipeline",
        description="Aggregate candidate data into deterministic canonical JSON profiles.",
    )
    parser.add_argument("--csv", action="append", default=[], metavar="PATH", help="CSV input (repeatable)")
    parser.add_argument("--resume", action="append", default=[], metavar="PATH", help="TXT/PDF resume (repeatable)")
    parser.add_argument("--ats", action="append", default=[], metavar="PATH", help="ATS JSON input (repeatable)")
    parser.add_argument("--config", metavar="PATH", help="Projection configuration JSON")
    parser.add_argument("--output", required=True, metavar="PATH", help="Output JSON path")
    parser.add_argument("--phone-region", default="US", metavar="CC", help="Region for national phone numbers (default: US)")
    parser.add_argument("--name-threshold", type=float, default=90.0, metavar="0-100", help="Fuzzy name match threshold")
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if not (args.csv or args.resume or args.ats):
        logging.error("At least one --csv, --resume, or --ats input is required")
        return 2
    try:
        config = ProjectionConfig.from_file(args.config)
        pipeline = CandidatePipeline(
            default_phone_region=args.phone_region,
            name_similarity_threshold=args.name_threshold,
        )
        output = pipeline.run(
            csv_paths=args.csv,
            resume_paths=args.resume,
            ats_paths=args.ats,
            config=config,
        )
        atomic_write_json(args.output, output)
    except (OSError, ValueError, ValidationError, PipelineError, ProjectionError, ValidationFailure) as exc:
        logging.error("Pipeline failed: %s", exc)
        return 1
    logging.info("Wrote %d candidate profiles to %s", len(output), Path(args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())

