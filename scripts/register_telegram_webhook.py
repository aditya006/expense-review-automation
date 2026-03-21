#!/usr/bin/env python3
from __future__ import annotations

import argparse

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="Register Telegram webhook")
    parser.add_argument("--bot-token", required=True)
    parser.add_argument("--webhook-url", required=True)
    parser.add_argument("--secret-token", default="")
    args = parser.parse_args()

    url = f"https://api.telegram.org/bot{args.bot_token}/setWebhook"
    payload = {"url": args.webhook_url}
    if args.secret_token:
        payload["secret_token"] = args.secret_token

    response = httpx.post(url, json=payload, timeout=10.0)
    print(response.status_code)
    print(response.text)


if __name__ == "__main__":
    main()
