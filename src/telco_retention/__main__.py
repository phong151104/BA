import argparse
from pathlib import Path
from .common import latest_run, save_csv


def main():
    parser = argparse.ArgumentParser(description="Telecom retention reproducible pipeline")
    parser.add_argument("command", choices=["download", "prepare", "train", "evaluate", "simulate", "report", "run-all", "score"])
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/upload_scores.csv"))
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
        run = train()
        evaluate(run)
        simulate(run)
        report(run)
        print(f"Complete: {run}")


if __name__ == "__main__":
    main()
