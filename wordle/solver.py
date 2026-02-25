#!/usr/bin/env python3
"""
solver.py — Claude-powered solver for NYT Wordle

Usage (after pip install -e .):
    wordle-solver                     # solve today's puzzle
    wordle-solver --date 2026-01-15   # solve a specific date's puzzle
    wordle-solver --hard              # hard mode (must reuse revealed hints)

Or run as module:
    python -m wordle.solver
    python -m wordle.solver --date 2026-01-15
"""

import argparse
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
# Load .env from project root (parent of wordle/)
_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / ".env")
load_dotenv()

import anthropic
import requests
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

WORDLE_API_URL = "https://www.nytimes.com/svc/wordle/v2/{date}.json"
CLAUDE_MODEL = "claude-sonnet-4-6"
MAX_GUESSES = 6
WORD_LENGTH = 5

# Emoji for share grid
EMOJI_GREEN = "🟩"
EMOJI_YELLOW = "🟨"
EMOJI_GRAY = "⬛"

# Rich color mapping
COLOR_GREEN = "bold white on green"
COLOR_YELLOW = "bold white on yellow"
COLOR_GRAY = "bold white on bright_black"

console = Console()

# ─────────────────────────────────────────────────────────────────────────────
# Wordle API
# ─────────────────────────────────────────────────────────────────────────────

def fetch_puzzle(date_str: str) -> dict:
    """Fetch puzzle from NYT Wordle API. Returns dict with 'solution', 'id', etc."""
    url = WORDLE_API_URL.format(date=date_str)
    resp = requests.get(url, timeout=10)
    if resp.status_code == 404:
        console.print(f"[red]No puzzle found for date {date_str}[/red]")
        sys.exit(1)
    resp.raise_for_status()
    return resp.json()


def get_today_date_str() -> str:
    """Get today's date as YYYY-MM-DD string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

# ─────────────────────────────────────────────────────────────────────────────
# Feedback evaluation
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_guess(guess: str, answer: str) -> list[str]:
    """
    Evaluate a Wordle guess against the answer.
    Returns list of 5 feedback values: 'green', 'yellow', or 'gray'.

    Algorithm (handles duplicate letters correctly):
    1. First pass: mark exact matches as green
    2. Second pass: for non-green letters, check if they exist
       in unmatched answer positions → yellow, else gray
    """
    feedback = ["gray"] * WORD_LENGTH
    answer_chars = list(answer)
    guess_chars = list(guess)

    # First pass: greens
    for i in range(WORD_LENGTH):
        if guess_chars[i] == answer_chars[i]:
            feedback[i] = "green"
            answer_chars[i] = None  # consumed

    # Second pass: yellows
    for i in range(WORD_LENGTH):
        if feedback[i] == "green":
            continue
        if guess_chars[i] in answer_chars:
            idx = answer_chars.index(guess_chars[i])
            feedback[i] = "yellow"
            answer_chars[idx] = None  # consumed

    return feedback

# ─────────────────────────────────────────────────────────────────────────────
# Display helpers
# ─────────────────────────────────────────────────────────────────────────────

def format_guess_rich(guess: str, feedback: list[str]) -> Text:
    """Format a guess with colored letter tiles for Rich display."""
    text = Text()
    for i, (letter, fb) in enumerate(zip(guess.upper(), feedback)):
        style = {"green": COLOR_GREEN, "yellow": COLOR_YELLOW, "gray": COLOR_GRAY}[fb]
        text.append(f" {letter} ", style=style)
        if i < WORD_LENGTH - 1:
            text.append(" ")
    return text


def format_guess_emoji(feedback: list[str]) -> str:
    """Format feedback as emoji row for share grid."""
    mapping = {"green": EMOJI_GREEN, "yellow": EMOJI_YELLOW, "gray": EMOJI_GRAY}
    return "".join(mapping[fb] for fb in feedback)


def build_board(guesses: list[tuple[str, list[str]]], puzzle_id: int | None,
                status: str = "Playing...") -> Panel:
    """Build the full Wordle board as a Rich Panel."""
    table = Table(
        show_header=False,
        show_edge=False,
        box=None,
        padding=(0, 1),
    )

    # Add guess rows
    for guess, feedback in guesses:
        text = format_guess_rich(guess, feedback)
        table.add_row(text)

    # Empty rows for remaining guesses
    for _ in range(MAX_GUESSES - len(guesses)):
        empty = Text()
        for i in range(WORD_LENGTH):
            empty.append(" _ ", "dim")
            if i < WORD_LENGTH - 1:
                empty.append(" ")
        table.add_row(empty)

    # Keyboard state
    keyboard_text = build_keyboard(guesses)

    title = f"🟩 Wordle #{puzzle_id}" if puzzle_id else "🟩 Wordle"
    subtitle = f"Guess {len(guesses)}/{MAX_GUESSES} — {status}"

    from rich.console import Group
    content = Group(table, Text(""), keyboard_text)

    return Panel(
        content,
        title=title,
        subtitle=subtitle,
        border_style="bright_green" if status == "SOLVED!" else "bright_blue",
        padding=(1, 3),
    )


def build_keyboard(guesses: list[tuple[str, list[str]]]) -> Text:
    """Build a mini keyboard showing letter states."""
    letter_states: dict[str, str] = {}

    for guess, feedback in guesses:
        for letter, fb in zip(guess, feedback):
            current = letter_states.get(letter)
            # Green > Yellow > Gray (don't downgrade)
            if current == "green":
                continue
            if current == "yellow" and fb != "green":
                continue
            letter_states[letter] = fb

    rows = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
    text = Text()
    for row_idx, row in enumerate(rows):
        if row_idx > 0:
            text.append("\n")
        text.append(" " * row_idx)  # indent for keyboard shape
        for letter in row:
            state = letter_states.get(letter)
            if state == "green":
                text.append(f" {letter.upper()} ", COLOR_GREEN)
            elif state == "yellow":
                text.append(f" {letter.upper()} ", COLOR_YELLOW)
            elif state == "gray":
                text.append(f" {letter.upper()} ", COLOR_GRAY)
            else:
                text.append(f" {letter.upper()} ", "dim")
    return text

# ─────────────────────────────────────────────────────────────────────────────
# Constraint tracker (for Claude's prompt)
# ─────────────────────────────────────────────────────────────────────────────

def build_constraints(guesses: list[tuple[str, list[str]]]) -> str:
    """Build a structured constraint summary from all guesses so far."""
    green_positions: dict[int, str] = {}
    yellow_letters: dict[str, set[int]] = {}  # letter -> positions where it's NOT
    gray_letters: set[str] = set()
    confirmed_letters: set[str] = set()  # letters known to be in the word

    for guess, feedback in guesses:
        for i, (letter, fb) in enumerate(zip(guess, feedback)):
            if fb == "green":
                green_positions[i] = letter
                confirmed_letters.add(letter)
            elif fb == "yellow":
                if letter not in yellow_letters:
                    yellow_letters[letter] = set()
                yellow_letters[letter].add(i)
                confirmed_letters.add(letter)
            elif fb == "gray":
                # Only mark truly absent if not confirmed elsewhere
                if letter not in confirmed_letters:
                    gray_letters.add(letter)

    # Remove gray letters that we later found are actually in the word
    gray_letters -= confirmed_letters

    lines = []
    # Green
    pattern = ["_"] * WORD_LENGTH
    for pos, letter in green_positions.items():
        pattern[pos] = letter.upper()
    lines.append(f"Pattern: {' '.join(pattern)}")

    # Yellow
    if yellow_letters:
        yellow_parts = []
        for letter, positions in sorted(yellow_letters.items()):
            pos_str = ",".join(str(p + 1) for p in sorted(positions))
            yellow_parts.append(f"{letter.upper()} (not position {pos_str})")
        lines.append(f"In word but wrong position: {'; '.join(yellow_parts)}")

    # Gray
    if gray_letters:
        lines.append(f"Not in word: {' '.join(sorted(l.upper() for l in gray_letters))}")

    return "\n".join(lines)

# ─────────────────────────────────────────────────────────────────────────────
# Claude integration
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an expert Wordle solver. You are playing Wordle — a game where you guess \
a 5-letter English word in up to 6 attempts.

After each guess, you receive feedback for each letter:
- GREEN (🟩): correct letter in the correct position
- YELLOW (🟨): correct letter but wrong position
- GRAY (⬛): letter is not in the word

RULES:
1. Every guess MUST be exactly 5 letters — a common, real English word.
2. Use ALL constraints from previous feedback. Never guess a word that contradicts known info.
3. Never repeat a previous guess.
4. Prefer common, everyday words over obscure ones.
5. Think about letter frequency: common letters are E, A, R, O, T, L, I, S, N.
6. For your first guess, use a word with diverse common letters (e.g., SLATE, CRANE, TRACE).

STRATEGY:
- Early guesses: maximize information by using diverse letters
- Mid guesses: use known greens/yellows to narrow candidates
- Late guesses: commit to the most likely word given all constraints

Respond with ONLY the 5-letter word, nothing else. No explanations, no punctuation.\
"""

HARD_MODE_ADDENDUM = """
HARD MODE is active:
- Any GREEN letter must stay in its exact position in all future guesses.
- Any YELLOW letter must appear somewhere in all future guesses.
- You MUST use all revealed information in every guess.\
"""


def ask_claude(client: anthropic.Anthropic, messages: list[dict],
               hard_mode: bool = False) -> str:
    """Ask Claude for the next Wordle guess."""
    system = SYSTEM_PROMPT
    if hard_mode:
        system += "\n\n" + HARD_MODE_ADDENDUM

    backoff = 1.0
    for attempt in range(5):
        try:
            resp = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=20,
                system=system,
                messages=messages,
            )
            text = resp.content[0].text.strip().lower()
            # Extract just the 5-letter word (Claude sometimes adds fluff)
            match = re.search(r"\b([a-z]{5})\b", text)
            if match:
                return match.group(1)
            return text[:5]  # fallback: take first 5 chars

        except anthropic.RateLimitError:
            wait = backoff + (time.time() % 1)
            console.print(f"[yellow]Rate limited, waiting {wait:.1f}s...[/yellow]")
            time.sleep(wait)
            backoff *= 2
        except anthropic.AuthenticationError:
            console.print("[red]Invalid API key. Check your .env file.[/red]")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]Claude API error: {e}[/red]")
            if attempt < 4:
                time.sleep(backoff)
                backoff *= 2
            else:
                raise

    console.print("[red]Failed to get response from Claude after retries.[/red]")
    sys.exit(1)


def build_feedback_message(guess: str, feedback: list[str], guess_num: int,
                           guesses: list[tuple[str, list[str]]]) -> str:
    """Build the feedback message to send to Claude after a guess."""
    # Visual feedback
    emoji_map = {"green": "🟩", "yellow": "🟨", "gray": "⬛"}
    tiles = " ".join(f"{emoji_map[fb]} {letter.upper()}" for letter, fb in zip(guess, feedback))

    msg = f"Guess {guess_num}/{MAX_GUESSES}: {guess.upper()}\n{tiles}\n\n"
    msg += build_constraints(guesses)
    msg += "\n\nWhat is your next guess?"

    return msg

# ─────────────────────────────────────────────────────────────────────────────
# Main solve loop
# ─────────────────────────────────────────────────────────────────────────────

def solve(date_str: str, api_key: str, hard_mode: bool = False):
    """Run the Wordle solver for a given date."""
    # Fetch puzzle
    console.print(f"[cyan]Fetching Wordle puzzle for {date_str}...[/cyan]")
    puzzle = fetch_puzzle(date_str)
    answer = puzzle["solution"].lower()
    puzzle_id = puzzle.get("id")

    console.print(f"[green]Wordle #{puzzle_id} loaded. Let's solve it![/green]")
    if hard_mode:
        console.print("[yellow]Hard mode enabled.[/yellow]")
    console.print()

    client = anthropic.Anthropic(api_key=api_key)
    guesses: list[tuple[str, list[str]]] = []
    messages: list[dict] = []
    solved = False

    # Initial prompt to Claude
    messages.append({
        "role": "user",
        "content": "Let's play Wordle! Give me your first guess — a 5-letter English word."
    })

    try:
        with Live(build_board(guesses, puzzle_id), console=console, refresh_per_second=4) as live:
            for turn in range(1, MAX_GUESSES + 1):
                # Get guess from Claude
                live.update(build_board(guesses, puzzle_id, f"Claude is thinking... (guess {turn})"))
                guess = ask_claude(client, messages, hard_mode)

                # Validate: must be 5 alpha chars
                if not (len(guess) == WORD_LENGTH and guess.isalpha()):
                    # Ask Claude to fix it
                    messages.append({"role": "assistant", "content": guess})
                    messages.append({
                        "role": "user",
                        "content": f"'{guess}' is not a valid 5-letter word. Try again — respond with ONLY a 5-letter English word."
                    })
                    guess = ask_claude(client, messages, hard_mode)
                    if not (len(guess) == WORD_LENGTH and guess.isalpha()):
                        console.print(f"[red]Claude gave invalid guess twice: '{guess}'. Skipping.[/red]")
                        continue

                # Check for repeated guess
                past_words = [g for g, _ in guesses]
                if guess in past_words:
                    messages.append({"role": "assistant", "content": guess})
                    messages.append({
                        "role": "user",
                        "content": f"You already guessed '{guess.upper()}'. Pick a DIFFERENT word."
                    })
                    guess = ask_claude(client, messages, hard_mode)
                    if guess in past_words:
                        # Force it — just continue and let it try again next turn
                        continue

                # Evaluate
                feedback = evaluate_guess(guess, answer)
                guesses.append((guess, feedback))

                # Add to conversation
                messages.append({"role": "assistant", "content": guess})

                # Check win
                if guess == answer:
                    solved = True
                    live.update(build_board(guesses, puzzle_id, "SOLVED!"))
                    time.sleep(0.5)
                    break

                # Send feedback to Claude
                feedback_msg = build_feedback_message(guess, feedback, turn, guesses)
                messages.append({"role": "user", "content": feedback_msg})

                live.update(build_board(guesses, puzzle_id, f"Guess {turn}/{MAX_GUESSES}"))
                time.sleep(0.3)  # brief pause for visual effect

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")

    # Final output
    console.print()
    if solved:
        score = len(guesses)
        console.print(f"[bold green]Solved in {score}/{MAX_GUESSES}![/bold green]")
    else:
        console.print(f"[bold red]Failed to solve. The answer was: {answer.upper()}[/bold red]")

    # Print share grid
    console.print()
    hard_star = "*" if hard_mode else ""
    header = f"Wordle {puzzle_id} {len(guesses) if solved else 'X'}/{MAX_GUESSES}{hard_star}"
    console.print(header)
    console.print()
    for _, feedback in guesses:
        console.print(format_guess_emoji(feedback))

    console.print()
    console.print("[dim]Powered by Claude AI[/dim]")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Claude-powered Wordle solver (NYT Wordle)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  wordle-solver                          # today's puzzle
  wordle-solver --date 2026-01-15        # specific date
  wordle-solver --hard                   # hard mode
  wordle-solver --date 2026-01-15 --hard
        """,
    )
    parser.add_argument("--date", "-d", type=str, default=None,
                        help="Puzzle date as YYYY-MM-DD (default: today)")
    parser.add_argument("--hard", action="store_true",
                        help="Enable hard mode (must reuse revealed hints)")
    parser.add_argument("--api-key", "-k", type=str, default=None,
                        help="Anthropic API key (default: from .env)")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("API_KEY")
    if not api_key:
        console.print("[red]Error: API key required.[/red]")
        console.print("Add API_KEY to .env file, set env var, or pass --api-key")
        sys.exit(1)

    date_str = args.date if args.date else get_today_date_str()

    # Validate date format
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        console.print(f"[red]Invalid date format: {date_str}. Use YYYY-MM-DD.[/red]")
        sys.exit(1)

    solve(date_str, api_key, args.hard)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        sys.exit(0)
