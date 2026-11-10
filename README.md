# Agentic-GameAI

An LLM agent that plays games of increasing difficulty. Each tier adds one new hard problem: perception, planning, timing, memory, and opponents. The shared code in `core/` is reused by every tier.

## Overview

| Tier | Game | New challenge | Status |
|------|------|---------------|--------|
| 0 | FrozenLake | Prove the perception, LLM decision, action loop works | Implemented |
| 1 | Snake | Turn a grid into a prompt the LLM can reason over | Implemented |
| 2 | Sokoban | Multi-step planning and recovery from dead ends | Implemented |
| 3 | Breakout (Atari) | Real-time timing and pixel perception | Implemented |
| 4 | Snake Arena (4 snakes) | Multiple competing agents | Implemented |
| 5 | Pokemon (PyBoy) | Long-horizon memory | Planned |


## Project Structure

```text
Agentic-GameAI-i9/
├── .env
├── .gitignore
├── requirements.txt
├── README.md
│
├── core/                     # code shared by every tier
│   ├── __init__.py
│   ├── llm.py                # LLM client with retries
│   ├── logger.py             # one JSON line per step
│   └── viewer.py             # pygame window and side panel helpers
│
├── envs/                     # one file per game
│   ├── __init__.py
│   ├── frozenlake.py         (Tier 0)
│   ├── snake.py              (Tier 1)
│   ├── sokoban.py            (Tier 2)
│   ├── breakout.py           (Tier 3)
│   ├── arena.py              (Tier 4)
│   └── pokemon.py            (Tier 5)
│
├── tiers/                    # one runnable script per tier
│   ├── __init__.py
│   ├── Frozenlake.py
│   ├── Snake.py
│   ├── Sokoban.py
│   ├── Breakout.py
│   └── SnakeIO.py
│
├── memory/                   # Tier 5 only: notes, database
└── logs/                     # one .jsonl file per run
```

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux
pip install -r requirements.txt
```

Create a `.env` file in the project root. Example for Google Gemini (get a key at aistudio.google.com/apikey):

```text
LLM_API_KEY=your_key_here
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL=gemini-2.5-flash
```

For Groq, use `https://api.groq.com/openai/v1` as the base URL and a model from its model list. Model names and free-tier limits change over time, so check your provider. Switching providers only requires editing `.env`.

## Usage

Run each tier from the project root:

```bash
python -m tiers.Frozenlake
python -m tiers.Snake
python -m tiers.Sokoban
python -m tiers.Breakout
python -m tiers.SnakeIO
```

Each tier has its settings and colors as named variables at the top of its file. Every run writes the prompt, the LLM reply, the action, and the result of each step to a `.jsonl` file in `logs/`.

## Tiers

### Tier 0: Sanity check

**Game:** FrozenLake (Gymnasium, no setup)

- Tiny grid with discrete actions and simple rules
- The goal is not a good agent. It is proving the loop runs end to end with logging
- Skills tested: basic LLM decision loop, state serialisation to text

### Tier 1: Single-step reasoning on a static grid

**Game:** Snake

- State is a small grid with no complex physics or timing
- Optional hints (what is next to the head) can be switched off to measure their effect
- Skills tested: turning grid state into a prompt, prompt engineering for spatial reasoning

### Tier 2: Planning and multi-step lookahead

**Game:** Sokoban (`gym-sokoban`)

- Pushing a box into a corner can make the level unsolvable, so the agent must plan ahead
- The LLM returns a short plan per call. Deadlock detection, retry with lessons from failed attempts, and an optional BFS solver hint are included
- Skills tested: planning, failure recovery, combining LLM reasoning with a lightweight search

### Tier 3: Real-time and reflex pressure

**Game:** Breakout (Gymnasium + ALE)

- Pixel state is converted into numbers: ball position and velocity, paddle position, and the bricks left on each side
- A fast reflex layer moves the paddle every frame to the predicted landing point of the ball. The LLM runs in a background thread and only chooses where on the paddle the ball should land
- A stall detector breaks loops where the ball repeats one path, and the run ends when both brick screens are cleared
- Set `USE_LLM = False` to measure the reflex layer alone as a baseline
- Skills tested: latency-aware agent loops, vision-based state extraction, hybrid fast and slow control

### Tier 4: Multi-agent competition

**Game:** Snake Arena, a local four-snake game on a shared board

- Four snakes move at the same time on one board with many pieces of food. Dead snakes turn into food
- By default Red and Blue are played by the LLM, which returns run-length plans such as `PLAN: UP 4, LEFT 3`. Green and Yellow are algorithm opponents, so results show whether the LLM beats a fixed strategy
- Settings let you choose which snakes the LLM controls, the board size, and the plan length
- Skills tested: opponent modelling, planning under competition, call-efficient LLM use

### Tier 5: Long-horizon memory (planned)

**Game:** Pokemon via PyBoy (the "Claude Plays Pokemon" style setup)

- Hours-long playthroughs need persistent memory: where have I been, what is my current goal, what did I learn
- Storing and retrieving memories of past game state and decisions makes retrieval (RAG) background directly useful
- Skills tested: long-term memory architecture, goal decomposition, context window management

