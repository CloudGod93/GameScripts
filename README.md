# GameScripts

AI-powered solvers for word games, using Claude (Anthropic API).

## Games

| Game | Status | Description |
|------|--------|-------------|
| [Contexto](contexto/) | Working | Solves [contexto.me](https://contexto.me) — guess the secret word by semantic distance |
| Wordle | Planned | Coming soon |

## Setup

1. Clone the repo and create a virtual environment:
   ```bash
   git clone https://github.com/CloudGod93/GameScripts.git
   cd GameScripts
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r <(python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))")
   # or simply:
   pip install anthropic requests rich python-dotenv
   ```

3. Create a `.env` file in the project root with your Anthropic API key:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```

## Running

### Contexto
```bash
# Solve today's game
python -m contexto.solver

# Solve a specific game
python -m contexto.solver 1254
```
