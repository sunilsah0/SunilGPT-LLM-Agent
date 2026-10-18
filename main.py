import os
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel, Field

load_dotenv()  # reads the .env file on your computer

# This works with many free providers (Groq, Gemini, OpenRouter),
# because they all use the same "OpenAI-style" API.
client = OpenAI(
    api_key=os.environ["LLM_API_KEY"],
    base_url=os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
)
MODEL = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")

# This tells the AI how to behave. Change it to give your AI a personality.
SYSTEM_PROMPT = (
    "You are a helpful, honest, and friendly AI assistant. "
    "Answer clearly. Use simple words unless the user asks for depth. "
    "Use Markdown for lists and code blocks. "
    "If you are not sure about something, say so instead of guessing."
)

app = FastAPI()


class Message(BaseModel):
    role: Literal["user", "assistant"]  # people cannot sneak in "system" messages
    content: str = Field(max_length=8000)


class ChatRequest(BaseModel):
    messages: list[Message]


@app.post("/api/chat")
def chat(req: ChatRequest):
    # keep only the last 20 messages so requests stay small
    history = [m.model_dump() for m in req.messages[-20:]]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    def stream():
        try:
            response = client.chat.completions.create(
                model=MODEL, messages=messages, stream=True
            )
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            print("LLM error:", e)  # you can see this in your terminal
            yield "\n\n⚠️ Sorry, the AI is busy or the free limit was reached. Try again in a minute."

    return StreamingResponse(stream(), media_type="text/plain; charset=utf-8")


# shows the chat page (static/index.html) at the home address
app.mount("/", StaticFiles(directory="static", html=True), name="static")