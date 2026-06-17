import streamlit as st
import pdfplumber
import google.generativeai as genai
import json
import requests
from bs4 import BeautifulSoup
import os

# Configure Gemini
genai.configure(api_key=os.environ.get("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

st.set_page_config(page_title="FactCheck Agent", page_icon="🔍", layout="wide")

st.title("Fact-Check Agent")
st.markdown("Upload a PDF to extract and verify claims against live web data.")

def extract_text_from_pdf(uploaded_file):
    text = ""
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text

def extract_claims(text):
    prompt = f"""
You are a fact-checking assistant. Extract all specific verifiable claims from the following text.
Focus on: statistics, percentages, dates, financial figures, numerical data, named facts.

Return ONLY a JSON array of objects with this format:
[
  {{"claim": "the exact claim", "context": "brief surrounding context"}}
]

Text:
{text[:6000]}

Return only the JSON array, no other text.
"""
    response = model.generate_content(prompt)
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

def search_web(query):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = f"https://www.google.com/search?q={requests.utils.quote(query)}&num=5"
        resp = requests.get(url, headers=headers, timeout=8)
        soup = BeautifulSoup(resp.text, "html.parser")
        snippets = []
        for g in soup.select(".VwiC3b, .yXK7lf, .MUxGbd"):
            snippets.append(g.get_text())
        return " ".join(snippets[:5])
    except Exception as e:
        return ""

def verify_claim(claim, context, web_data):
    prompt = f"""
You are a fact-checker. Given a claim and web search results, determine if the claim is accurate.

Claim: {claim}
Context: {context}
Web Search Results: {web_data[:2000] if web_data else "No results found."}

Respond ONLY with a JSON object:
{{
  "verdict": "Verified" or "Inaccurate" or "False",
  "explanation": "1-2 sentence explanation",
  "correct_fact": "The correct information if claim is wrong, else empty string"
}}

Verdicts:
- Verified: claim matches web data
- Inaccurate: claim is outdated or partially wrong
- False: claim is wrong or no evidence exists

Return only JSON, no other text.
"""
    response = model.generate_content(prompt)
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

# UI
uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])

if uploaded_file:
    with st.spinner("Extracting text from PDF..."):
        text = extract_text_from_pdf(uploaded_file)

    if not text.strip():
        st.error("Could not extract text from PDF. Try a text-based PDF.")
    else:
        st.success(f"Extracted {len(text)} characters from PDF.")

        with st.spinner("Identifying claims using AI..."):
            try:
                claims = extract_claims(text)
                st.info(f"Found {len(claims)} verifiable claims.")
            except Exception as e:
                st.error(f"Claim extraction failed: {e}")
                claims = []

        if claims:
            st.markdown("---")
            st.subheader("Verification Results")

            verified_count = 0
            inaccurate_count = 0
            false_count = 0

            results = []

            progress = st.progress(0)
            for i, item in enumerate(claims):
                claim = item.get("claim", "")
                context = item.get("context", "")

                web_data = search_web(claim)
                try:
                    result = verify_claim(claim, context, web_data)
                    results.append({"claim": claim, **result})

                    verdict = result.get("verdict", "False")
                    if verdict == "Verified":
                        verified_count += 1
                    elif verdict == "Inaccurate":
                        inaccurate_count += 1
                    else:
                        false_count += 1
                except Exception as e:
                    results.append({"claim": claim, "verdict": "False", "explanation": f"Error: {e}", "correct_fact": ""})
                    false_count += 1

                progress.progress((i + 1) / len(claims))

            # Summary
            col1, col2, col3 = st.columns(3)
            col1.metric("Verified", verified_count, delta=None)
            col2.metric("Inaccurate", inaccurate_count, delta=None)
            col3.metric("False", false_count, delta=None)

            st.markdown("---")

            for r in results:
                verdict = r.get("verdict", "False")
                if verdict == "Verified":
                    color = "green"
                    icon = "VERIFIED"
                elif verdict == "Inaccurate":
                    color = "orange"
                    icon = "INACCURATE"
                else:
                    color = "red"
                    icon = "FALSE"

                with st.expander(f"[{icon}] {r['claim'][:100]}"):
                    st.markdown(f"**Verdict:** :{color}[{verdict}]")
                    st.markdown(f"**Explanation:** {r.get('explanation', '')}")
                    if r.get("correct_fact"):
                        st.markdown(f"**Correct Fact:** {r.get('correct_fact')}")
