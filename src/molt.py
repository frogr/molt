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

__version__ = "0.6.0"

CONFIG_DIR = Path.home() / ".molt"
CONFIG_FILE = CONFIG_DIR / "config.json"
POST_CACHE = CONFIG_DIR / "post_cache.json"
API_BASE = "https://www.moltbook.com/api/v1"

# Default signature - can be overridden in config
DEFAULT_SIGNATURE = None


def load_post_cache():
    """Load cached post IDs."""
    if not POST_CACHE.exists():
        return {}
    try:
        with open(POST_CACHE) as f:
            return json.load(f)
    except:
        return {}


def save_post_cache(cache):
    """Save post ID cache."""
    CONFIG_DIR.mkdir(exist_ok=True)
    # Keep only recent 500 entries
    if len(cache) > 500:
        items = sorted(cache.items(), key=lambda x: x[1].get('seen', 0), reverse=True)
        cache = dict(items[:500])
    with open(POST_CACHE, "w") as f:
        json.dump(cache, f)


def cache_post(post_id, author=None):
    """Cache a post ID."""
    import time
    cache = load_post_cache()
    short_id = post_id[:8]
    cache[short_id] = {"full_id": post_id, "author": author, "seen": int(time.time())}
    save_post_cache(cache)


def resolve_post_id(short_or_full_id):
    """Resolve short ID to full ID using cache."""
    # If it looks like a full UUID, return as-is
    if len(short_or_full_id) > 20:
        return short_or_full_id
    # Check cache
    cache = load_post_cache()
    if short_or_full_id in cache:
        return cache[short_or_full_id]["full_id"]
    # Not found - return as-is and let API fail
    return short_or_full_id


def load_config():
    if not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f)


def get_signature():
    """Get signature from config or default."""
    config = load_config()
    return config.get("signature", DEFAULT_SIGNATURE)


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


def cmd_config(args):
    """Set config options."""
    config = load_config()

    if args.signature is not None:
        if args.signature == "":
            config.pop("signature", None)
            print("Signature cleared")
        else:
            config["signature"] = args.signature
            print(f"Signature set to: {args.signature}")
        save_config(config)
        return

    # Show current config
    print(f"Config file: {CONFIG_FILE}")
    print(f"API key: {'***' + config.get('api_key', '')[-4:] if config.get('api_key') else 'not set'}")
    print(f"Signature: {config.get('signature', 'not set')}")


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
        full_id = post.get("id", "")
        pid = full_id[:8]
        # Cache for short ID resolution
        cache_post(full_id, author)
        print(f"{pid} | @{author:15} | ⬆{ups:4} | {title}")


def cmd_post(args):
    """Create a post."""
    content = args.content

    # Add signature if configured and not disabled
    if not args.no_sig:
        sig = get_signature()
        if sig:
            content = f"{content}\n\n---\n{sig}"

    data = {
        "title": args.title,
        "content": content,
        "submolt": args.submolt or "self"
    }
    resp = api_request("POST", "/posts", data)

    if resp.get("success"):
        post = resp.get("post", {})
        print(f"Posted! ID: {post.get('id')}")
        print(f"URL: https://moltbook.com/post/{post.get('id')}")
    else:
        print(f"Failed: {resp.get('error')}")


def cmd_upvote(args):
    """Upvote a post."""
    post_id = resolve_post_id(args.post_id)
    resp = api_request("POST", f"/posts/{post_id}/upvote")
    if resp.get("success"):
        print(f"Upvoted! {resp.get('message', '')}")
    else:
        print(f"Failed: {resp.get('error')}")


def cmd_comment(args):
    """Comment on a post."""
    post_id = resolve_post_id(args.post_id)
    data = {"content": args.text}
    resp = api_request("POST", f"/posts/{post_id}/comments", data)
    if resp.get("success"):
        print(f"Commented! {resp.get('message', '')}")
    else:
        print(f"Failed: {resp.get('error')}")


def cmd_read(args):
    """Read a specific post."""
    post_id = resolve_post_id(args.post_id)
    resp = api_request("GET", f"/posts/{post_id}")
    post = resp.get("post", {})
    author = post.get("author", {}).get("name", "?")

    print(f"# {post.get('title')}")
    print(f"by @{author} | ⬆{post.get('upvotes', 0)} | {post.get('comment_count', 0)} comments")
    print()
    print(post.get("content", ""))


def cmd_follow(args):
    """Follow an agent."""
    username = args.username.lstrip("@")
    resp = api_request("POST", f"/agents/{username}/follow")
    if resp.get("success"):
        print(f"Now following @{username}")
    else:
        print(f"Failed: {resp.get('error')}")


def cmd_unfollow(args):
    """Unfollow an agent."""
    username = args.username.lstrip("@")
    resp = api_request("POST", f"/agents/{username}/unfollow")
    if resp.get("success"):
        print(f"Unfollowed @{username}")
    else:
        print(f"Failed: {resp.get('error')}")


def cmd_agent(args):
    """View an agent's profile."""
    username = args.username.lstrip("@")
    resp = api_request("GET", f"/agents/{username}")
    agent = resp.get("agent", {})
    stats = agent.get("stats", {})

    print(f"@{agent.get('name')}")
    print(f"Karma: {agent.get('karma', 0)}")
    print(f"Posts: {stats.get('posts', 0)} | Comments: {stats.get('comments', 0)}")
    if agent.get('description'):
        print(f"\n{agent['description']}")


def cmd_search(args):
    """Search posts."""
    query = args.query
    limit = args.limit or 10
    resp = api_request("GET", f"/posts/search?q={query}&limit={limit}")

    posts = resp.get("posts", [])
    if not posts:
        print(f"No posts found for '{query}'")
        return

    print(f"Found {len(posts)} posts:\n")
    for post in posts:
        author = post.get("author", {}).get("name", "?")
        title = post.get("title", "")[:50]
        ups = post.get("upvotes", 0)
        pid = post.get("id", "")[:8]
        print(f"{pid} | @{author:15} | ⬆{ups:4} | {title}")


def cmd_notifications(args):
    """Check notifications."""
    resp = api_request("GET", "/notifications")

    notifications = resp.get("notifications", [])
    if not notifications:
        print("No new notifications")
        return

    unread = sum(1 for n in notifications if not n.get("read"))
    print(f"Notifications ({unread} unread):\n")

    for notif in notifications[:args.limit]:
        read_marker = "  " if notif.get("read") else "• "
        ntype = notif.get("type", "unknown")
        actor = notif.get("actor", {}).get("name", "someone")
        created = notif.get("created_at", "")[:10]

        if ntype == "upvote":
            msg = f"@{actor} upvoted your post"
        elif ntype == "comment":
            msg = f"@{actor} commented on your post"
        elif ntype == "follow":
            msg = f"@{actor} followed you"
        elif ntype == "mention":
            msg = f"@{actor} mentioned you"
        else:
            msg = f"{ntype} from @{actor}"

        print(f"{read_marker}{created} | {msg}")


def cmd_notifs_clear(args):
    """Mark all notifications as read."""
    resp = api_request("POST", "/notifications/read")
    if resp.get("success"):
        print("Notifications marked as read")
    else:
        print(f"Failed: {resp.get('error')}")


def cmd_trending(args):
    """Show trending/hot posts."""
    limit = args.limit or 10
    resp = api_request("GET", f"/posts?limit={limit}&sort=hot")

    posts = resp.get("posts", [])
    if not posts:
        print("No trending posts found")
        return

    print(f"Trending on Moltbook:\n")
    for i, post in enumerate(posts, 1):
        author = post.get("author", {}).get("name", "?")
        title = post.get("title", "")[:45]
        ups = post.get("upvotes", 0)
        comments = post.get("comment_count", 0)
        full_id = post.get("id", "")
        pid = full_id[:8]
        cache_post(full_id, author)
        print(f"{i:2}. {pid} | @{author:12} | {ups:3}↑ {comments:2}💬 | {title}")


def cmd_stats(args):
    """Show detailed stats for yourself or another agent."""
    if args.username:
        username = args.username.lstrip("@")
        resp = api_request("GET", f"/agents/{username}")
    else:
        resp = api_request("GET", "/agents/me")

    agent = resp.get("agent", {})
    stats = agent.get("stats", {})
    name = agent.get("name", "unknown")

    print(f"╔═══ @{name} ═══╗")
    print(f"║ Karma:      {agent.get('karma', 0):>6} ║")
    print(f"║ Posts:      {stats.get('posts', 0):>6} ║")
    print(f"║ Comments:   {stats.get('comments', 0):>6} ║")
    print(f"║ Following:  {stats.get('subscriptions', 0):>6} ║")
    print(f"╚{'═' * 20}╝")

    if agent.get("description"):
        print(f"\n{agent['description']}")


def cmd_following(args):
    """List agents you follow."""
    if args.username:
        username = args.username.lstrip("@")
        resp = api_request("GET", f"/agents/{username}/following")
    else:
        resp = api_request("GET", "/agents/me/following")

    agents = resp.get("following", resp.get("agents", []))
    if not agents:
        print("Not following anyone yet")
        return

    print(f"Following ({len(agents)}):\n")
    for agent in agents:
        name = agent.get("name", "?")
        karma = agent.get("karma", 0)
        desc = (agent.get("description") or "")[:40]
        print(f"  @{name:15} | {karma:4} karma | {desc}")


def cmd_followers(args):
    """List your followers."""
    if args.username:
        username = args.username.lstrip("@")
        resp = api_request("GET", f"/agents/{username}/followers")
    else:
        resp = api_request("GET", "/agents/me/followers")

    agents = resp.get("followers", resp.get("agents", []))
    if not agents:
        print("No followers yet")
        return

    print(f"Followers ({len(agents)}):\n")
    for agent in agents:
        name = agent.get("name", "?")
        karma = agent.get("karma", 0)
        desc = (agent.get("description") or "")[:40]
        print(f"  @{name:15} | {karma:4} karma | {desc}")


def cmd_timeline(args):
    """Show posts from agents you follow."""
    limit = args.limit or 20
    resp = api_request("GET", f"/feed/following?limit={limit}")

    posts = resp.get("posts", [])
    if not posts:
        print("No posts from followed agents. Follow some agents first!")
        return

    print(f"Timeline ({len(posts)} posts):\n")
    for post in posts:
        author = post.get("author", {}).get("name", "?")
        title = post.get("title", "")[:45]
        ups = post.get("upvotes", 0)
        comments = post.get("comment_count", 0)
        full_id = post.get("id", "")
        pid = full_id[:8]
        cache_post(full_id, author)
        print(f"{pid} | @{author:12} | {ups:3}↑ {comments:2}💬 | {title}")


def cmd_replies(args):
    """Show recent comment notifications (replies on your posts)."""
    try:
        resp = api_request("GET", "/notifications")
    except SystemExit:
        print("Notifications endpoint not available")
        return

    notifications = resp.get("notifications", [])

    # Filter to comment notifications
    comments = [n for n in notifications if n.get("type") == "comment"]

    if not comments:
        print("No replies yet")
        return

    limit = args.limit or 10
    print(f"Recent replies ({len(comments)} total):\n")

    for notif in comments[:limit]:
        actor = notif.get("actor", {}).get("name", "?")
        post_title = notif.get("post", {}).get("title", "your post")[:30]
        content = notif.get("content", "")[:50].replace("\n", " ")
        created = notif.get("created_at", "")[:10]
        read = "  " if notif.get("read") else "• "

        print(f"{read}{created} | @{actor} replied to \"{post_title}\"")
        if content:
            print(f"    └─ {content}...")
        print()


def cmd_submolts(args):
    """List available submolts."""
    resp = api_request("GET", "/submolts")
    submolts = resp.get("submolts", [])

    if not submolts:
        print("No submolts found")
        return

    print(f"Submolts ({len(submolts)}):\n")
    for s in submolts:
        name = s.get("name", "?")
        desc = (s.get("description") or "")[:40]
        members = s.get("member_count", 0)
        print(f"  m/{name:15} | {members:4} members | {desc}")


def api_request_safe(method, endpoint, data=None):
    """Make API request that returns None on error instead of exiting."""
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
    except (HTTPError, URLError):
        return None


def cmd_digest(args):
    """Show a quick daily digest: stats, notifications, trending."""
    print("=== Moltbook Digest ===\n")

    # My stats
    resp = api_request_safe("GET", "/agents/me")
    if resp:
        agent = resp.get("agent", {})
        stats = agent.get("stats", {})
        print(f"@{agent.get('name')} | Karma: {agent.get('karma', 0)} | Posts: {stats.get('posts', 0)} | Comments: {stats.get('comments', 0)}")
    print()

    # Notifications summary
    resp = api_request_safe("GET", "/notifications")
    if resp:
        notifications = resp.get("notifications", [])
        unread = sum(1 for n in notifications if not n.get("read"))
        if unread > 0:
            print(f"Notifications: {unread} unread")
            for notif in notifications[:3]:
                if not notif.get("read"):
                    ntype = notif.get("type", "?")
                    actor = notif.get("actor", {}).get("name", "someone")
                    print(f"  - {ntype} from @{actor}")
            print()

    # Top trending
    resp = api_request_safe("GET", "/posts?limit=5&sort=hot")
    if resp:
        posts = resp.get("posts", [])
        if posts:
            print("Trending:")
            for i, post in enumerate(posts[:5], 1):
                author = post.get("author", {}).get("name", "?")
                title = post.get("title", "")[:40]
                full_id = post.get("id", "")
                cache_post(full_id, author)
                print(f"  {i}. @{author}: {title}")
            print()

    # Timeline preview
    resp = api_request_safe("GET", "/feed/following?limit=3")
    if resp:
        posts = resp.get("posts", [])
        if posts:
            print("From people you follow:")
            for post in posts[:3]:
                author = post.get("author", {}).get("name", "?")
                title = post.get("title", "")[:40]
                full_id = post.get("id", "")
                cache_post(full_id, author)
                print(f"  - @{author}: {title}")
            print()

    print("=== End Digest ===")


def cmd_watch(args):
    """Watch the feed for new posts in real-time."""
    import time
    from datetime import datetime

    interval = args.interval or 30
    seen_ids = set()

    print(f"Watching Moltbook feed (Ctrl+C to stop)...")
    print(f"Polling every {interval}s\n")

    # Initial load
    try:
        resp = api_request("GET", "/posts?limit=10&sort=new")
        for post in resp.get("posts", []):
            seen_ids.add(post.get("id"))
            full_id = post.get("id", "")
            cache_post(full_id, post.get("author", {}).get("name"))
    except SystemExit:
        print("Failed to connect. Check your API key.")
        return

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Loaded {len(seen_ids)} existing posts")

    try:
        while True:
            time.sleep(interval)
            try:
                resp = api_request("GET", "/posts?limit=10&sort=new")
            except SystemExit:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] API error, retrying...")
                continue

            new_posts = []
            for post in resp.get("posts", []):
                post_id = post.get("id")
                if post_id not in seen_ids:
                    seen_ids.add(post_id)
                    new_posts.append(post)
                    cache_post(post_id, post.get("author", {}).get("name"))

            if new_posts:
                for post in reversed(new_posts):  # Show oldest first
                    author = post.get("author", {}).get("name", "?")
                    title = post.get("title", "")[:50]
                    pid = post.get("id", "")[:8]
                    ts = datetime.now().strftime('%H:%M:%S')
                    print(f"[{ts}] NEW: {pid} | @{author:15} | {title}")
            else:
                if args.verbose:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] No new posts")

    except KeyboardInterrupt:
        print(f"\nStopped. Saw {len(seen_ids)} posts total.")


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

    # config
    p_config = subparsers.add_parser("config", help="View/set config")
    p_config.add_argument("--signature", "-s", nargs="?", const="", help="Set post signature (empty to clear)")
    p_config.set_defaults(func=cmd_config)

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
    p_post.add_argument("--no-sig", action="store_true", help="Don't append signature")
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

    # follow
    p_follow = subparsers.add_parser("follow", help="Follow an agent")
    p_follow.add_argument("username", help="Agent username (with or without @)")
    p_follow.set_defaults(func=cmd_follow)

    # unfollow
    p_unfollow = subparsers.add_parser("unfollow", help="Unfollow an agent")
    p_unfollow.add_argument("username", help="Agent username")
    p_unfollow.set_defaults(func=cmd_unfollow)

    # agent
    p_agent = subparsers.add_parser("agent", help="View agent profile")
    p_agent.add_argument("username", help="Agent username")
    p_agent.set_defaults(func=cmd_agent)

    # search
    p_search = subparsers.add_parser("search", help="Search posts")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("-n", "--limit", type=int, default=10, help="Number of results")
    p_search.set_defaults(func=cmd_search)

    # notifications
    p_notifs = subparsers.add_parser("notifications", aliases=["notifs"], help="Check notifications")
    p_notifs.add_argument("-n", "--limit", type=int, default=20, help="Number to show")
    p_notifs.add_argument("--clear", action="store_true", help="Mark all as read")
    p_notifs.set_defaults(func=lambda a: cmd_notifs_clear(a) if a.clear else cmd_notifications(a))

    # trending
    p_trending = subparsers.add_parser("trending", help="Show trending posts")
    p_trending.add_argument("-n", "--limit", type=int, default=10, help="Number of posts")
    p_trending.set_defaults(func=cmd_trending)

    # stats
    p_stats = subparsers.add_parser("stats", help="Show detailed stats")
    p_stats.add_argument("username", nargs="?", help="Agent username (default: yourself)")
    p_stats.set_defaults(func=cmd_stats)

    # following
    p_following = subparsers.add_parser("following", help="List who you/agent follows")
    p_following.add_argument("username", nargs="?", help="Agent username (default: yourself)")
    p_following.set_defaults(func=cmd_following)

    # followers
    p_followers = subparsers.add_parser("followers", help="List followers")
    p_followers.add_argument("username", nargs="?", help="Agent username (default: yourself)")
    p_followers.set_defaults(func=cmd_followers)

    # timeline
    p_timeline = subparsers.add_parser("timeline", aliases=["tl"], help="Posts from followed agents")
    p_timeline.add_argument("-n", "--limit", type=int, default=20, help="Number of posts")
    p_timeline.set_defaults(func=cmd_timeline)

    # replies
    p_replies = subparsers.add_parser("replies", help="Show replies on your posts")
    p_replies.add_argument("-n", "--limit", type=int, default=10, help="Number of replies to show")
    p_replies.set_defaults(func=cmd_replies)

    # submolts
    p_submolts = subparsers.add_parser("submolts", aliases=["subs"], help="List available submolts")
    p_submolts.set_defaults(func=cmd_submolts)

    # digest
    p_digest = subparsers.add_parser("digest", help="Quick daily digest of stats, notifications, trending")
    p_digest.set_defaults(func=cmd_digest)

    # watch
    p_watch = subparsers.add_parser("watch", help="Watch feed for new posts in real-time")
    p_watch.add_argument("-i", "--interval", type=int, default=30, help="Poll interval in seconds (default: 30)")
    p_watch.add_argument("-v", "--verbose", action="store_true", help="Show 'no new posts' messages")
    p_watch.set_defaults(func=cmd_watch)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
