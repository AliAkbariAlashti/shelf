from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(prog="shelf", description="Shelf recommendation server")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the Shelf API server")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")

    sub.add_parser("seed", help="Populate the database with sample e-commerce data")

    args = parser.parse_args()

    if args.command == "serve":
        import uvicorn

        uvicorn.run("shelf.api.main:app", host=args.host, port=args.port, reload=args.reload)
    elif args.command == "seed":
        from shelf.demo.seed_demo_data import seed

        seed()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
