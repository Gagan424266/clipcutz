"""A clip that was already posted can be sent again, and a second click while one is on its way is ignored.

Runs against the code directly, with its own empty data folder."""
import os, sys, tempfile
os.environ["CLIPCUTZ_DATA"] = tempfile.mkdtemp(prefix="pc-repost-")
sys.path.insert(0, ".")
from unittest.mock import patch
from studio import ctx, posting

fails = []
def check(n, got, want=True):
    ok = want(got) if callable(want) else got == want
    print(("PASS " if ok else "FAIL ") + n + ("" if ok else f"   got {got!r}")); ok or fails.append(n)

job = {"id": "job1", "creator": None, "clips": [{"id": "clip01"}]}
clip = job["clips"][0]
acc = {"id": "yt_1", "name": "Gagan", "platform": "youtube"}

with ctx.as_user("u_test"):
    with patch.object(posting.accounts, "get", return_value=acc), patch.object(posting, "_mirror"):
        posting._posts.clear()
        first = posting.enqueue(job, clip, ["yt_1"], now=True)
        check("the first post is queued", len(first), 1)
        check("a second click while it is waiting does nothing", len(posting.enqueue(job, clip, ["yt_1"], now=True)), 0)
        first[0]["status"] = "posted"
        check("a finished post is not sent twice on its own", len(posting.enqueue(job, clip, ["yt_1"], now=True)), 0)
        again = posting.enqueue(job, clip, ["yt_1"], now=True, again=True)
        check("post again queues a new one", len(again), 1)
        check("the old post is no longer the current one", first[0]["status"], "replaced")
        check("post again does not stack a second one while the new one is waiting",
              len(posting.enqueue(job, clip, ["yt_1"], now=True, again=True)), 0)

with ctx.as_user("u_test"):
    with patch.object(posting.accounts, "get", return_value=acc), patch.object(posting, "_mirror"):
        posting._posts.clear()
        spaced = posting.enqueue(job, clip, ["yt_1"], now=True)
        nxt = posting.enqueue(job, {"id": "clip02"}, ["yt_1"], now=True)
        check("the next clip waits 10 seconds", nxt[0]["due_at"] - spaced[0]["due_at"] >= 9)

import time
boom = RuntimeError('400 uploadLimitExceeded The user has exceeded the number of videos they may upload.')
waiting = {"id": "p2", "user": "u_test", "job": "job1", "clip": "clip02", "creator": None,
           "account": "yt_1", "account_name": "Gagan", "platform": "youtube", "status": "scheduled",
           "due_at": time.time(), "title": "Two", "tries": 0, "error": None}
held = {"id": "p1", "user": "u_test", "job": "job1", "clip": "clip01", "creator": None,
        "account": "yt_1", "account_name": "Gagan", "platform": "youtube", "status": "posting",
        "due_at": time.time(), "title": "One", "tries": 0, "error": None}
full = {"id": "job1", "creator": None, "dir": "/tmp", "clips": [
    {"id": "clip01", "status": "done", "file": "a.mp4", "title": "T", "description": "", "hashtags": []},
    {"id": "clip02", "status": "done", "file": "b.mp4", "title": "U", "description": "", "hashtags": []}]}
with ctx.as_user("u_test"):
    posting._posts[:] = [held, waiting]
    with patch.object(posting.jobs, "get", return_value=full), patch.object(posting.accounts, "get", return_value=acc), \
            patch.object(posting.accounts, "youtube_upload", side_effect=boom), patch.object(posting, "_mirror"):
        posting._post(held)
check("YouTube's daily limit is explained in plain words", "today" in held["error"])
check("the other clips wait hours instead of failing immediately", waiting["due_at"] > time.time() + 3600)
check("the daily limit does not use up the retries", held["tries"], 0)

print("ALL PASSED" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
