uv sync
gcc example/demo.c -o example/demo
uv run python main.py --path ./example/demo --prompt "solve this crackme"
