# FactCheck Agent

A deployed web app that automates PDF claim verification using AI and live web search.

## What it does

1. Upload any PDF
2. AI extracts all verifiable claims (stats, dates, figures)
3. Each claim is searched on the live web
4. Claims are flagged as **Verified**, **Inaccurate**, or **False**

## Tech Stack

- **Frontend/Backend:** Streamlit
- **AI:** Google Gemini 1.5 Flash
- **PDF Parsing:** pdfplumber
- **Web Search:** Google Search scraping via requests + BeautifulSoup
- **Deployment:** Streamlit Cloud

## Local Setup

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_key_here
streamlit run app.py
```

## Deployment

Deployed on Streamlit Cloud. Set `GEMINI_API_KEY` in Streamlit Cloud secrets.

## Evaluation

The app successfully flags intentionally false or outdated statistics in "trap documents" by cross-referencing claims against live web data.
