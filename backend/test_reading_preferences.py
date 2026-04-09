import argparse
import json
import time
from typing import List

import requests


def create_reading_preference_task(base_url: str, book_titles: List[str]) -> str:
    url = f"{base_url.rstrip('/')}/agent/reading-preferences/tasks"
    payload = {
        "book_titles": book_titles,
    }
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    task_id = data.get("task_id")
    if not task_id:
        raise RuntimeError("Task id not found in response")
    return task_id


def poll_reading_preference_task(base_url: str, task_id: str, interval: int = 2, timeout: int = 300) -> bool:
    url = f"{base_url.rstrip('/')}/agent/reading-preferences/tasks/{task_id}"
    started_at = time.time()

    while time.time() - started_at < timeout:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        status = data.get("status")
        print(f"Task status: {status}")

        if status == "completed":
            result = data.get("result", {})
            print("Success!")
            print(f"Provider: {result.get('provider')}")
            print(f"Model: {result.get('model')}")
            print(f"Input summary: {json.dumps(result.get('input_summary', {}), ensure_ascii=False)}")
            print("\nAnalysis:\n")
            print(result.get("analysis", ""))
            return True

        if status == "failed":
            print(f"Task failed: {data.get('error')}")
            return False

        time.sleep(interval)

    print("Polling timed out")
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test reading preference analysis task API.")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8001",
        help="API base URL, default: http://127.0.0.1:8001",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=2,
        help="Polling interval in seconds, default: 2",
    )
    parser.add_argument(
        "--poll-timeout",
        type=int,
        default=300,
        help="Polling timeout in seconds, default: 300",
    )
    parser.add_argument(
        "titles",
        nargs="*",
        help="Book titles to analyze. If omitted, a default demo list is used.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    titles = args.titles or [
        "Effective Python",
        "Atomic Habits",
        "Deep Work",
        "Clean Code",
        "Thinking, Fast and Slow",
    ]

    print("Testing reading preference API with titles:")
    for title in titles:
        print(f"- {title}")
    print()

    task_id = create_reading_preference_task(args.base_url, titles)
    print(f"Created task: {task_id}")
    poll_reading_preference_task(
        args.base_url,
        task_id,
        interval=args.poll_interval,
        timeout=args.poll_timeout,
    )


if __name__ == "__main__":
    main()
