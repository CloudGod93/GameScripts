#!/usr/bin/env python3
"""
solver.py — Claude-powered solver for contexto.me

Usage:
    python -m contexto.solver                     # solve today's game
    python -m contexto.solver --game 1200         # solve specific game #
    python -m contexto.solver --game 1200 --max-guesses 150
    python -m contexto.solver --lang pt           # Portuguese version

    # or run directly:
    python contexto/solver.py
    python contexto/solver.py --game 1200
"""

import argparse
import os
from pathlib import Path
import random
import sys
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
# Load .env from project root (parent of contexto/)
_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / ".env")
# Also try local .env as fallback
load_dotenv()

import anthropic
import requests
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

CONTEXTO_BASE_URL = "https://api.contexto.me/machado/{lang}/game/{game_id}/{word}"

ANCHOR_GAME_ID = 1256
ANCHOR_DATE = datetime(2026, 2, 23, tzinfo=timezone.utc)

CLAUDE_MODEL = "claude-sonnet-4-6"

RANK_GREEN_THRESHOLD = 300
RANK_YELLOW_THRESHOLD = 1500

REQUEST_DELAY = 0.25
CLAUDE_CALL_DELAY = 0.5

MAX_RECENT_GUESSES = 18
STUCK_THRESHOLD = 6       # guesses without improvement before forcing a pivot
ENDGAME_DISTANCE = 10     # distance threshold for endgame mode
BATCH_SIZE = 5            # how many words to ask Claude for per turn

console = Console()

# ─────────────────────────────────────────────────────────────────────────────
# Broad seed words — one per major semantic domain to triangulate quickly
# ─────────────────────────────────────────────────────────────────────────────

SEED_WORDS = [
    # nature & environment
    "water", "tree", "mountain", "weather", "flower",
    # food & drink
    "food", "fruit", "bread", "sugar", "coffee",
    # animals
    "animal", "bird", "fish", "dog",
    # people & body
    "person", "hand", "heart", "family",
    # objects & tools
    "house", "car", "book", "knife", "phone",
    # abstract & society
    "time", "money", "love", "power", "game",
    # materials & substances
    "metal", "wood", "glass", "stone",
    # arts & culture
    "music", "color", "dance",
]

# ─────────────────────────────────────────────────────────────────────────────
# Pivot bank — categorized words for forced domain exploration
# When stuck, we pick from the least-explored domains
# ─────────────────────────────────────────────────────────────────────────────

PIVOT_DOMAINS = {
    "food_fruit": ["apple", "melon", "berry", "grape", "lemon", "peach", "cherry", "mango", "plum", "pear", "banana", "orange", "coconut", "pineapple"],
    "food_meal": ["dinner", "breakfast", "soup", "salad", "cake", "cheese", "butter", "rice", "pasta", "sauce", "spice", "pepper", "salt", "honey"],
    "vegetables": ["carrot", "potato", "tomato", "onion", "corn", "bean", "pea", "lettuce", "garlic", "mushroom", "cucumber", "celery"],
    "drink": ["tea", "wine", "beer", "juice", "milk", "soda", "whiskey", "cocktail", "lemonade", "smoothie"],
    "nature": ["river", "ocean", "forest", "desert", "island", "valley", "lake", "pond", "creek", "marsh", "meadow", "prairie"],
    "plants": ["rose", "grass", "seed", "root", "leaf", "vine", "bush", "herb", "moss", "fern", "oak", "pine", "palm", "willow"],
    "weather": ["rain", "snow", "wind", "storm", "cloud", "thunder", "frost", "fog", "ice", "heat", "drought", "hurricane"],
    "animals": ["cat", "horse", "wolf", "bear", "eagle", "snake", "rabbit", "deer", "lion", "whale", "butterfly", "bee", "ant", "spider"],
    "body": ["head", "eye", "bone", "skin", "blood", "brain", "tooth", "hair", "finger", "foot", "neck", "shoulder", "chest"],
    "clothing": ["shirt", "dress", "shoe", "hat", "coat", "belt", "glove", "scarf", "sock", "jacket", "suit", "skirt", "tie"],
    "home": ["door", "window", "floor", "roof", "wall", "bed", "chair", "table", "lamp", "mirror", "shelf", "carpet", "curtain"],
    "tools": ["hammer", "saw", "drill", "wrench", "pliers", "screwdriver", "brush", "shovel", "rake", "axe", "needle", "scissors"],
    "transport": ["boat", "train", "plane", "bicycle", "truck", "bus", "ship", "wheel", "engine", "road", "bridge", "tunnel"],
    "work": ["teacher", "doctor", "farmer", "soldier", "writer", "artist", "cook", "nurse", "judge", "pilot", "merchant", "clerk"],
    "emotion": ["joy", "fear", "anger", "sadness", "hope", "pride", "shame", "grief", "envy", "trust", "disgust", "surprise"],
    "abstract": ["truth", "freedom", "justice", "peace", "luck", "fate", "dream", "thought", "memory", "wisdom", "beauty", "faith"],
    "science": ["chemical", "atom", "cell", "energy", "gravity", "magnet", "circuit", "voltage", "spectrum", "crystal", "molecule"],
    "sport": ["ball", "goal", "race", "team", "score", "match", "swim", "jump", "throw", "kick", "pitch", "court"],
    "music_art": ["song", "piano", "guitar", "drum", "painting", "sculpture", "poem", "novel", "film", "theater", "camera"],
    "material": ["cotton", "silk", "leather", "rubber", "plastic", "clay", "brick", "steel", "copper", "gold", "silver", "diamond"],
    "color_light": ["red", "blue", "green", "yellow", "purple", "pink", "brown", "white", "black", "shadow", "bright", "dark"],
    "time_space": ["morning", "night", "winter", "summer", "spring", "autumn", "hour", "century", "dawn", "dusk", "midnight"],
    "war_conflict": ["war", "battle", "sword", "shield", "army", "weapon", "gun", "bullet", "bomb", "tank", "fortress"],
    "water_sea": ["wave", "tide", "shore", "coral", "anchor", "sail", "harbor", "port", "dock", "lighthouse", "seaweed"],
    "earth_geo": ["sand", "mud", "dust", "cave", "cliff", "volcano", "canyon", "hill", "ridge", "boulder", "pebble"],
    "sky_space": ["sun", "moon", "star", "planet", "sky", "cloud", "rainbow", "comet", "galaxy", "orbit", "satellite"],
    "medical": ["medicine", "pill", "hospital", "surgery", "fever", "wound", "bandage", "vaccine", "symptom", "diagnosis"],
    "tech": ["computer", "internet", "software", "robot", "screen", "keyboard", "network", "data", "code", "signal"],
    "money_biz": ["bank", "coin", "debt", "profit", "stock", "trade", "market", "price", "tax", "wealth", "budget"],
    "legal": ["law", "crime", "prison", "trial", "jury", "verdict", "punishment", "evidence", "witness", "contract"],
    "religion": ["church", "prayer", "soul", "heaven", "angel", "temple", "ritual", "sacred", "blessing", "miracle"],
}


# ─────────────────────────────────────────────────────────────────────────────
# Contexto API
# ─────────────────────────────────────────────────────────────────────────────

def get_current_game_id() -> int:
    now = datetime.now(timezone.utc)
    delta = now - ANCHOR_DATE
    return ANCHOR_GAME_ID + delta.days


def guess_word(game_id: int, word: str, lang: str = "en") -> dict | None:
    url = CONTEXTO_BASE_URL.format(lang=lang, game_id=game_id, word=word.lower().strip())
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return {
            "word": data.get("result", word),
            "distance": int(data["distance"]),
        }
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return None
        return None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Display helpers
# ─────────────────────────────────────────────────────────────────────────────

def rank_color(distance: int) -> str:
    if distance == 0:
        return "bold green"
    if distance <= RANK_GREEN_THRESHOLD:
        return "green"
    if distance <= RANK_YELLOW_THRESHOLD:
        return "yellow"
    return "red"


def format_rank_bar(distance: int, max_width: int = 20) -> str:
    if distance == 0:
        return "█" * max_width
    fill = max(0, max_width - int(distance / 600))
    return "█" * fill + "░" * (max_width - fill)


def build_leaderboard(guesses: list[dict], count: int = 10) -> Table:
    table = Table(
        title="Leaderboard", box=box.ROUNDED, show_header=True,
        header_style="bold cyan", title_style="bold cyan",
        border_style="cyan", padding=(0, 1),
    )
    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("Word", width=16)
    table.add_column("Dist", justify="right", width=6)
    table.add_column("", width=20)

    if not guesses:
        table.add_row("", "[dim]no guesses yet[/dim]", "", "")
        return table

    sorted_g = sorted(guesses, key=lambda x: x["distance"])[:count]
    for i, row in enumerate(sorted_g, 1):
        d = row["distance"]
        color = rank_color(d)
        table.add_row(
            str(i),
            f"[{color}]{row['word']}[/{color}]",
            f"[{color}]{d}[/{color}]",
            f"[{color}]{format_rank_bar(d)}[/{color}]",
        )
    return table


def build_guess_feed(recent: list[dict], phase: str) -> Table:
    table = Table(
        title=f"Guess Feed — {phase}", box=box.ROUNDED, show_header=True,
        header_style="bold", title_style="bold", border_style="dim", padding=(0, 1),
    )
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Word", width=16)
    table.add_column("Dist", justify="right", width=6)
    table.add_column("", width=20)

    for entry in recent:
        d = entry["distance"]
        color = rank_color(d)
        label = "FOUND!" if d == 0 else str(d)
        table.add_row(
            str(entry["guess_num"]),
            f"[{color}]{entry['word']}[/{color}]",
            f"[{color}]{label}[/{color}]",
            f"[{color}]{format_rank_bar(d)}[/{color}]",
        )
    return table


def build_header(game_id: int, lang: str, guess_number: int, max_guesses: int,
                 elapsed: float, status: str) -> Panel:
    info = Text()
    info.append(f"Game #{game_id}", style="bold cyan")
    info.append("  |  ", style="dim")
    info.append(f"Model: {CLAUDE_MODEL}", style="cyan")
    info.append("  |  ", style="dim")
    info.append(f"Lang: {lang}", style="cyan")
    info.append("  |  ", style="dim")
    info.append(f"Guess: {guess_number}/{max_guesses}", style="bold white")
    info.append("  |  ", style="dim")
    info.append(f"Time: {elapsed:.0f}s", style="white")
    info.append("  |  ", style="dim")
    info.append(status, style="bold yellow")
    return Panel(info, title="[bold]Contexto Solver[/bold]", border_style="bright_cyan", padding=(0, 2))


def build_status_line(messages: list[str], max_lines: int = 3) -> Panel:
    text = Text()
    for msg in messages[-max_lines:]:
        text.append(f"  {msg}\n", style="dim")
    if not messages:
        text.append("  Waiting...\n", style="dim")
    return Panel(text, title="[dim]Status[/dim]", border_style="dim", height=max_lines + 2)


def build_dashboard(game_id, lang, guess_number, max_guesses, elapsed, status_text,
                    guesses, recent_feed, phase, status_messages):
    return Group(
        build_header(game_id, lang, guess_number, max_guesses, elapsed, status_text),
        "", build_guess_feed(recent_feed, phase),
        "", build_leaderboard(guesses, count=10),
        "", build_status_line(status_messages),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pivot logic — escape local minima
# ─────────────────────────────────────────────────────────────────────────────

def get_explored_domains(attempted_words: set[str]) -> set[str]:
    """Figure out which pivot domains we've already touched."""
    explored = set()
    for domain, words in PIVOT_DOMAINS.items():
        if any(w in attempted_words for w in words):
            explored.add(domain)
    return explored


def pick_pivot_word(attempted_words: set[str]) -> str | None:
    """Pick a word from the least-explored domain."""
    explored = get_explored_domains(attempted_words)
    unexplored = [d for d in PIVOT_DOMAINS if d not in explored]

    candidates = unexplored if unexplored else list(PIVOT_DOMAINS.keys())
    random.shuffle(candidates)

    for domain in candidates:
        available = [w for w in PIVOT_DOMAINS[domain] if w not in attempted_words]
        if available:
            return random.choice(available)

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Claude strategy engine
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an expert solver for the word game Contexto (contexto.me).

HOW THE GAME WORKS:
- There is one secret word. Every word has a distance score (word embedding cosine similarity).
- Distance 0 = the secret word. Lower distance = closer.
- Similarity = co-occurrence in text corpora, NOT dictionary synonyms.

CRITICAL RULES:
1. ALWAYS FOLLOW THE SIGNAL. Look at the words with the LOWEST distance scores. \
The answer is in the SAME domain as those words. If "food" is at distance 108, \
EVERY guess should be food-related. Do NOT wander off to unrelated topics.

2. When exploring (best distance > 500), try diverse domains to find the right one.

3. When narrowing (best distance < 500), STAY IN THE WINNING DOMAIN. \
Do not guess random words. Only guess words closely related to your best results.

4. When close (distance < 50), try: compound words, specific subtypes, \
agent nouns (fisher), specific varieties, or the exact term connecting the top words.

5. NEVER repeat words or guess morphological variants (stare/stared/staring).

6. The answer is usually a common, concrete noun.

RESPONSE FORMAT:
Reply with EXACTLY 5 words, one per line, lowercase, no punctuation, no explanation.
"""


def build_guess_history_str(guesses: list[dict], limit: int = 40) -> str:
    if not guesses:
        return "No guesses yet."
    sorted_g = sorted(guesses, key=lambda x: x["distance"])[:limit]
    lines = [f"distance {g['distance']:>5}: {g['word']}" for g in sorted_g]
    if len(guesses) > limit:
        lines.append(f"... and {len(guesses) - limit} more (omitted)")
    return "\n".join(lines)


def ask_claude_for_batch(
    client: anthropic.Anthropic,
    conversation: list[dict],
    guesses: list[dict],
    attempted_words: set[str],
    guess_number: int,
    status_messages: list[str],
    is_stuck: bool = False,
    pivot_hint: str | None = None,
) -> tuple[list[str], list[dict]]:
    """Ask Claude for a batch of word guesses. Returns (word_list, updated_conversation)."""

    history_str = build_guess_history_str(guesses)
    best = sorted(guesses, key=lambda x: x["distance"])[0] if guesses else None
    best_info = (
        f"Closest so far: '{best['word']}' at distance {best['distance']}"
        if best else "No guesses yet"
    )

    recent_tried = sorted(attempted_words)[-30:] if len(attempted_words) > 30 else sorted(attempted_words)

    # Build context-aware hints
    extra_hints = ""

    if is_stuck and pivot_hint:
        extra_hints += (
            f"\n\nPIVOT REQUIRED: You have been stuck in the same semantic cluster for too long. "
            f"COMPLETELY ABANDON your current line of thinking. "
            f"I just probed '{pivot_hint}' from a different domain — use that new signal. "
            f"Try words from a TOTALLY different category than your recent guesses. "
            f"Each of your 5 words should be from a DIFFERENT domain."
        )
    elif is_stuck:
        extra_hints += (
            f"\n\nWARNING: You are stuck. Your best distance has not improved in many guesses. "
            f"Your current cluster is WRONG. Try completely different domains: "
            f"food, animals, tools, clothing, body parts, weather, materials, sports, etc. "
            f"Each of your 5 words should be from a DIFFERENT domain."
        )

    if best and best["distance"] <= 3:
        top_words = [g["word"] for g in sorted(guesses, key=lambda x: x["distance"])[:5]]
        extra_hints += (
            f"\n\nALMOST THERE — Distance {best['distance']}! "
            f"The answer is practically a SYNONYM of: {', '.join(top_words)}. "
            f"Think: what is ANOTHER WORD for '{top_words[0]}'? "
            f"Try every synonym, near-synonym, and closely related noun you can think of. "
            f"Also try: the formal version, the informal version, the British vs American spelling, "
            f"compound words, and specific subtypes of '{top_words[0]}'."
        )
    elif best and best["distance"] <= ENDGAME_DISTANCE:
        top_words = [g["word"] for g in sorted(guesses, key=lambda x: x["distance"])[:5]]
        extra_hints += (
            f"\n\nENDGAME — Distance {best['distance']}! "
            f"The answer is EXTREMELY close to: {', '.join(top_words)}. "
            f"ALL 5 words must be tightly related. Think: "
            f"what SPECIFIC THING connects '{top_words[0]}' and '{top_words[1] if len(top_words) > 1 else top_words[0]}'? "
            f"Try: compound words, agent nouns, specific subtypes, the exact category name, "
            f"or less common synonyms."
        )
    elif best and best["distance"] <= 100:
        top_words = [g["word"] for g in sorted(guesses, key=lambda x: x["distance"])[:8]]
        extra_hints += (
            f"\n\nVERY CLOSE (d={best['distance']}) — Top words: {', '.join(top_words)}. "
            f"DO NOT STRAY. ALL 5 guesses must be tightly related to these words. "
            f"Try specific items, subtypes, compound words, or the umbrella term. "
            f"Do NOT guess generic adjectives or unrelated words."
        )
    elif best and best["distance"] <= 400:
        top_words = [g["word"] for g in sorted(guesses, key=lambda x: x["distance"])[:5]]
        extra_hints += (
            f"\n\nGOOD SIGNAL (d={best['distance']}) — Best words: {', '.join(top_words)}. "
            f"STAY in this domain. ALL 5 guesses must be related to these top words. "
            f"Think: what category do these belong to? Guess more words from THAT category. "
            f"Do NOT guess random or unrelated words."
        )

    user_msg = (
        f"Guess round starting at #{guess_number}\n"
        f"{best_info}\n\n"
        f"Guesses sorted by distance (lower = closer):\n"
        f"{history_str}\n\n"
        f"Words already tried (do NOT repeat): {', '.join(recent_tried) if recent_tried else 'none'}"
        f"{extra_hints}\n\n"
        f"Give me {BATCH_SIZE} words, one per line:"
    )

    conversation.append({"role": "user", "content": user_msg})

    backoff_base = 2.0
    for attempt in range(6):
        time.sleep(CLAUDE_CALL_DELAY)
        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=60,
                system=SYSTEM_PROMPT,
                messages=conversation,
            )
            raw = response.content[0].text.strip().lower()
            conversation.append({"role": "assistant", "content": raw})

            # Parse multiple words from response
            words = []
            for line in raw.split("\n"):
                w = line.strip().split()[0].strip(".,!?\"'-:0123456789) ") if line.strip() else ""
                if w and w not in attempted_words and w not in words and len(w) > 1:
                    words.append(w)

            if words:
                return words[:BATCH_SIZE], conversation

            # If all words were duplicates, ask again
            status_messages.append("All suggestions were duplicates, asking again...")
            conversation.append({
                "role": "user",
                "content": "All those were already tried. Give me 5 completely new, different words."
            })
            continue

        except anthropic.RateLimitError:
            sleep_s = min(60, (backoff_base ** attempt) + random.random())
            status_messages.append(f"Rate limited, sleeping {sleep_s:.1f}s...")
            time.sleep(sleep_s)
        except anthropic.AuthenticationError as e:
            console.clear()
            console.print(f"[red bold]ERROR: Invalid API key.[/red bold]\n[red]{e}[/red]")
            sys.exit(1)
        except anthropic.BadRequestError as e:
            if 'credit balance' in str(e).lower():
                console.clear()
                console.print("[red bold]ERROR: No credits.[/red bold]")
                console.print("[red]https://console.anthropic.com/settings/plans[/red]")
                sys.exit(1)
            status_messages.append(f"API error: {e}")
            time.sleep(2)
        except Exception as e:
            status_messages.append(f"Error: {type(e).__name__}: {e}")
            time.sleep(2)

    fallback = pick_pivot_word(attempted_words) or "thing"
    status_messages.append(f"Claude failed, falling back to '{fallback}'")
    conversation.append({"role": "assistant", "content": fallback})
    return [fallback], conversation


# ─────────────────────────────────────────────────────────────────────────────
# Main solver loop
# ─────────────────────────────────────────────────────────────────────────────

def solve(game_id: int, lang: str, max_guesses: int, api_key: str):
    client = anthropic.Anthropic(api_key=api_key)

    guesses: list[dict] = []
    attempted: set[str] = set()
    conversation: list[dict] = []
    recent_feed: list[dict] = []
    status_messages: list[str] = []
    start_time = time.time()
    guess_number = 0
    found = False
    phase = "Phase 1: Broad Probes"
    best_distance = float("inf")
    guesses_since_improvement = 0
    interrupted = False

    console.clear()

    def do_guess(word: str) -> dict | None:
        """Submit a guess to Contexto and track results."""
        nonlocal guess_number, found, best_distance, guesses_since_improvement
        guess_number += 1
        result = guess_word(game_id, word, lang)
        time.sleep(REQUEST_DELAY)

        if result is None:
            attempted.add(word)
            status_messages.append(f"'{word}' not in vocab")
            return None

        attempted.add(word)
        guesses.append(result)
        recent_feed.append({"guess_num": guess_number, "word": result["word"], "distance": result["distance"]})

        if result["distance"] < best_distance:
            best_distance = result["distance"]
            guesses_since_improvement = 0
        else:
            guesses_since_improvement += 1

        if result["distance"] == 0:
            found = True

        return result

    try:
        with Live(console=console, refresh_per_second=4, screen=True) as live:

            def refresh(status_text: str = "Thinking..."):
                elapsed = time.time() - start_time
                live.update(build_dashboard(
                    game_id, lang, guess_number, max_guesses, elapsed, status_text,
                    guesses, recent_feed[-MAX_RECENT_GUESSES:], phase, status_messages,
                ))

            # ── Phase 1: Broad seed probes ────────────────────────────────────
            refresh("Sending broad probes...")

            for seed in SEED_WORDS:
                if found:
                    break
                if seed in attempted:
                    continue
                refresh(f"Probing: {seed}")
                do_guess(seed)
                refresh(f"Probed {len(attempted)}/{len(SEED_WORDS)} seeds")

            # ── Phase 2: Claude-guided batch search with stuck detection ─────
            if not found:
                phase = "Phase 2: Claude Search"
                pivot_cooldown = 0

                while not found and guess_number < max_guesses:
                    is_stuck = guesses_since_improvement >= STUCK_THRESHOLD and best_distance > 50
                    pivot_hint = None

                    # Force a pivot: probe a word from an unexplored domain
                    if is_stuck and pivot_cooldown <= 0:
                        pivot_word = pick_pivot_word(attempted)
                        if pivot_word:
                            status_messages.append(f"PIVOT: trying '{pivot_word}' from new domain")
                            refresh(f"Pivoting: {pivot_word}")
                            result = do_guess(pivot_word)
                            if found:
                                break
                            if result:
                                pivot_hint = pivot_word
                            conversation.clear()
                            status_messages.append("Conversation reset — fresh perspective")
                            guesses_since_improvement = 0
                            pivot_cooldown = 5
                            refresh("Pivoted, asking Claude with fresh eyes...")
                        else:
                            status_messages.append("No more pivot words available")

                    pivot_cooldown = max(0, pivot_cooldown - 1)

                    # Ask Claude for a batch of words
                    refresh("Asking Claude for batch...")
                    words, conversation = ask_claude_for_batch(
                        client, conversation, guesses, attempted,
                        guess_number + 1, status_messages,
                        is_stuck=is_stuck, pivot_hint=pivot_hint,
                    )
                    status_messages.append(f"Claude suggested: {', '.join(words)}")

                    # Submit each word in the batch rapidly
                    for word in words:
                        if found or guess_number >= max_guesses:
                            break
                        if word in attempted:
                            continue
                        refresh(f"Guessing: {word}")
                        result = do_guess(word)
                        if found:
                            break
                        if result:
                            refresh(f"{result['word']} -> d={result['distance']}")
                        else:
                            refresh(f"'{word}' not in vocab")

            # ── Final screen ──────────────────────────────────────────────────
            if found:
                phase = "SOLVED!"
                refresh("SOLVED!")
            else:
                phase = "FAILED"
                refresh(f"Did not solve in {max_guesses} guesses")
            time.sleep(1.5)

    except KeyboardInterrupt:
        interrupted = True

    # ── Results ───────────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    console.clear()
    console.print()

    if interrupted:
        console.rule("[bold yellow]Contexto Solver — Interrupted[/bold yellow]")
    else:
        console.rule("[bold cyan]Contexto Solver — Results[/bold cyan]")
    console.print()

    if interrupted:
        console.print(f"  [yellow]Stopped by user after {guess_number} guesses.[/yellow]")
        console.print(f"  Game    : [cyan]#{game_id}[/cyan]")
        console.print(f"  Time    : [cyan]{elapsed:.1f}s[/cyan]")
        if guesses:
            best = sorted(guesses, key=lambda x: x["distance"])[0]
            console.print(f"  Closest : [cyan]{best['word']}[/cyan] (d={best['distance']})")
    elif found:
        winner = sorted(guesses, key=lambda x: x["distance"])[0]
        console.print(f"  [bold green]SOLVED![/bold green] The word was: [bold green]{winner['word'].upper()}[/bold green]")
        console.print(f"  Game    : [cyan]#{game_id}[/cyan]")
        console.print(f"  Guesses : [cyan]{guess_number}[/cyan]")
        console.print(f"  Time    : [cyan]{elapsed:.1f}s[/cyan]")
        console.print(f"  Model   : [cyan]{CLAUDE_MODEL}[/cyan]")
        console.print()

        green_count  = sum(1 for g in guesses if 1 <= g["distance"] <= RANK_GREEN_THRESHOLD)
        yellow_count = sum(1 for g in guesses if RANK_GREEN_THRESHOLD < g["distance"] <= RANK_YELLOW_THRESHOLD)
        red_count    = sum(1 for g in guesses if g["distance"] > RANK_YELLOW_THRESHOLD)
        console.print(f"  [green]{'█' * min(green_count, 20)}[/green] {green_count} green")
        console.print(f"  [yellow]{'█' * min(yellow_count, 20)}[/yellow] {yellow_count} yellow")
        console.print(f"  [red]{'█' * min(red_count, 20)}[/red] {red_count} red")
    else:
        console.print(f"  [red]Did not solve in {max_guesses} guesses.[/red]")
        console.print(f"  Game    : [cyan]#{game_id}[/cyan]")
        console.print(f"  Time    : [cyan]{elapsed:.1f}s[/cyan]")

    console.print()
    console.print(build_leaderboard(guesses, count=15))
    console.print()

    return found, guess_number, guesses


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Claude-powered Contexto solver (contexto.me)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python contexto_solver.py                      # today's game
  python contexto_solver.py --game 1200          # specific game
  python contexto_solver.py --game 1200 --max-guesses 100
  python contexto_solver.py --lang pt            # Portuguese
        """,
    )
    parser.add_argument("--game", "-g", type=int, default=None,
                        help="Game number (default: today's)")
    parser.add_argument("--max-guesses", "-m", type=int, default=200,
                        help="Max guesses (default: 200)")
    parser.add_argument("--lang", "-l", type=str, default="en", choices=["en", "pt", "es"],
                        help="Language (default: en)")
    parser.add_argument("--api-key", "-k", type=str, default=None,
                        help="Anthropic API key (default: from .env)")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]Error: Anthropic API key required.[/red]")
        console.print("Add ANTHROPIC_API_KEY to .env file, set env var, or pass --api-key")
        sys.exit(1)

    game_id = args.game if args.game is not None else get_current_game_id()
    solve(game_id, args.lang, args.max_guesses, api_key)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        sys.exit(0)
