"""Start AI4Brain: python run.py, then open http://127.0.0.1:5000"""

import argparse

from ai4brain.server import create_app


def main():
    parser = argparse.ArgumentParser(description="Run the AI4Brain cognitive growth agent")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--db", default=None, help="SQLite path (default: data/ai4brain.db)")
    args = parser.parse_args()
    app = create_app(args.db)
    print(f"AI4Brain is running at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, threaded=True, debug=False)


if __name__ == "__main__":
    main()
