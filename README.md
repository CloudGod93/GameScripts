# 🎮 GameScripts

**AI-powered solvers for word games, powered by Claude.**

![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)
![Claude](https://img.shields.io/badge/AI-Claude%20Sonnet-blueviolet?logo=anthropic&logoColor=white)

---

## 🧩 Games

| Game | Status | Description |
|------|--------|-------------|
| [🧠 Contexto](contexto/) | ✅ Working | Solves [contexto.me](https://contexto.me) — guess the secret word by semantic distance |
| [🟩 Wordle](wordle/) | ✅ Working | Solves [NYT Wordle](https://www.nytimes.com/games/wordle) — 5-letter word in 6 guesses with color feedback |

---

## 🧠 Contexto Solver

The Contexto solver uses Claude to guess the secret word on [contexto.me](https://contexto.me). The game ranks every guess by semantic distance — `0` means you found the word, higher numbers mean further away.

### How it works

1. **🌱 Seed phase** — Casts a wide net with ~33 words across many domains (food, animals, tools, emotions, etc.) to triangulate the general area
2. **🤖 Claude loop** — Sends the best guesses so far to Claude in batches of 5, with context-aware hints at each distance tier:
   - `d ≤ 3` → *ALMOST THERE* — try exact synonyms
   - `d ≤ 10` → *ENDGAME* — very close, small variations
   - `d ≤ 100` → *VERY CLOSE* — right neighborhood
   - `d ≤ 400` → *GOOD SIGNAL* — stay in this domain
3. **🔄 Stuck detection** — If 6 guesses pass without improvement and best distance is still > 50, the solver pivots to an unexplored domain from a bank of ~350 words across 31 categories and resets Claude's conversation for a fresh perspective
4. **🎯 Victory** — Distance `0` found!

### 📺 Terminal UI

Rich live dashboard with:
- Real-time guess feed with color-coded distances
- Top 10 leaderboard of closest guesses
- Status panel showing current phase, best distance, and guess count
- Graceful Ctrl+C handling with progress summary

### 🔢 Game numbering

Contexto releases a new game daily. Game numbers increment by 1 each day:

- **Game #1254** = February 23, 2026 (anchor point)
- **Today's game** = anchor + days since anchor

The solver auto-calculates today's game number. Use `--game` to solve a past or specific game.

---

## 🟩 Wordle Solver

The Wordle solver uses Claude to play [NYT Wordle](https://www.nytimes.com/games/wordle). It fetches the daily puzzle, then has Claude guess the 5-letter word with real green/yellow/gray feedback — just like a human would play.

### How it works

1. **📡 Fetch puzzle** — Pulls today's answer from the NYT Wordle API (hidden from Claude)
2. **🤖 Claude plays** — Each turn, Claude picks a 5-letter word based on all previous feedback
3. **🎯 Evaluate** — The guess is scored against the answer:
   - 🟩 **Green** — correct letter, correct position
   - 🟨 **Yellow** — correct letter, wrong position
   - ⬛ **Gray** — letter not in the word
4. **🔁 Repeat** — Feedback and constraints are sent back to Claude (up to 6 guesses)
5. **📊 Share grid** — Win or lose, prints the emoji share grid

### 📺 Terminal UI

Rich live board with:
- Color-coded letter tiles (green/yellow/gray) just like the real game
- Mini keyboard showing known letter states
- Empty rows for remaining guesses
- Supports hard mode (`--hard`)

### 🔢 Puzzle dates

Wordle uses calendar dates instead of game numbers:

- **Puzzle #1** = June 19, 2021
- **Today's puzzle** = auto-detected by date
- Use `--date YYYY-MM-DD` to solve any past puzzle

---

## 🚀 Setup

1. **Clone and create a virtual environment:**
   ```bash
   git clone https://github.com/CloudGod93/GameScripts.git
   cd GameScripts
   python -m venv .venv
   source .venv/bin/activate
   ```

2. **Install in editable mode** (picks up all dependencies automatically):
   ```bash
   pip install -e .
   ```

3. **Configure your API key** — copy the example and add your key:
   ```bash
   cp .env.example .env
   ```
   Then edit `.env`:
   ```
   API_KEY=sk-ant-...
   ```

---

## ▶️ Usage

### Contexto
```bash
contexto-solver                          # solve today's game
contexto-solver --game 1200              # solve a specific game
contexto-solver --model opus             # use Claude Opus instead of Sonnet
contexto-solver --game 1200 --max-guesses 100
contexto-solver --lang pt                # Portuguese
```

### Wordle
```bash
wordle-solver                            # solve today's puzzle
wordle-solver --date 2026-01-15          # solve a specific date
wordle-solver --model opus               # use Claude Opus instead of Sonnet
wordle-solver --hard                     # hard mode
wordle-solver --date 2026-01-15 --hard   # specific date + hard mode
```

> Both solvers default to **Claude Sonnet 4.6**. Use `--model opus` for Claude Opus 4.6.

---

## 🤝 Contributing

Want to add a solver for another word game? Contributions are welcome!

1. Fork the repo
2. Create a new branch (`git checkout -b add-wordle-solver`)
3. Add your game solver in its own folder (e.g. `wordle/`)
4. Add a `[project.scripts]` entry in `pyproject.toml` for the CLI command
5. Open a PR

Each game gets its own package directory. Shared config (`.env`, `pyproject.toml`) lives at the root.

---

## 📄 License

[MIT](LICENSE) — do whatever you want with it.
