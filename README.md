# CodeDoodle

Draw a flowchart, binary tree or state diagram on paper. Take a photo. Get code you can run, plus a step-by-step trace of how it executes.

CodeDoodle sends the photo to **Gemma 4** (through the Gemini API) and gets back a Python or C++ program that implements the diagram, an example trace, and a list of anything it had to guess. You can edit the code, run it in the browser, and step through the trace one diagram element at a time. The whole website is a single Streamlit script.

![Sample sketch](samples/even_or_odd.png)

## How it works

```
 photo (upload or camera)
        │
        ▼
 streamlit_app.py ──► app/imaging.py   fix rotation, flatten, shrink
        │
        ▼
 app/llm.py ──► Gemma 4 via the Gemini API   (the ONE api key)
        │            reply: JSON with code, trace, doubts
        ▼
 page shows code + trace
        │
        └─ "Run" ──► app/runner.py   time- and memory-limited subprocess (Python or g++)
```

## The one API key

The project needs a single key: a **Gemini API key** from Google AI Studio. Gemma 4 is served through the same API, so there is nothing else to sign up for.

1. Open <https://aistudio.google.com/apikey> and sign in with a Google account.
2. Click **Create API key** and copy it.
3. Put it in `.env` as `GEMINI_API_KEY` (see Quick start). `.env` is in `.gitignore`; never commit it.

The free tier is rate-limited. Check AI Studio for the current limits.

Models (set with `GEMMA_MODEL`):

| Model ID | Use it when |
|---|---|
| `gemma-4-31b-it` (default) | you want the best reading of messy handwriting |
| `gemma-4-26b-a4b-it` | you want faster replies |

## Quick start

You need Python 3.10 or newer. For C++ you also need `g++`.

```bash
git clone <your-repo-url> codedoodle
cd codedoodle

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # Windows: copy .env.example .env
# open .env and paste your key after GEMINI_API_KEY=

streamlit run streamlit_app.py
```

Streamlit opens <http://localhost:8501>. Drop in `samples/even_or_odd.png` and press **Read my sketch**.

No key yet? Set `DEMO_MODE=1` in `.env`. Every photo then returns the same even/odd example, enough to try the code tabs, the Run button and the trace.

## How Streamlit works (read this once)

Streamlit **re-runs `streamlit_app.py` from top to bottom every time the user does something**: picks a file, clicks a button, edits a text box. Three ideas follow from that:

- **Widgets return values.** `st.file_uploader(...)` returns the file, `st.button(...)` returns `True` only on the run triggered by that click. There are no event handlers to write.
- **`st.session_state` is the memory.** A normal variable is rebuilt on every re-run, so anything that must survive is stored there: the model's answer (`ss.result`), the code, the last run output and the active trace step. This is why clicking **Next** in the trace does not call the model again: it only changes `ss.step`, and the page redraws from the saved answer.
- **A widget with a `key` is bound to `session_state[key]`.** The code editor uses `key="code"`, so after a successful read we set `ss.code = answer["code"]` and the editor shows it. What the user types flows back into `ss.code`, which the Run button uses.

## Project layout

```
codedoodle/
├── streamlit_app.py      The website: layout, buttons, tabs, trace stepper
├── .streamlit/
│   └── config.toml       Colours, upload limit
├── app/
│   ├── llm.py            Gemma call, JSON extraction, one retry
│   ├── prompts.py        The prompt that turns a diagram into code + trace
│   ├── imaging.py        Photo preparation
│   ├── runner.py         Limited execution of Python and C++
│   └── demo.py           Canned answer for DEMO_MODE
├── samples/              A ready-made test sketch
├── tests/                pytest suite
├── Dockerfile
├── requirements.txt
└── .env.example
```

## How it was built, step by step

1. **Prove the model call.** Gemma 4 accepts images through the Gemini API (`google-genai` SDK). One request carries the photo plus a text prompt; the reply is text.
2. **Ask for JSON.** `prompts.py` requests one JSON object: `diagram_type`, `title`, `summary`, `code`, `sample_stdin`, `trace[]`, `uncertainties[]`. `llm.py` parses it itself (`extract_json` strips code fences and chatter), normalises it, and retries once if it is not valid JSON.
3. **Prepare the photo.** `imaging.py` fixes phone rotation, puts transparent PNGs on white, and shrinks the long side to 1600 px.
4. **Run the code with limits.** `runner.py` uses a temp folder, a stripped environment (your key is not passed through), CPU, memory, file-size and process limits, a wall-clock timeout, capped output, and no network when the host allows `unshare -rn`.
5. **Build the page in `streamlit_app.py`.**
   - Left column: file upload (or camera), language choice, the **Read my sketch** button, then the title, summary and "Check these readings".
   - Right column: **View** tab (highlighted code) and **Edit** tab (plain text box), the input box, **Run** and the output.
   - Full width underneath: the trace, with Back and Next buttons, a progress bar, the active step in a bordered card, and a table of all steps.
6. **Style.** `.streamlit/config.toml` sets the colours; a short CSS block in the script adds the graph-paper background and the yellow button.
7. **Test.** `tests/` covers the runner, the reply parser and the image preparation.

## Drawing tips for better results

- Dark pen on plain white paper. Avoid lined paper and shadows.
- Fill the frame with the diagram and shoot straight on.
- Label every arrow out of a diamond (Yes/No, True/False).
- Write conditions in code-like form: `n % 2 == 0`, not "n is even".
- For trees, write the value inside each node and draw one line per child.

## Deploy for free on Streamlit Community Cloud

1. Push the repo to GitHub.
2. At <https://share.streamlit.io> choose **New app**, pick the repo and set the main file to `streamlit_app.py`.
3. Under **Advanced settings → Secrets**, paste:

   ```toml
   GEMINI_API_KEY = "your-key"
   ENABLE_RUN = "0"
   ```

Keep `ENABLE_RUN = "0"` on any public link (see Safety notes). Without it, anyone who finds the URL can run code on the server.

## Demo day tips

- Rehearse with 2 or 3 sketches you have already tested, and keep their photos on the laptop.
- Free-tier limits are per key. Do not let the whole team test against the same key right before your slot.
- Keep `DEMO_MODE=1` ready as a fallback if the Wi-Fi or the API fails, and tell the judges when you use it.
- Switch language mid-demo: the same sketch to Python, then to C++.
- The camera toggle lets you draw on paper and capture it live with the laptop webcam.

## Safety notes

`runner.py` is a guard rail for running on your own laptop, **not a security boundary**. Generated or edited code runs as the same OS user as the app and can read files that user can read. So:

- Do not expose a public app with execution on. Set `ENABLE_RUN=0` (the Run button then switches off).
- If you need public execution, move it to a separate service with no network and no secrets (Piston, Judge0, gVisor or Firecracker).
- The Dockerfile runs as a non-root user and takes the key from the environment. Never bake `.env` into an image.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Docker

```bash
docker build -t codedoodle .
docker run -p 8501:8501 -e GEMINI_API_KEY=your-key -e ENABLE_RUN=0 codedoodle
```

## Roadmap

- Highlight the active line in the editor while stepping through the trace.
- Draw the tree or graph the model read next to the code, so mistakes in the reading are easy to spot.
- More languages (Java, JavaScript).
- Ask the model to fix its code when it fails to compile.

## License

MIT
