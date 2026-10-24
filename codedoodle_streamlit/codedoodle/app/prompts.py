"""The prompt that turns a photo of a diagram into code plus a trace.

The instructions live in the user turn (not a system instruction) so the same
request works on every Gemma endpoint, and the reply format is plain JSON that
we parse ourselves instead of relying on a JSON-mode switch.
"""

LANGUAGE_NAMES = {"python": "Python 3", "cpp": "C++17"}


def build_prompt(language: str) -> str:
    lang = LANGUAGE_NAMES[language]
    return f"""You are CodeDoodle, an expert at reading hand-drawn programming diagrams.

The image is a photo of a hand-drawn diagram: a flowchart, binary tree, linked list, graph, or state-transition diagram. Read it carefully. Boxes are statements, diamonds are conditions, arrows show control flow (read arrow labels such as Yes/No/True/False), and ovals are start/end.

Do three things:
1. Identify what the diagram is.
2. Write a complete, runnable {lang} program that implements exactly what the diagram shows. Follow the diagram's logic and labels; do not "improve" it.
3. Trace one example run of the program, step by step.

Rules for the code:
- Single file, standard library only, no network access, no file access.
- For Python: write clean, minimal, beginner-friendly code. Use standard input() and print().
- For Python: do NOT use sys.stdin.readline, low-level I/O buffers, or unnecessary try/except boilerplate unless explicitly drawn in the diagram.
- If the diagram needs input, provide matching sample_stdin (the raw values to feed into input(), one per line).
- For C++, include every needed header and define int main().
- Add short comments that name the diagram element each block comes from, for example "# diamond: n % 2 == 0".

Rules for the trace:
- Use the sample input you chose. Each step covers one diagram element (a box, a diamond branch, or a transition), in the order it executes.
- "state" shows the variable values after that step, in a few words.
- Use at most 25 steps. For loops, show the first two iterations, then summarise the rest in one step.

If part of the handwriting is unclear, make the most reasonable reading and list it in "uncertainties". If the image is not a programming diagram, set "diagram_type" to "unrecognized" and leave "code" empty.

Reply with ONLY one JSON object, no markdown fences, in exactly this shape:
{{
  "diagram_type": "flowchart | binary_tree | linked_list | graph | state_machine | other | unrecognized",
  "title": "short name for the algorithm",
  "summary": "one or two sentences on what the diagram does",
  "code": "the full program as a single string",
  "sample_stdin": "input for the run, or an empty string",
  "trace": [
    {{"step": 1, "element": "label from the diagram", "explanation": "what happens here", "state": "n=7"}}
  ],
  "uncertainties": ["anything you had to guess"]
}}"""
