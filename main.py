import ast
import json
import operator
import os
import time
from datetime import datetime, timezone
from typing import Literal
import urllib.error
import urllib.request
from collections import defaultdict, deque
from ddgs import DDGS
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel, Field

load_dotenv()

client = OpenAI(
    api_key=os.environ["LLM_API_KEY"],
    base_url=os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
)
MODEL = os.environ.get("LLM_MODEL", "openai/gpt-oss-20b")

SYSTEM_PROMPT = (
    "You are a helpful, honest, and friendly AI assistant. "
    "Answer clearly. Use simple words unless the user asks for depth. "
    "Use Markdown for lists and code blocks. "
    "You have tools: use calculator for maths, get_current_datetime for the "
    "current date or time, and web_search for recent news or facts you are "
    "not sure about. After searching, mention the website names you used. "
    "If you are not sure about something, say so instead of guessing."
)

app = FastAPI()
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]


def current_user(authorization: str = Header(default="")):
    """Asks Supabase: is this login token real? Returns the user, or stops with 401."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Please log in")
    req = urllib.request.Request(
        f"{SUPABASE_URL}/auth/v1/user",
        headers={"Authorization": authorization, "apikey": SUPABASE_KEY},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError:
        raise HTTPException(status_code=401, detail="Login expired")
    except Exception:
        raise HTTPException(status_code=503, detail="Login service unavailable")


# each user can send at most 15 messages per minute (protects your free limit)
hits = defaultdict(deque)


def check_rate(user_id: str):
    now = time.time()
    q = hits[user_id]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= 15:
        raise HTTPException(status_code=429, detail="Too many messages")
    q.append(now)

# ---------------------------------------------------------------
# TOOL 1: calculator (safe: it only allows numbers and + - * / ** %)
# ---------------------------------------------------------------
OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise ValueError("Exponent too big")
        return OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_eval(node.operand))
    raise ValueError("Unsupported expression")


def calculator(expression: str) -> str:
    try:
        return str(_eval(ast.parse(expression, mode="eval").body))
    except Exception as e:
        return f"Calculator error: {e}"


# ---------------------------------------------------------------
# TOOL 2: current date and time (in UTC)
# ---------------------------------------------------------------
def get_current_datetime() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%A, %d %B %Y, %H:%M UTC")


# ---------------------------------------------------------------
# TOOL 3: web search
# ---------------------------------------------------------------
def web_search(query: str) -> str:
    try:
        results = DDGS().text(query, max_results=5)
        if not results:
            return "No results found."
        return "\n\n".join(
            f"{r['title']}\n{r['body']}\nSource: {r['href']}" for r in results
        )
    except Exception as e:
        return f"Search failed: {e}"


# ---------------------------------------------------------------
# The "menu" that tells the AI which tools exist
# ---------------------------------------------------------------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Do maths. Input is an expression like '1234*5678' or '(5+3)/2'.",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_datetime",
            "description": "Get the current date and time.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the internet for recent news or facts.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
]

STATUS = {
    "calculator": "Calculating",
    "get_current_datetime": "Checking the time",
    "web_search": "Searching the web",
}


def run_tool(name: str, args: dict) -> str:
    if name == "calculator":
        return calculator(args.get("expression", ""))
    if name == "get_current_datetime":
        return get_current_datetime()
    if name == "web_search":
        return web_search(args.get("query", ""))
    return f"Unknown tool: {name}"


def typewriter(text: str):
    """Sends the answer in small pieces so it looks like typing."""
    for i in range(0, len(text), 6):
        yield text[i : i + 6]
        time.sleep(0.008)


# ---------------------------------------------------------------
# The agent loop: ask AI -> maybe use tools -> ask again -> answer
# ---------------------------------------------------------------
def agent(history):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    for _ in range(5):  # at most 5 rounds, so it can never loop forever
        response = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS
        )
        msg = response.choices[0].message

        if not msg.tool_calls:  # no tool needed, this is the final answer
            yield from typewriter(msg.content or "")
            return

        # the AI asked to use tools: remember that request
        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
        )

        # run each tool and give the result back to the AI
        for tc in msg.tool_calls:
            name = tc.function.name
            yield f"*🔧 {STATUS.get(name, name)}...*\n\n"
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = run_tool(name, args)
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": result}
            )

    yield "Sorry, that took too many steps. Please try a simpler question."


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ChatRequest(BaseModel):
    messages: list[Message]


@app.post("/api/chat")
def chat(req: ChatRequest, user=Depends(current_user)):
    check_rate(user["id"])
    history = [m.model_dump() for m in req.messages[-20:]]

    def stream():
        try:
            yield from agent(history)
        except Exception as e:
            print("LLM error:", repr(e))
            yield "\n\n⚠️ Error: " + repr(e)[:300]

    return StreamingResponse(stream(), media_type="text/plain; charset=utf-8")


app.mount("/", StaticFiles(directory="static", html=True), name="static")