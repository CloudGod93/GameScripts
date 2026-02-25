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
| 🟩 Wordle | 🕐 Planned | Coming soon |

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
contexto-solver --game 1200 --max-guesses 100
contexto-solver --lang pt                # Portuguese
contexto-solver --api-key sk-ant-...     # pass key directly (optional)
```

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
