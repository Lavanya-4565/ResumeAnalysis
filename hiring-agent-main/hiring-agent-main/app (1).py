import os
import re
import subprocess
import sys
from pathlib import Path

import streamlit as st

PROJECT_DIR = Path(__file__).parent
ROLES_DIR = PROJECT_DIR / "roles"
UPLOAD_DIR = PROJECT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="Hiring Agent", page_icon="📄", layout="wide")
st.title("📄 Hiring Agent: Resume Analyzer")
st.caption("Upload a resume PDF. A local LLM (Ollama, gemma3:4b) scores it against a role.")

# ---- Sidebar: role choice ----
roles = (
    sorted(p.name for p in ROLES_DIR.iterdir() if p.is_dir())
    if ROLES_DIR.exists()
    else ["software_engineering_intern"]
)
role = st.sidebar.selectbox("Role to score against", roles)
st.sidebar.info("Scoring runs fully on your laptop and can take 3 to 10 minutes.")

uploaded = st.file_uploader("Upload resume (PDF)", type="pdf")

if uploaded and st.button("Analyze resume", type="primary"):
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", uploaded.name)
    pdf_path = UPLOAD_DIR / safe_name
    pdf_path.write_bytes(uploaded.getbuffer())

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    with st.spinner("Analyzing... please wait, the local model is working."):
        result = subprocess.run(
            [sys.executable, "score.py", str(pdf_path), "--role", role],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )

    output = result.stdout
    if result.returncode != 0 or "OVERALL SCORE" not in output:
        st.error("The analysis did not finish. See the details below.")
        st.code((result.stderr or output)[-3000:])
        st.stop()

    # ---- Pull values out of the printed report ----
    name = re.search(r"RESUME EVALUATION RESULTS FOR:\s*(.+)", output)
    overall = re.search(r"OVERALL SCORE:\s*([\d.]+)\s*/\s*(\d+)", output)
    report = output[output.index("RESUME EVALUATION RESULTS"):]

    cats = []
    for label, got, mx in re.findall(
        r"^\W*([A-Za-z][A-Za-z ]+?):\s*([\d.]+)\s*/\s*(\d+)\s*$", report, re.M
    ):
        if "OVERALL" not in label.upper():
            cats.append((label.strip(), float(got), float(mx)))

    st.success("Analysis complete")
    if name:
        st.subheader(f"Candidate: {name.group(1).strip()}")

    left, right = st.columns([1, 2])
    with left:
        if overall:
            st.metric("Overall score", f"{overall.group(1)} / {overall.group(2)}")
            st.progress(min(float(overall.group(1)) / float(overall.group(2)), 1.0))
    with right:
        for label, got, mx in cats:
            st.write(f"**{label}**: {got:g} / {mx:g}")
            st.progress(min(got / mx, 1.0) if mx else 0.0)

    st.divider()
    st.subheader("Full evaluation report")
    st.text(report)

    with st.expander("Technical log (for debugging)"):
        st.code((result.stderr or "") + "\n" + output[: output.index("RESUME EVALUATION RESULTS")])
