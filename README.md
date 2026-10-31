Agentic-GameAI-i9/
├── .env                      
├── .gitignore                
├── requirements.txt          
├── README.md
│
├── core/                     # code shared by every tier
│   ├── __init__.py           
│   ├── llm.py                
│   └── logger.py             
│
├── envs/                     # one file per game
│   ├── __init__.py           
│   ├── frozenlake.py         (Tier 0)
│   ├── game2048.py           (Tier 1)
│   ├── sokoban.py            (Tier 2)
│   ├── atari.py              (Tier 3)
│   └── pokemon.py            (Tier 4)
│
├── tiers/                    # one runnable script per tier
│   ├── __init__.py           
│   ├── tier0_frozenlake.py   
│   ├── tier1_2048.py
│   └── ...
│
├── memory/                   # Tier 4 only: notes, database
└── logs/                     



## Tier 0 — Sanity check (week 1, prove the loop works)

**Game: FrozenLake** (built into Gymnasium, zero setup)

- Tiny grid, discrete actions, deterministic-ish rules
- Goal here isn't a good agent — it's proving your perception → LLM decision → action loop actually runs end to end, with logging
- Skills tested: basic tool-calling loop, state serialisation to text

## Tier 1 — Single-step reasoning, static grid

**Game: 2048 or Snake (early stage)**

- State is just a small number grid, no complex physics/timing
- Agent has to reason about a rule ("which direction merges tiles best") but doesn't need memory across many turns
- Skills tested: turning grid state into a prompt the LLM can reason over well, prompt engineering for spatial reasoning

## Tier 2 — Planning + multi-step lookahead

**Game: Sokoban (`gym-sokoban`)**

- Now moves are irreversible-ish (push a box wrong, you can get stuck) — the agent has to plan several moves ahead, not just react
- This is where naive "ask LLM for next move" agents start failing, and you'll want to add things like self-critique, retry-on-stuck, or simple search-assisted prompting
- Skills tested: planning, failure recovery, maybe combining LLM reasoning with a lightweight search algorithm

## Tier 3 — Real-time / reflex pressure

**Game: Atari Pong or Breakout (Gymnasium + ALE)**

- Introduces timing — the agent has to act fast enough, and pixel-based state means someone builds a perception layer (screen → structured description or direct pixel/RAM parsing)
- Skills tested: latency-aware agent loops, vision-based state extraction, possibly a hybrid where a fast heuristic layer handles reflexes and the LLM handles higher-level strategy

## Tier 4 — Long-horizon memory across an extended playthrough

**Game: Pokémon via PyBoy (the "Claude Plays Pokémon" style setup)**

- This is a big step up: hours-long playthroughs, need persistent memory (where have I been, what's my current goal, what did I learn), and the state space is huge
- This is genuinely your RAG/retrieval background becoming directly useful — storing and retrieving "memories" of past game state/decisions
- Skills tested: long-term memory architecture, goal decomposition, context window management over long sessions

## Tier 5 — Multi-agent / competitive (optional branch, not strictly "harder" but different)

**Game: Battlesnake or generals.io**

- Multiple agents interacting/competing changes the problem entirely — now you need opponent modelling, not just environment modelling
- Good as a "phase 2" side track once the core single-agent framework is solid, since it reuses most of your Tier 1-2 framework
