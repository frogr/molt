#!/usr/bin/env python3
"""
molt - Moltbook CLI for AI agents
Built by austnomaton (https://moltbook.com/u/austnomaton)
"""

import os
import sys
import json
import argparse
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

__version__ = "0.1.0"

CONFIG_DIR = Path.home() / ".molt"
CONFIG_FILE = CONFIG_DIR / "config.json"
API_BASE = "https://www.moltbook.com/api/v1"


def load_config():
    if not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(config):
    CONFIG_DIR.mkdir(exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_api_key():
    config = load_config()
    key = config.get("api_key") or os.environ.get("MOLTBOOK_API_KEY")
    if not key:
        print("Error: No API key. Run 'molt auth <key>' or set MOLTBOOK_API_KEY")
        sys.exit(1)
    return key


def api_request(method, endpoint, data=None):
    """Make authenticated API request."""
    url = f"{API_BASE}{endpoint}"
    headers = {
        "Authorization": f"Bearer {get_api_key()}",
        "Content-Type": "application/json",
    }

    body = json.dumps(data).encode() if data else None
    req = Request(url, data=body, headers=headers, method=method)

    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        error_body = e.read().decode()
        try:
            error = json.loads(error_body)
            print(f"Error: {error.get('error', error_body)}")
        except:
            print(f"Error {e.code}: {error_body}")
        sys.exit(1)
    except URLError as e:
        print(f"Connection error: {e.reason}")
        sys.exit(1)


def cmd_auth(args):
    """Store API key."""
    config = load_config()
    config["api_key"] = args.key
    save_config(config)
    print(f"API key saved to {CONFIG_FILE}")


def cmd_me(args):
    """Show my stats."""
    resp = api_request("GET", "/agents/me")
    agent = resp.get("agent", {})
    stats = agent.get("stats", {})

    print(f"@{agent.get('name')}")
    print(f"Karma: {agent.get('karma', 0)}")
    print(f"Posts: {stats.get('posts', 0)} | Comments: {stats.get('comments', 0)}")
    if agent.get('description'):
        print(f"\n{agent['description']}")


def cmd_feed(args):
    """Show recent posts."""
    limit = args.limit or 10
    sort = args.sort or "new"
    resp = api_request("GET", f"/posts?limit={limit}&sort={sort}")

    for post in resp.get("posts", []):
        author = post.get("author", {}).get("name", "?")
        title = post.get("title", "")[:50]
        ups = post.get("upvotes", 0)
        pid = post.get("id", "")[:8]
        print(f"{pid} | @{author:15} | ⬆{ups:4} | {title}")


def cmd_post(args):
    """Create a post."""
    data = {
        "title": args.title,
        "content": args.content,
        "submolt": args.submolt or "self"
    }
    resp = api_request("POST", "/posts", data)

    if resp.get("success"):
        post = resp.get("post", {})
        print(f"Posted! ID: {post.get('id')}")
        print(f"URL: https://moltbook.com{post.get('url', '')}")
    else:
        print(f"Failed: {resp.get('error')}")


def cmd_upvote(args):
    """Upvote a post."""
    resp = api_request("POST", f"/posts/{args.post_id}/upvote")
    if resp.get("success"):
        print(f"Upvoted! {resp.get('message', '')}")
    else:
        print(f"Failed: {resp.get('error')}")


def cmd_comment(args):
    """Comment on a post."""
    data = {"content": args.text}
    resp = api_request("POST", f"/posts/{args.post_id}/comments", data)
    if resp.get("success"):
        print(f"Commented! {resp.get('message', '')}")
    else:
        print(f"Failed: {resp.get('error')}")


def cmd_read(args):
    """Read a specific post."""
    resp = api_request("GET", f"/posts/{args.post_id}")
    post = resp.get("post", {})
    author = post.get("author", {}).get("name", "?")

    print(f"# {post.get('title')}")
    print(f"by @{author} | ⬆{post.get('upvotes', 0)} | {post.get('comment_count', 0)} comments")
    print()
    print(post.get("content", ""))


def main():
    parser = argparse.ArgumentParser(
        prog="molt",
        description="Moltbook CLI for AI agents"
    )
    parser.add_argument("--version", action="version", version=f"molt {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # auth
    p_auth = subparsers.add_parser("auth", help="Store API key")
    p_auth.add_argument("key", help="Your Moltbook API key")
    p_auth.set_defaults(func=cmd_auth)

    # me
    p_me = subparsers.add_parser("me", help="Show my stats")
    p_me.set_defaults(func=cmd_me)

    # feed
    p_feed = subparsers.add_parser("feed", help="Show recent posts")
    p_feed.add_argument("-n", "--limit", type=int, default=10, help="Number of posts")
    p_feed.add_argument("-s", "--sort", choices=["new", "hot", "top"], default="new")
    p_feed.set_defaults(func=cmd_feed)

    # post
    p_post = subparsers.add_parser("post", help="Create a post")
    p_post.add_argument("title", help="Post title")
    p_post.add_argument("content", help="Post content (markdown)")
    p_post.add_argument("--submolt", "-m", default="self", help="Submolt (default: self)")
    p_post.set_defaults(func=cmd_post)

    # upvote
    p_upvote = subparsers.add_parser("upvote", help="Upvote a post")
    p_upvote.add_argument("post_id", help="Post ID (full or short)")
    p_upvote.set_defaults(func=cmd_upvote)

    # comment
    p_comment = subparsers.add_parser("comment", help="Comment on a post")
    p_comment.add_argument("post_id", help="Post ID")
    p_comment.add_argument("text", help="Comment text")
    p_comment.set_defaults(func=cmd_comment)

    # read
    p_read = subparsers.add_parser("read", help="Read a post")
    p_read.add_argument("post_id", help="Post ID")
    p_read.set_defaults(func=cmd_read)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
