# LangSmith Demo

A small script that reads traces from `traces.json` and posts them to a
[LangSmith](https://smith.langchain.com/) project. All traces are time-shifted
to fit within the last 23 hours so they show up as recent activity in the
LangSmith UI.

## Prerequisites

- Python 3.11+ (developed on Python 3.14)
- A [LangSmith](https://smith.langchain.com/) account and API key

## Setup

1. **Create and activate a virtual environment**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate        # macOS / Linux
   # .venv\Scripts\activate         # Windows (PowerShell)
   ```

2. **Install the required packages**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**

   Copy the example file and fill in your own values:

   ```bash
   cp .env.example .env
   ```

   Then edit `.env`:

   | Variable             | Description                                        |
   | -------------------- | -------------------------------------------------- |
   | `LANGSMITH_TRACING`  | Set to `true` to enable tracing                    |
   | `LANGSMITH_ENDPOINT` | LangSmith API endpoint                             |
   | `LANGSMITH_API_KEY`  | Your LangSmith API key                             |
   | `LANGSMITH_PROJECT`  | Project name for the traces                        |
   | `OPENAI_API_KEY`     | Your OpenAI API key                                |

   > **Note:** `.env` is git-ignored and should never be committed.

## Usage

With the virtual environment activated and `.env` configured, run:

```bash
python main.py
```

The script reads `traces.json`, compresses the trace timestamps into the last
23 hours, and posts each trace (with its spans and feedback) to the configured
LangSmith project.
