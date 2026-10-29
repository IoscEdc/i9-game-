# Doodle Snake AI

A minimal Snake game where an autonomous AI agent plays using OpenRouter with Pygame.

## Directory Structure

```
harsh/Snake_Game/
├── .env                 # OpenRouter API key and model config
├── .env.example         # Template
├── requirements.txt     # Dependencies (pygame, requests, python-dotenv)
├── game.py              # Snake game logic
├── agent.py             # OpenRouter API caller with board prompt
├── main.py              # Pygame runner with Home Screen and Game Over modal
└── README.md            # Instructions
```

## Quick Start

1. Set your OpenRouter API key in `.env`:
```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
MODEL_NAME=nvidia/nemotron-3.5-super-vl:free
```

2. Run the game:
```bash
python3 main.py
```

## Controls
- Mouse: Click Play button on Home Screen, or Pause/Resume during game.
- Keyboard:
  - [SPACE]: Pause / Resume
  - [R]: Restart
  - [H]: Home Screen
  - [Q]: Quit
