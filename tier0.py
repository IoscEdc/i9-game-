import os, time
import gymnasium as gym
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

env = gym.make("FrozenLake-v1", map_name="4x4", render_mode=None)
observation, info = env.reset()

terminated = False
truncated = False
step_count = 0

print("--- Starting Tier 0 Sanity Check ---")

while not (terminated or truncated) and step_count < 15:
    step_count+=1

prompt = f"""
You are playing a grid game called FrozenLake on a 4x4 board.
Your current position tile index is: {observation}.

The board layout (indices 0 to 15) is:
Row 0: [ 0:S, 1:F, 2:F, 3:F ]
Row 1: [ 4:F, 5:H, 6:F, 7:H ]
Row 2: [ 8:F, 9:F, 10:F, 11:H ]
Row 3: [ 12:H, 13:F, 14:F, 15:G ]

Legend: S = Start, F = Frozen (safe), H = Hole (lose), G = Goal (win).
Valid Actions:
0 = Left
1 = Down
2 = Right
3 = Up

Choose your next action based on your current position.
IMPORTANT: Reply with ONLY a single digit number (0, 1, 2 or 3) corresponding to your action. No extra text.
"""

try:
    response = client.models.generate_content(
        model="gemini-3.8-flash", contents=prompt
    )
    raw_output = response.text.strip()
    action = int(raw_output) if raw_output.isdigit() else 0

    if action not in [0, 1, 2, 3]:
        action = 0

except Exception as e:
    print(f"API Error or parsing failed: {e}. Defaulting to action 0.")
    action = 0

next_observation, reward, terminated, truncated, info = env.step(action)

action_names = ["Left", "Down", "Right", "Up"]
print(f"Step {step_count} | Current Tile: {observation} | Chosen Action:"
      f" {action} ({action_names[action]}) | Next Tile: {next_observation} |"
      f" Reward: {reward}"
)

observation = next_observation

time.sleep(0.5)

print("--- EPISODE FINISHED ---")
if reward > 0:
    print("Success! Reached the goal!")
else:
    print("Ended in a hole or timed out. That's totally fine for Tier 0!")

env.close()