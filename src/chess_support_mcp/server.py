from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import chess
from mcp.server.fastmcp import FastMCP


@dataclass
class GameState:
    """Holds a single in-memory chess game state."""

    board: chess.Board
    san_history: List[str]

    @classmethod
    def new(cls) -> "GameState":
        return cls(board=chess.Board(), san_history=[])

    def reset(self) -> None:
        self.board.reset()
        self.san_history.clear()

    def add_move_uci(self, uci: str) -> Dict[str, Any]:
        try:
            move = chess.Move.from_uci(uci)
        except Exception as exc:  # noqa: BLE001
            return {
                "accepted": False,
                "reason": "parse_error",
                "parse_error": str(exc),
            }
        if move not in self.board.legal_moves:
            return {
                "accepted": False,
                "reason": "illegal",
                "expected_turn": "white" if self.board.turn else "black",
            }
        san = self.board.san(move)
        self.board.push(move)
        self.san_history.append(san)
        return {"accepted": True}

    def is_move_legal(self, uci: str) -> Dict[str, Any]:
        try:
            move = chess.Move.from_uci(uci)
        except Exception as exc:  # noqa: BLE001
            return {"parse_error": str(exc), "legal": False}
        return {"legal": move in self.board.legal_moves}

    def all_moves(self) -> List[str]:
        return [m.uci() for m in self.board.move_stack]

    def all_moves_detailed(self) -> List[Dict[str, Any]]:
        details: List[Dict[str, Any]] = []
        for idx, move in enumerate(self.board.move_stack):
            details.append({
                "ply": idx + 1,
                "uci": move.uci(),
                "san": self.san_history[idx] if idx < len(self.san_history) else None,
                "side": "white" if idx % 2 == 0 else "black",
            })
        return details

    def last_n_moves(self, n: int) -> List[str]:
        if n <= 0:
            return []
        return [m.uci() for m in self.board.move_stack[-n:]]

    def last_n_moves_detailed(self, n: int) -> List[Dict[str, Any]]:
        if n <= 0:
            return []
        start = max(0, len(self.board.move_stack) - n)
        result: List[Dict[str, Any]] = []
        for idx in range(start, len(self.board.move_stack)):
            move = self.board.move_stack[idx]
            result.append({
                "ply": idx + 1,
                "uci": move.uci(),
                "san": self.san_history[idx] if idx < len(self.san_history) else None,
                "side": "white" if idx % 2 == 0 else "black",
            })
        return result

    def ascii_board(self) -> str:
        return str(self.board)

    def pieces_map(self) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for square, piece in self.board.piece_map().items():
            mapping[chess.square_name(square)] = piece.symbol()
        return mapping

    def status(self) -> Dict[str, Any]:
        fen = self.board.fen()
        parts = fen.split()
        last_move_uci = self.board.move_stack[-1].uci() if self.board.move_stack else None
        last_move_san = self.san_history[-1] if self.san_history else None
        return {
            "fen": fen,
            "side_to_move": "white" if self.board.turn else "black",
            "fullmove_number": self.board.fullmove_number,
            "halfmove_clock": self.board.halfmove_clock,
            "ply_count": len(self.board.move_stack),
            "castling_rights": parts[2] if len(parts) >= 3 else None,
            "en_passant_square": parts[3] if len(parts) >= 4 else None,
            "last_move_uci": last_move_uci,
            "last_move_san": last_move_san,
            "who_moved_last": ("white" if (len(self.board.move_stack) - 1) % 2 == 0 else "black") if self.board.move_stack else None,
            "is_check": self.board.is_check(),
            "is_game_over": self.board.is_game_over(),
            "result": self.board.result(claim_draw=True) if self.board.is_game_over() else None,
            "pieces": self.pieces_map(),
        }


server = FastMCP(
    "chess-support-mcp",
    "MCP server that manages a single chess game: create/reset, add move, list moves, last N moves, ASCII board, move legality, and status.",
)

_GAME = GameState.new()


@server.tool()
def create_or_reset_game() -> Dict[str, Any]:
    """Create a new game or reset the current one to the initial position.

    Returns (in result):
    - ok: boolean
    - status: object with the current position metadata:
      - fen: string (Forsyth–Edwards Notation)
      - side_to_move: "white" | "black"
      - fullmove_number: int
      - halfmove_clock: int
      - ply_count: int (number of half-moves made)
      - castling_rights: string like "KQkq" or "-"
      - en_passant_square: algebraic square like "e3" or "-"
      - last_move_uci: string | null
      - last_move_san: string | null
      - who_moved_last: "white" | "black" | null
      - is_check: boolean
      - is_game_over: boolean
      - result: string like "1-0", "0-1", "1/2-1/2" or null
      - pieces: object mapping squares to piece symbols, e.g. {"e4":"P", "e5":"p"}
    - moves: array of UCI strings for all moves played so far (empty after reset)
    - moves_detailed: array of { ply:int, side:"white"|"black", uci:string, san:string }

    Notes:
    - This tool does not suggest moves; it only manages state.
    """

    _GAME.reset()
    return {
        "ok": True,
        "status": _GAME.status(),
        "moves": _GAME.all_moves(),
        "moves_detailed": [
            _format_move_detail(idx, move, _GAME.san_history)
            for idx, move in enumerate(_GAME.board.move_stack)
        ],
    }


@server.tool()
def get_status() -> Dict[str, Any]:
    """Get current position metadata for model-friendly planning.

    Returns (in result):
    - fen, side_to_move, fullmove_number, halfmove_clock, ply_count
    - castling_rights, en_passant_square
    - last_move_uci, last_move_san, who_moved_last
    - is_check, is_game_over, result
    - pieces: square-to-piece map (e.g., {"a2":"P", "e1":"K"})
    """

    return _GAME.status()


@server.tool()
def add_move(uci: str) -> Dict[str, Any]:
    """Apply a move in UCI format if legal.

    Parameters:
    - uci: string like "e2e4", "g1f3", promotions like "e7e8q".

    Returns (in result):
    - On success: { accepted:true, status: Status, moves:[...], moves_detailed:[...] }
      where Status is the same shape returned by get_status(), including last_move_{uci,san}.
    - On failure: { accepted:false, reason:"illegal", expected_turn:"white"|"black", status: Status }

    Notes:
    - This tool validates legality only; it does not suggest or score moves.
    """

    move_outcome = _GAME.add_move_uci(uci)
    response: Dict[str, Any] = {"accepted": bool(move_outcome.get("accepted"))}
    response["status"] = _GAME.status()
    if not response["accepted"]:
        if "reason" in move_outcome:
            response["reason"] = move_outcome["reason"]
        if "expected_turn" in move_outcome:
            response["expected_turn"] = move_outcome["expected_turn"]
        return response

    response["moves"] = _GAME.all_moves()
    response["moves_detailed"] = _GAME.all_moves_detailed()
    return response


@server.tool()
def is_legal(uci: str) -> Dict[str, Any]:
    """Check if a UCI move is legal in the current position.

    Returns (in result):
    - { legal:boolean }.
    - If the UCI string cannot be parsed, { parse_error:string, legal:false }.
    """

    return _GAME.is_move_legal(uci)


@server.tool()
def list_moves() -> List[str]:
    """Return all moves played so far in UCI, ordered from the start of the game."""

    return _GAME.all_moves()


def _format_move_detail(idx: int, move: chess.Move, san_history: List[str]) -> Dict[str, Any]:
    return {
        "ply": idx + 1,
        "uci": move.uci(),
        "san": san_history[idx] if idx < len(san_history) else None,
        "side": "white" if idx % 2 == 0 else "black",
    }


@server.tool()
def list_moves_detailed() -> List[Dict[str, Any]]:
    """Return detailed move history.

    Each item: { ply:int, side:"white"|"black", uci:string, san:string }
    """

    return [
        _format_move_detail(idx, move, _GAME.san_history)
        for idx, move in enumerate(_GAME.board.move_stack)
    ]


@server.tool()
def last_moves(n: int = 1) -> List[str]:
    """Return the last N moves in UCI (default 1).

    Parameters:
    - n: integer >= 1. If n <= 0, returns an empty list.
    """

    return _GAME.last_n_moves(n)


@server.tool()
def last_moves_detailed(n: int = 1) -> List[Dict[str, Any]]:
    """Return the last N moves with details (default 1).

    Each item: { ply:int, side:"white"|"black", uci:string, san:string }.
    Parameters:
    - n: integer >= 1. If n <= 0, returns an empty list.
    """

    if n <= 0:
        return []
    start = max(0, len(_GAME.board.move_stack) - n)
    return [
        _format_move_detail(idx, _GAME.board.move_stack[idx], _GAME.san_history)
        for idx in range(start, len(_GAME.board.move_stack))
    ]


@server.tool()
def board_ascii() -> str:
    """Return an ASCII representation of the board from White's perspective.

    Notes:
    - This is a human-oriented view, suitable for displaying the board to users in UIs, logs, or chat.
    - For model reasoning, prefer the JSON map in get_status().pieces.
    """

    return _GAME.ascii_board()


 


def main() -> None:
    """Entry point: run MCP server over stdio."""

    server.run()


if __name__ == "__main__":
    main()


