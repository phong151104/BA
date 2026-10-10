import argparse
from pathlib import Path
from .common import latest_run, save_csv


def main():
    parser = argparse.ArgumentParser(description="Telecom retention reproducible pipeline")
    parser.add_argument("command", choices=["download", "prepare", "train", "evaluate", "simulate", "report", "export", "run-all", "score", "prune"])
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/upload_scores.csv"))
    parser.add_argument("--pdf", choices=["auto", "require", "skip"], default="auto", help="PDF conversion for export (needs Microsoft Word/PowerPoint)")
    parser.add_argument("--keep", type=int, default=2, help="Runs to keep for prune")
    args = parser.parse_args()
    from .data import download, prepare, parse_upload
    if args.command == "download":
        print(download())
    elif args.command == "prepare":
        print(prepare().shape)
    elif args.command == "train":
        from .modeling import train
        print(train())
    elif args.command == "evaluate":
        from .modeling import evaluate
        print(evaluate())
    elif args.command == "simulate":
        from .analysis import simulate
        print(simulate())
    elif args.command == "report":
        from .reporting import report
        print(report())
    elif args.command == "export":
        from .export import export
        print(export(pdf=args.pdf))
    elif args.command == "prune":
        from .common import prune_runs
        print("Removed:", prune_runs(args.keep))
    elif args.command == "score":
        if not args.input:
            parser.error("score requires --input")
        from .modeling import score_frame
        frame, quality = parse_upload(args.input.read_bytes())
        save_csv(score_frame(frame), args.output)
        print(args.output)
    else:
        from .modeling import train, evaluate
        from .analysis import simulate
        from .reporting import report
        from .export import export
        run = train()
        evaluate(run)
        simulate(run)
        report(run)
        print(export(run, pdf=args.pdf))
        print(f"Complete: {run}")


if __name__ == "__main__":
    main()
