import streamlit as st
import pdfplumber
import requests
from bs4 import BeautifulSoup
import json
import os

def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except:
        return os.environ.get("GEMINI_API_KEY", "")

def call_gemini(prompt):
    api_key = get_api_key()
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

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

Return ONLY a JSON array like:
[{{"claim": "the exact claim", "context": "brief surrounding context"}}]

Text:
{text[:6000]}

Return only the JSON array, no markdown, no explanation.
"""
    raw = call_gemini(prompt).strip()
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
        snippets = [g.get_text() for g in soup.select(".VwiC3b, .yXK7lf, .MUxGbd")]
        return " ".join(snippets[:5])
    except:
        return ""

def verify_claim(claim, context, web_data):
    prompt = f"""
You are a fact-checker. Given a claim and web search results, determine accuracy.

Claim: {claim}
Context: {context}
Web Results: {web_data[:2000] if web_data else "No results found."}

Respond ONLY with this JSON:
{{"verdict": "Verified" or "Inaccurate" or "False", "explanation": "1-2 sentences", "correct_fact": "correct info if wrong, else empty string"}}

Verdicts:
- Verified: matches web data
- Inaccurate: outdated or partially wrong
- False: wrong or no evidence

Return only JSON, no markdown.
"""
    raw = call_gemini(prompt).strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])

if uploaded_file:
    with st.spinner("Extracting text from PDF..."):
        text = extract_text_from_pdf(uploaded_file)

    if not text.strip():
        st.error("Could not extract text from PDF.")
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

            verified_count = inaccurate_count = false_count = 0
            results = []
            progress = st.progress(0)

            for i, item in enumerate(claims):
                claim = item.get("claim", "")
                context = item.get("context", "")
                web_data = search_web(claim)
                try:
                    result = verify_claim(claim, context, web_data)
                    results.append({"claim": claim, **result})
                    v = result.get("verdict", "False")
                    if v == "Verified": verified_count += 1
                    elif v == "Inaccurate": inaccurate_count += 1
                    else: false_count += 1
                except Exception as e:
                    results.append({"claim": claim, "verdict": "False", "explanation": f"Error: {e}", "correct_fact": ""})
                    false_count += 1
                progress.progress((i + 1) / len(claims))

            col1, col2, col3 = st.columns(3)
            col1.metric("Verified", verified_count)
            col2.metric("Inaccurate", inaccurate_count)
            col3.metric("False", false_count)
            st.markdown("---")

            for r in results:
                verdict = r.get("verdict", "False")
                color = "green" if verdict == "Verified" else "orange" if verdict == "Inaccurate" else "red"
                with st.expander(f"[{verdict.upper()}] {r['claim'][:100]}"):
                    st.markdown(f"**Verdict:** :{color}[{verdict}]")
                    st.markdown(f"**Explanation:** {r.get('explanation', '')}")
                    if r.get("correct_fact"):
                        st.markdown(f"**Correct Fact:** {r.get('correct_fact')}")
