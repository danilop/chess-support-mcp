## Chess Support MCP Server

An MCP server that manages the state of a single chess game for LLMs/agents. It intentionally does not suggest moves. Instead, it provides tools to:

- Create/reset game
- Add a move (UCI)
- List all moves
- Get last N moves
- Machine-friendly board JSON (square-to-piece map) in `get_status()`
- Check if a move is legal
- Get status (FEN, whose turn, check, game over, result)

### Requirements

- Python 3.13+
- uv package manager

### Run via uvx directly from GitHub (no local checkout)

You can run this MCP server without cloning by using `uvx` with a Git URL. Replace placeholders with your repo info and optional tag/commit.

Generic MCP config (Inspector-style):

```json
{
  "servers": {
    "chess-support-mcp": {
      "transport": {
        "type": "stdio",
        "command": "uvx",
        "args": [
          "--from",
          "git+https://github.com/danilop/chess-support-mcp.git",
          "chess-support-mcp"
        ]
      }
    }
  }
}
```

Claude Desktop `mcpServers` example:

```json
{
  "mcpServers": {
    "chess-support-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/danilop/chess-support-mcp.git",
        "chess-support-mcp"
      ]
    }
  }
}
```

The first run may take longer while `uvx` resolves and builds the package; subsequent runs use cache.

### Configure as a local MCP server (JSON)

Use stdio with `uv run` (no hardcoded paths). Example generic JSON config:

```json
{
  "servers": {
    "chess-support-mcp": {
      "transport": {
        "type": "stdio",
        "command": "uv",
        "args": ["run", "chess-support-mcp"]
      }
    }
  }
}
```

Include a local path to your project without hardcoding a specific one by using a placeholder and setting the working directory via `cwd` (preferred), or by passing `--project`:

Option A (preferred: set working directory):

```json
{
  "servers": {
    "chess-support-mcp": {
      "transport": {
        "type": "stdio",
        "command": "uv",
        "args": ["run", "chess-support-mcp"],
        "cwd": "<ABSOLUTE_PATH_TO_PROJECT>"
      }
    }
  }
}
```

Option B (use uv's project flag):

```json
{
  "servers": {
    "chess-support-mcp": {
      "transport": {
        "type": "stdio",
        "command": "uv",
        "args": ["run", "--project", "<ABSOLUTE_PATH_TO_PROJECT>", "chess-support-mcp"]
      }
    }
  }
}
```

Claude Desktop configuration (in its JSON settings), using `mcpServers`:

```json
{
  "mcpServers": {
    "chess-support-mcp": {
      "command": "uv",
      "args": ["run", "chess-support-mcp"],
      "cwd": "<ABSOLUTE_PATH_TO_PROJECT>"
    }
  }
}
```

### Tools (Methods)

- `create_or_reset_game()` → Reset to initial position. Returns `status` (with `pieces` map), and `moves`.
- `get_status()` → Returns FEN; `side_to_move` and `turn` (white/black); `fullmove_number`; `halfmove_clock`; `ply_count`; `last_move_uci`; `last_move_san`; `who_moved_last`; check flags; `is_game_over`; and `result` when over.
- `add_move(uci: str)` → Apply a move if legal (e.g., `e2e4`, `g1f3`, promotion like `e7e8q`). Returns acceptance, `reason` for failures (including `expected_turn`); updated FEN, SAN, flags, and move history.
- `is_legal(uci: str)` → Check legality of a UCI move in the current position.
- `list_moves()` → All moves in UCI made so far.
- `list_moves_detailed()` → All moves with `ply`, `side`, `uci`, `san`.
- `last_moves(n: int=1)` → Last N moves in UCI.
- `last_moves_detailed(n: int=1)` → Last N moves with `ply`, `side`, `uci`, `san`.
- `board_ascii()` → ASCII board (optional, human-oriented). The normal API returns machine-friendly JSON in `status.pieces`.

### API design notes

- Moves are always provided in UCI (e.g., `e2e4`, `g1f3`, promotions `e7e8q`). The server infers side-to-move from position; you never specify white/black when sending a move.
- `get_status().side_to_move` tells the model whose turn it is. `who_moved_last`, `last_move_uci`, and `last_move_san` help with context.
- Detailed move lists are provided in separate `*_detailed` tools to keep the basic list simple and backwards compatible.

### Notes

- The server maintains one in-memory game.
- The server does not provide hints or best moves.
 
### Development

- Run tests:

```bash
uv run pytest -q
```

