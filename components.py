"""
Core game logic for Minesweeper.

This module contains pure domain logic without any pygame or pixel-level
concerns. It defines:
- CellState: the state of a single cell
- Cell: a cell positioned by (col,row) with an attached CellState
- Board: grid management, mine placement, adjacency computation, reveal/flag

The Board exposes imperative methods that the presentation layer (run.py)
can call in response to user inputs, and does not know anything about
rendering, timing, or input devices.
"""

import random
from typing import List, Tuple


class CellState:
    """Mutable state of a single cell.

    Attributes:
        is_mine: Whether this cell contains a mine.
        is_revealed: Whether the cell has been revealed to the player.
        is_flagged: Whether the player flagged this cell as a mine.
        adjacent: Number of adjacent mines in the 8 neighboring cells.
    """

    def __init__(self, is_mine: bool = False, is_revealed: bool = False, is_flagged: bool = False, adjacent: int = 0):
        self.is_mine = is_mine
        self.is_revealed = is_revealed
        self.is_flagged = is_flagged
        self.adjacent = adjacent


class Cell:
    """Logical cell positioned on the board by column and row."""

    def __init__(self, col: int, row: int):
        self.col = col
        self.row = row
        self.state = CellState()


class Board:
    """Minesweeper board state and rules.

    Responsibilities:
    - Generate and place mines with first-click safety
    - Compute adjacency counts for every cell
    - Reveal cells (iterative flood fill when adjacent == 0)
    - Toggle flags, check win/lose conditions
    """

    def __init__(self, cols: int, rows: int, mines: int):
        self.cols = cols
        self.rows = rows
        self.num_mines = mines
        self.cells: List[Cell] = [Cell(c, r) for r in range(rows) for c in range(cols)]
        self._mines_placed = False
        self.revealed_count = 0
        self.game_over = False
        self.win = False

    def index(self, col: int, row: int) -> int:
        """Return the flat list index for (col,row)."""
        return row * self.cols + col

    def is_inbounds(self, col: int, row: int) -> bool:
        return 0 <= col < self.cols and 0 <= row < self.rows

    def neighbors(self, col: int, row: int) -> List[Tuple[int, int]]:
        deltas = [
            (-1, -1), (0, -1), (1, -1),
            (-1, 0),           (1, 0),
            (-1, 1),  (0, 1),  (1, 1),
        ]
        result = []
        for dc, dr in deltas:
            nc, nr = col + dc, row + dr
            if self.is_inbounds(nc, nr):
                result.append((nc, nr))
        return result

    def place_mines(self, safe_col: int, safe_row: int) -> None:
        # 금지 구역(첫 클릭 + 인접 8칸)
        forbidden = {(safe_col, safe_row)} | set(self.neighbors(safe_col, safe_row))

        all_positions = [(c, r) for r in range(self.rows) for c in range(self.cols)]
        pool = [p for p in all_positions if p not in forbidden]

        random.shuffle(pool)
        mine_positions = set(pool[: self.num_mines])

        # 지뢰 배치
        for (c, r) in mine_positions:
            idx = self.index(c, r)
            self.cells[idx].state.is_mine = True

        # adjacency 계산
        for r in range(self.rows):
            for c in range(self.cols):
                cell = self.cells[self.index(c, r)]
                if cell.state.is_mine:
                    continue
                count = 0
                for (nc, nr) in self.neighbors(c, r):
                    if self.cells[self.index(nc, nr)].state.is_mine:
                        count += 1
                cell.state.adjacent = count

        self._mines_placed = True

    def reveal(self, col: int, row: int) -> None:
        if not self.is_inbounds(col, row):
            return

        # 첫 클릭 -> 지뢰 배치
        if not self._mines_placed:
            self.place_mines(col, row)

        cell = self.cells[self.index(col, row)]

        # 이미 열렸거나 깃발이면 무시
        if cell.state.is_revealed or cell.state.is_flagged:
            return

        # 지뢰 클릭 -> 게임 오버
        if cell.state.is_mine:
            cell.state.is_revealed = True
            self.game_over = True
            self._reveal_all_mines()
            return

        # 일반 셀 오픈
        stack = [(col, row)]
        while stack:
            c, r = stack.pop()
            curr = self.cells[self.index(c, r)]
            if curr.state.is_revealed or curr.state.is_flagged:
                continue

            curr.state.is_revealed = True
            self.revealed_count += 1

            # 주변 지뢰 0 -> flood-fill 계속
            if curr.state.adjacent == 0:
                for (nc, nr) in self.neighbors(c, r):
                    ncell = self.cells[self.index(nc, nr)]
                    if not ncell.state.is_revealed and not ncell.state.is_flagged:
                        stack.append((nc, nr))

        self._check_win()

    def toggle_flag(self, col: int, row: int) -> None:
        if not self.is_inbounds(col, row):
            return

        cell = self.cells[self.index(col, row)]

        # 이미 열렸으면 무시
        if cell.state.is_revealed:
            return

        cell.state.is_flagged = not cell.state.is_flagged

    def flagged_count(self) -> int:
        return sum(1 for cell in self.cells if cell.state.is_flagged)

    def _reveal_all_mines(self) -> None:
        """Reveal all mines; called on game over."""
        for cell in self.cells:
            if cell.state.is_mine:
                cell.state.is_revealed = True

    def _check_win(self) -> None:
        """Set win=True when all non-mine cells have been revealed."""
        total_cells = self.cols * self.rows
        if self.revealed_count == total_cells - self.num_mines and not self.game_over:
            self.win = True
            for cell in self.cells:
                if not cell.state.is_revealed and not cell.state.is_mine:
                    cell.state.is_revealed = True
                    
    def hint_reveal(self) -> None:
        """Reveal a random safe unrevealed cell."""
        # 게임이 시작되지 않았거나 게임 오버/승리 상태면 무시
        if not self._mines_placed or self.game_over or self.win:
            return

        # 지뢰가 아니고 아직 공개되지 않은 칸들 찾기
        safe_unrevealed = [
            cell for cell in self.cells
            if not cell.state.is_mine and not cell.state.is_revealed and not cell.state.is_flagged
        ]

        # 공개할 칸이 없으면 무시
        if not safe_unrevealed:
            return

        # 랜덤으로 선택해서 reveal
        hint_cell = random.choice(safe_unrevealed)
        self.reveal(hint_cell.col, hint_cell.row)
