"""Canned response for DEMO_MODE=1.

This is the safety net for a flaky venue Wi-Fi or a rate-limited key. It always
describes the even/odd flowchart in samples/even_or_odd.png, whatever image is
uploaded, so label it as a demo whenever you use it.
"""

_TRACE = [
    {"step": 1, "element": "Start", "explanation": "The program begins.", "state": "-"},
    {"step": 2, "element": "Read n", "explanation": "Read one integer from input.", "state": "n=7"},
    {"step": 3, "element": "n % 2 == 0 ?", "explanation": "7 % 2 is 1, so the condition is false and the No arrow is taken.", "state": "n=7, condition=False"},
    {"step": 4, "element": "Print odd", "explanation": "The No branch prints the word odd.", "state": "output=odd"},
    {"step": 5, "element": "End", "explanation": "Both branches meet here and the program stops.", "state": "done"},
]

_PY = '''# oval: Start
n = int(input())          # parallelogram: read n

if n % 2 == 0:            # diamond: n % 2 == 0 ?
    print("even")         # box: print even  (Yes branch)
else:
    print("odd")          # box: print odd   (No branch)
# oval: End
'''

_CPP = '''#include <iostream>
using namespace std;

int main() {
    // oval: Start
    int n;
    cin >> n;                 // parallelogram: read n

    if (n % 2 == 0) {         // diamond: n % 2 == 0 ?
        cout << "even" << endl;   // box: print even  (Yes branch)
    } else {
        cout << "odd" << endl;    // box: print odd   (No branch)
    }
    return 0;                 // oval: End
}
'''


def demo_result(language: str) -> dict:
    return {
        "diagram_type": "flowchart",
        "title": "Even or odd",
        "summary": "Reads a number and prints whether it is even or odd, using one yes/no decision.",
        "language": language,
        "code": _CPP if language == "cpp" else _PY,
        "sample_stdin": "7",
        "trace": _TRACE,
        "uncertainties": ["DEMO MODE: this is a canned example, not a reading of your photo."],
    }
