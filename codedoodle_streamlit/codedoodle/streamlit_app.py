"""CodeDoodle: photograph a hand-drawn diagram, get code you can run.

Run with:  streamlit run streamlit_app.py
"""

import os
import sys
from pathlib import Path

# Automatically add the folder where streamlit_app.py lives to Python's search path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from dotenv import load_dotenv

load_dotenv()

import streamlit as st  # noqa: E402

from app import llm, runner  # noqa: E402
from app.imaging import prepare_image  # noqa: E402

st.set_page_config(page_title="CodeDoodle", layout="wide")

# Streamlit Community Cloud keeps keys in "secrets"; copy them into the environment
# so the rest of the code reads settings the same way everywhere.
for _name in ("GEMINI_API_KEY", "GEMMA_MODEL", "ENABLE_RUN", "DEMO_MODE"):
    try:
        if _name in st.secrets:
            os.environ.setdefault(_name, str(st.secrets[_name]))
    except Exception:  # no secrets file: fine when running locally
        pass

# Static styling only (graph paper + sticky-note button). No model text goes in here.
st.markdown(
    """
    <style>
    .stApp {
        background-image:
            linear-gradient(#cddae5 1px, transparent 1px),
            linear-gradient(90deg, #cddae5 1px, transparent 1px);
        background-size: 28px 28px;
    }
    h1 { letter-spacing: -0.02em; font-weight: 800; }
    button[kind="primary"], [data-testid="stBaseButton-primary"] {
        background: #ffd83a; color: #14283d; font-weight: 800;
        border: 2px solid #14283d; border-radius: 4px; box-shadow: 4px 4px 0 #14283d;
    }
    button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {
        background: #ffe56b; color: #14283d; border-color: #14283d;
    }
    button[kind="primary"]:disabled, [data-testid="stBaseButton-primary"]:disabled {
        background: #e6e9ec; color: #56606c; border-color: #aab3bd; box-shadow: 4px 4px 0 #aab3bd;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

ss = st.session_state
ss.setdefault("result", None)  # last answer from the model
ss.setdefault("code", "")      # bound to the editor box
ss.setdefault("stdin", "")     # bound to the input box
ss.setdefault("run", None)     # last run output
ss.setdefault("step", 0)       # active trace step


def go_to_step(delta: int) -> None:
    last = len(ss.result["trace"]) - 1
    ss.step = max(0, min(last, ss.step + delta))


# ---------------------------------------------------------------- header
st.title("CodeDoodle")
st.write("Photograph a flowchart, tree or state diagram. Get code you can run, and a trace of how it executes.")

has_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
if os.getenv("DEMO_MODE") == "1":
    st.info("Demo mode is on: every sketch returns the same example.")
elif not has_key:
    st.warning("No GEMINI_API_KEY found. Add it to your .env file and restart the app.")

left, right = st.columns([5, 7], gap="large")

# ---------------------------------------------------------------- left: the sketch
with left:
    st.subheader("Your sketch")

    use_camera = st.toggle("Use the camera instead of a file")
    if use_camera:
        image_file = st.camera_input("Take a photo of your diagram", label_visibility="collapsed")
    else:
        image_file = st.file_uploader(
            "Upload a photo of your diagram", type=["png", "jpg", "jpeg", "webp"]
        )

    if image_file is not None and not use_camera:
        st.image(image_file)

    language_label = st.radio("Write the code in", ["Python", "C++"], horizontal=True)
    language = "python" if language_label == "Python" else "cpp"

    if st.button("Read my sketch", type="primary", disabled=image_file is None):
        try:
            with st.spinner("Reading your sketch. This usually takes 10 to 30 seconds."):
                jpeg, mime = prepare_image(image_file.getvalue())
                answer = llm.analyze_sketch(jpeg, mime, language)
        except (ValueError, llm.LLMError) as err:
            st.error(str(err))
        else:
            if answer["diagram_type"] == "unrecognized" or not answer["code"].strip():
                st.warning(
                    "No programming diagram found in this photo. Draw with a dark pen on plain "
                    "paper, fill the frame with the diagram, and avoid shadows."
                )
            else:
                ss.result = answer
                ss.code = answer["code"]
                ss.stdin = answer["sample_stdin"]
                ss.run = None
                ss.step = 0

    result = ss.result
    if result:
        st.divider()
        st.subheader(result["title"])
        st.write(f"{result['diagram_type'].replace('_', ' ').capitalize()}. {result['summary']}")
        if result["uncertainties"]:
            with st.expander("Check these readings", expanded=True):
                for doubt in result["uncertainties"]:
                    st.write(f"- {doubt}")

# ---------------------------------------------------------------- right: the code
with right:
    st.subheader("Code")
    if not result:
        st.info("Your code appears here after you read a sketch.")
    else:
        view_tab, edit_tab = st.tabs(["View", "Edit"])
        with view_tab:
            st.code(ss.code, language="cpp" if result["language"] == "cpp" else "python", line_numbers=True)
        with edit_tab:
            st.text_area("Edit the code", key="code", height=420, label_visibility="collapsed")

        st.text_area("Input (stdin)", key="stdin", height=80, help="Values your program reads, one per line.")

        import subprocess
        import time

        if st.button("Run", type="primary"):
            with st.spinner("Running..."):
                start_time = time.time()
                try:
                    if result["language"] == "python":
                        # Execute Python script with stdin support
                        proc = subprocess.run(
                            [sys.executable, "-c", ss.code],
                            input=ss.stdin,
                            text=True,
                            capture_output=True,
                            timeout=5
                        )
                        duration = int((time.time() - start_time) * 1000)
                        ss.run = {
                            "stdout": proc.stdout,
                            "stderr": proc.stderr,
                            "exit_code": proc.returncode,
                            "duration_ms": duration,
                            "timed_out": False,
                            "phase": "run"
                        }
                    else:
                        st.info("Direct C++ compilation requires GCC/Clang installed locally on Windows.")
                except subprocess.TimeoutExpired:
                    ss.run = {
                        "stdout": "",
                        "stderr": "Execution timed out after 5 seconds.",
                        "exit_code": -1,
                        "duration_ms": 5000,
                        "timed_out": True,
                        "phase": "run"
                    }
                except Exception as e:
                    ss.run = {
                        "stdout": "",
                        "stderr": str(e),
                        "exit_code": 1,
                        "duration_ms": 0,
                        "timed_out": False,
                        "phase": "run"
                    }

        run = ss.run
        if run:
            ending = "timed out" if run["timed_out"] else f"exit {run['exit_code']}"
            st.caption(f"{ending} · {run['duration_ms']} ms")
            if run["stdout"]:
                st.subheader("Output:")
                st.code(run["stdout"], language=None)
            if run["stderr"]:
                st.subheader("Errors / Trace:")
                st.code(run["stderr"], language=None)

# ---------------------------------------------------------------- trace
if result and result["trace"]:
    st.divider()
    st.subheader("How it runs")

    steps = result["trace"]
    step = min(ss.step, len(steps) - 1)

    back_col, next_col, count_col = st.columns([1, 1, 6])
    back_col.button("Back", on_click=go_to_step, args=(-1,), disabled=step == 0)
    next_col.button("Next", on_click=go_to_step, args=(1,), disabled=step == len(steps) - 1)
    count_col.caption(f"Step {step + 1} of {len(steps)}")

    st.progress((step + 1) / len(steps))
    current = steps[step]
    with st.container(border=True):
        st.markdown(f"**{current['element'] or 'Step ' + str(current['step'])}**")
        st.write(current["explanation"])
        if current["state"]:
            st.code(current["state"], language=None)

    with st.expander("See all steps"):
        st.table(
            [
                {"Step": s["step"], "Diagram element": s["element"], "What happens": s["explanation"], "State": s["state"]}
                for s in steps
            ]
        )
