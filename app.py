"""
LINE公式アカウント Webhookサーバー
グループチャットのメッセージを受信してテキストファイルに保存する
"""

import os
import json
import hashlib
import hmac
import base64
from datetime import datetime, timezone, timedelta
from flask import Flask, request, abort

app = Flask(__name__)

CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")

JST = timezone(timedelta(hours=9))

LOG_DIR = os.environ.get("LOG_DIR", "logs")
os.makedirs(LOG_DIR, exist_ok=True)


def verify_signature(body, signature):
    hash_value = hmac.new(CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(hash_value).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def get_log_filepath(group_id, timestamp):
    date_str = timestamp.strftime("%Y-%m-%d")
    safe_group_id = group_id[:16] if group_id else "direct"
    return os.path.join(LOG_DIR, f"{date_str}_{safe_group_id}.txt")


def save_message(event):
    ts = event.get("timestamp", 0)
    dt = datetime.fromtimestamp(ts / 1000, tz=JST)
    time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    source = event.get("source", {})
    group_id = source.get("groupId", "direct")
    user_id = source.get("userId", "unknown")
    message = event.get("message", {})
    msg_type = message.get("type", "unknown")

    if msg_type == "text":
        content = message.get("text", "")
    elif msg_type == "image":
        content = "[画像]"
    elif msg_type == "video":
        content = "[動画]"
    elif msg_type == "audio":
        content = "[音声]"
    elif msg_type == "file":
        content = f"[ファイル: {message.get('fileName', '不明')}]"
    elif msg_type == "sticker":
        content = "[スタンプ]"
    elif msg_type == "location":
        content = f"[位置情報: {message.get('title', '')} {message.get('address', '')}]"
    else:
        content = f"[{msg_type}]"

    filepath = get_log_filepath(group_id, dt)
    line_text = f"[{time_str}] user:{user_id[:8]}  {content}\n"
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(line_text)
    print(f"Saved: {filepath} | {line_text.strip()}")


def handle_join_event(event):
    source = event.get("source", {})
    group_id = source.get("groupId", "unknown")
    dt = datetime.now(JST)
    filepath = get_log_filepath(group_id, dt)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(f"[{dt.strftime('%Y-%m-%d %H:%M:%S')}] === Bot joined group ===\n")
    print(f"Joined group: {group_id}")


@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_data()
    signature = request.headers.get("X-Line-Signature", "")
    if CHANNEL_SECRET and not verify_signature(body, signature):
        abort(403)
    data = json.loads(body)
    events = data.get("events", [])
    for event in events:
        event_type = event.get("type", "")
        if event_type == "message":
            save_message(event)
        elif event_type == "join":
            handle_join_event(event)
    return "OK", 200


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "service": "LINE Webhook Server"}, 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"LINE Webhook Server starting on port {port}")
    app.run(host="0.0.0.0", port=port)
