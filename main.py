"""AI Agent 入口"""

import sys
from src.agent import build_agent


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # type: ignore[attr-defined]

    agent = build_agent()
    print("AI Agent 已启动，输入 'quit' 退出\n")

    while True:
        user_input = input("你: ")
        if user_input.lower() in ("quit", "exit", "q"):
            break

        response = agent.chat(user_input)
        print(f"AI: {response}\n")


if __name__ == "__main__":
    main()
