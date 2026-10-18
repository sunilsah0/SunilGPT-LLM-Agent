
# SunilGPT-LLMChat

A free, open-source AI chat assistant that runs in the browser, in the style of ChatGPT and Claude. It streams answers, can use tools (calculator, date and time, web search), can answer questions about your own files, and works for guests as well as logged-in users.

**Live demo:** https://sunilgpt-llm-agent.onrender.com
**Source code:** https://github.com/sunilsah0/SunilGPT-LLM-Agent

> The demo runs on free hosting. If nobody has used it for a while, the first message can take about 30 seconds while the server wakes up.

---

## Features

- **Streaming chat** with Markdown, code blocks and tables
- **Agent tools:** calculator, current date and time, and web search (the AI decides when to use them)
- **Chat with your files:** attach a PDF, `.txt` or `.md` file and ask questions about it
- **Smarter file search:** keyword search (BM25) improved by asking the AI for related words
- **Optional login:** chat as a guest, or sign up to save chats online on all devices
- **Multiple chats** in a sidebar, with Copy and Regenerate buttons and a Stop button
- **Guest and user limits** to protect the free AI quota
- **Light and dark mode**, and a layout that works on phones

---

## How it works

```
Browser (static/index.html)
   |  1. user sends a message (with a login token if logged in)
   v
FastAPI server (main.py)
   |  2. checks the login token with Supabase (guests are allowed)
   |  3. applies rate limits
   |  4. finds the best parts of any attached files
   |  5. runs the agent loop: ask the AI -> use tools if needed -> answer
   v
Free LLM API (Groq, OpenAI-compatible)
```

- **Frontend:** one HTML file with plain JavaScript (no build step)
- **Backend:** FastAPI (Python), serves the page and the API
- **AI model:** any OpenAI-compatible provider. The default is Groq with `openai/gpt-oss-20b`
- **Login and database:** Supabase (email and password login, one `chats` table protected by Row Level Security)
- **Hosting:** Render (free web service)

---

## Project structure

```
SunilGPT-LLM-Agent/
├── main.py             # backend: login check, limits, tools, file search, agent loop
├── requirements.txt    # Python packages
├── .env.example        # template for your secret settings
├── .gitignore          # keeps .env and venv out of GitHub
├── README.md           # this file
└── static/
    └── index.html      # the whole chat screen
```

---

## Run it on your computer

### 1. Requirements

- Python 3.12 (3.11 or newer should also work)
- A free Groq API key (https://console.groq.com)
- A free Supabase project (https://supabase.com), see [Supabase setup](#supabase-setup)

### 2. Download and install

```bash
git clone https://github.com/sunilsah0/SunilGPT-LLM-Agent.git
cd SunilGPT-LLM-Agent

python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Mac / Linux

pip install -r requirements.txt
```

### 3. Add your settings

Copy `.env.example` to a new file named `.env` and fill it in:

```
LLM_API_KEY=your-groq-key
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=openai/gpt-oss-20b

SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-supabase-publishable-key
```

Free model names change from time to time. If you get a "model not found" error, check the provider's website for a current model name.

Also open `static/index.html`, find `SUPABASE_URL` and `SUPABASE_KEY` near the top of the script, and paste the same two values. They are meant to be public (the database rules protect the data).

### 4. Start it

```bash
uvicorn main:app --reload
```

Open http://127.0.0.1:8000

---

## Supabase setup

1. Create a free project at supabase.com.
2. Open **SQL Editor**, paste this and click **Run**:

```sql
create table public.chats (
  id uuid primary key,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  title text not null default 'New chat',
  messages jsonb not null default '[]'::jsonb,
  docs jsonb not null default '[]'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.chats enable row level security;

create policy "read own chats" on public.chats
  for select to authenticated using ((select auth.uid()) = user_id);

create policy "add own chats" on public.chats
  for insert to authenticated with check ((select auth.uid()) = user_id);

create policy "edit own chats" on public.chats
  for update to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

create policy "delete own chats" on public.chats
  for delete to authenticated using ((select auth.uid()) = user_id);

create index on public.chats (user_id, updated_at desc);
```

3. Under **Authentication**, open the Email sign-in settings. For testing you can turn **Confirm email** off. Supabase's free email sending is limited, and a public app should later use its own email service.
4. Under **Authentication, URL Configuration**, set the **Site URL** to your live address.
5. Under **Project Settings, API**, copy the **Project URL** and the **publishable key**.

> Never use the `secret` or `service_role` key in this project, and never put it in `index.html`.

---

## Deploy for free on Render

1. Push your code to GitHub (`.env` must **not** be uploaded; `.gitignore` already blocks it).
2. On render.com choose **New, Web Service** and connect your repository.
3. Use these settings:

| Setting       | Value                                            |
| ------------- | ------------------------------------------------ |
| Build Command | `pip install -r requirements.txt`              |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Instance Type | Free                                             |

4. Add these **environment variables** (same values as your `.env`, without quotes):

`LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `SUPABASE_URL`, `SUPABASE_KEY`, and `PYTHON_VERSION` (for example `3.12.8`).

5. Deploy. Render gives you a public address. Every `git push` to the main branch redeploys automatically.

For debugging only, you can add `DEBUG_ERRORS=1` to show technical errors in the chat. Remove it before sharing the app.

---

## Share it with friends

**The easy way: send the link.**

1. Copy your live address: https://sunilgpt-llm-agent.onrender.com
2. Send it by message, email or social media. Anyone can open it and start chatting, no account needed.

**Tips for sharing**

- **Guests vs accounts:** guests can chat and attach `.txt` and `.md` files, and their chats stay only in their own browser. Friends who sign up get saved chats on all their devices and PDF upload.
- **On a phone:** open the link, then use the browser menu and choose **Add to Home Screen** for an app-like icon.
- **QR code:** make a free QR code for the link (many free QR generators exist) and print it or show it on a slide.
- **First message is slow?** The free server sleeps when idle and needs about 30 seconds to wake up. A free uptime monitor (for example UptimeRobot) that opens `/health` every 5 minutes keeps it awake.
- **Shared limits:** everyone shares one free AI quota. Guests get 8 messages per minute and 40 per day, logged-in users get 15 per minute and 300 per day, and all guests together get 500 per day. You can change these in `main.py` (`LIMITS`, `GUEST_DAILY_TOTAL`).
- **Privacy:** messages go to the AI provider, and chats and files of logged-in users are stored in your Supabase database. Tell friends not to share private information.

**Share the code instead:** send the GitHub link. A friend can follow [Run it on your computer](#run-it-on-your-computer) and [Deploy for free on Render](#deploy-for-free-on-render) to host their own copy with their own free keys.

---

## Configuration reference

| Variable         | What it is                                               |
| ---------------- | -------------------------------------------------------- |
| `LLM_API_KEY`  | Your key from the AI provider (keep secret)              |
| `LLM_BASE_URL` | The provider's OpenAI-compatible address                 |
| `LLM_MODEL`    | The model name to use                                    |
| `SUPABASE_URL` | Your Supabase project address (starts with `https://`) |
| `SUPABASE_KEY` | Your Supabase publishable key                            |
| `DEBUG_ERRORS` | Set to `1` only while debugging                        |

Other providers that speak the same API (for example Google Gemini at `https://generativelanguage.googleapis.com/v1beta/openai/`) can be used by changing `LLM_BASE_URL`, `LLM_MODEL` and the key.

---

## Troubleshooting

| Problem                                                          | Fix                                                                                            |
| ---------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Buttons do nothing and the browser console shows `Invalid URL` | `SUPABASE_URL` in `index.html` must be the full address, like `https://xxxx.supabase.co` |
| `model_not_found`                                              | Change `LLM_MODEL` to a model your provider currently offers                                 |
| `KeyError: 'SUPABASE_URL'` on start                            | Add the variable to `.env` (or to Render's Environment page)                                 |
| Server error about `proxies` when starting                     | Upgrade the package: `pip install --upgrade openai`                                          |
| "Your login expired"                                             | Refresh the page and log in again                                                              |
| "Too many messages"                                              | You hit a rate limit. Wait a minute, or log in for higher limits                               |
| PDF says "No text found"                                         | The PDF is a scan (pictures of pages). Scanned PDFs are not supported                          |
| Search says "Search failed"                                      | The free web search is sometimes blocked or rate limited. Try again later                      |

---

## Security notes

- Keep `.env` private. If a key is ever uploaded by mistake, delete it at the provider and create a new one.
- The Supabase publishable key in `index.html` is public by design. Data is protected by Row Level Security, so each user can only read and change their own chats.
- The server checks every login token with Supabase before using the AI for a logged-in user.
- Rate limits are based on IP address and are best-effort. The shared daily cap for guests is the main protection for your free quota.
- The calculator tool only allows numbers and basic maths operators.

---

## Roadmap

- [ ] Model picker (switch between free models)
- [ ] Better summaries of long documents
- [ ] Image upload with a free vision model
- [ ] Voice input and spoken answers
- [ ] Meaning search with embeddings (Supabase pgvector)

---

## Built with

Python, FastAPI, Uvicorn, the OpenAI Python SDK (used with Groq), pypdf, ddgs, Supabase, marked, DOMPurify, and Render.

## License

Add a license of your choice (for example MIT) by creating a `LICENSE` file in this repository.
