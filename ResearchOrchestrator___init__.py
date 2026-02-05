import logging
import os
import json
import uuid
import datetime
import azure.functions as func
import requests
from azure.storage.blob import BlobServiceClient

# --- Environment variables ---
OPENAI_ENDPOINT = os.environ["OPENAI_ENDPOINT"].rstrip("/")
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_DEPLOYMENT_NAME = os.environ["OPENAI_DEPLOYMENT_NAME"]

BING_ENDPOINT = os.environ.get("BING_ENDPOINT", "").rstrip("/")
BING_API_KEY = os.environ.get("BING_API_KEY")

STORAGE_ACCOUNT_NAME = os.environ["STORAGE_ACCOUNT_NAME"]
DOCUMENT_CONTAINER_NAME = os.environ["DOCUMENT_CONTAINER_NAME"]


def call_openai_chat(system_prompt: str, user_prompt: str, temperature: float = 0.2):
    """
    Call Azure OpenAI Chat Completions (GPT-4o or similar).
    """
    url = f"{OPENAI_ENDPOINT}/openai/deployments/{OPENAI_DEPLOYMENT_NAME}/chat/completions?api-version=2024-02-15-preview"
    headers = {
        "Content-Type": "application/json",
        "api-key": OPENAI_API_KEY,
    }
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": 2000,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def bing_search(query: str, top: int = 5):
    """
    Very simple Bing Web Search wrapper.
    """
    if not BING_ENDPOINT or not BING_API_KEY:
        return []

    params = {"q": query, "count": top}
    headers = {"Ocp-Apim-Subscription-Key": BING_API_KEY}
    resp = requests.get(BING_ENDPOINT, params=params, headers=headers, timeout=20)
    resp.raise_for_status()
    results = resp.json()

    web_pages = results.get("webPages", {}).get("value", [])
    items = []
    for item in web_pages:
        items.append(
            {
                "name": item.get("name"),
                "snippet": item.get("snippet"),
                "url": item.get("url"),
            }
        )
    return items


# --- Agents ---

def coordinator_agent(question: str):
    """
    Coordinator decides what sub-tasks to run (simplified).
    """
    # For now, always call all agents; later you can make this dynamic.
    plan = {
        "call_search": True,
        "call_summarization": True,
        "call_extraction": True,
        "call_citation": True,
        "call_document_builder": True,
    }
    return plan


def search_agent(question: str):
    """
    Use Bing to search web and return raw results.
    """
    results = bing_search(question, top=5)
    return results


def summarization_agent(question: str, search_results):
    """
    Summarize the search results into a concise narrative.
    """
    context_text = ""
    for idx, r in enumerate(search_results, start=1):
        context_text += f"[{idx}] {r['name']} - {r['snippet']} (URL: {r['url']})\n"

    system_prompt = (
        "You are a research summarization assistant. "
        "Given a user question and web search snippets, produce a structured summary."
    )
    user_prompt = f"User question: {question}\n\nWeb results:\n{context_text}\n\nWrite a structured summary."
    summary = call_openai_chat(system_prompt, user_prompt)
    return summary


def data_extraction_agent(question: str, summary: str):
    """
    Extract key facts/metrics/entities from the summary.
    """
    system_prompt = (
        "You extract key facts, metrics, entities, and important bullet points from text. "
        "Return them as a JSON object with keys: 'key_facts', 'metrics', 'entities'."
    )
    user_prompt = f"User question: {question}\n\nSummary:\n{summary}\n\nExtract structured data."
    raw = call_openai_chat(system_prompt, user_prompt)
    # Try to parse JSON; if it fails, wrap as text.
    try:
        data = json.loads(raw)
    except Exception:
        data = {"raw_extraction": raw}
    return data


def citation_agent(search_results, summary: str):
    """
    Construct citation list from search results and how they support the summary.
    """
    refs_text = ""
    for idx, r in enumerate(search_results, start=1):
        refs_text += f"[{idx}] {r['name']} ({r['url']})\n"

    system_prompt = (
        "You create a citations section for a research report using a list of sources with URLs. "
        "Return a formatted citations section in markdown."
    )
    user_prompt = f"Summary:\n{summary}\n\nSources:\n{refs_text}\n\nGenerate citations section."
    citations = call_openai_chat(system_prompt, user_prompt)
    return citations


def document_builder_agent(question: str, summary: str, extraction, citations: str):
    """
    Build a simple HTML document that can be opened in Word.
    """
    extracted_str = json.dumps(extraction, indent=2, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8" />
    <title>Research Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1, h2, h3 {{ color: #1F4E79; }}
        .section {{ margin-bottom: 24px; }}
        pre {{ background: #f5f5f5; padding: 8px; border-radius: 4px; }}
    </style>
</head>
<body>
    <h1>Research Report</h1>
    <div class="section">
        <h2>Question</h2>
        <p>{question}</p>
    </div>
    <div class="section">
        <h2>Executive Summary</h2>
        <p>{summary.replace(chr(10), "<br/>")}</p>
    </div>
    <div class="section">
        <h2>Extracted Facts & Entities</h2>
        <pre>{extracted_str}</pre>
    </div>
    <div class="section">
        <h2>Citations</h2>
        <pre>{citations}</pre>
    </div>
</body>
</html>"""
    return html


def upload_document_to_blob(html_content: str, question: str):
    """
    Upload the HTML to Blob Storage as .html (Word-readable) and return URL (SAS-less).
    In a real system, you should generate a SAS token or secure access pattern.
    """
    connection_str = os.environ.get("AzureWebJobsStorage")
    if not connection_str:
        raise RuntimeError("AzureWebJobsStorage not found in environment")

    blob_service = BlobServiceClient.from_connection_string(connection_str)
    container_client = blob_service.get_container_client(DOCUMENT_CONTAINER_NAME)
    container_client.create_container(exist_ok=True)

    doc_id = str(uuid.uuid4())
    file_name = f"report-{doc_id}.html"

    blob_client = container_client.get_blob_client(file_name)
    blob_client.upload_blob(html_content.encode("utf-8"), overwrite=True)

    # Public URL if container is public; otherwise, you'd generate SAS.
    blob_url = blob_client.url
    return blob_url, file_name


# --- HTTP Trigger Function ---

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("ResearchOrchestrator HTTP trigger processed a request.")

    try:
        body = req.get_json()
    except ValueError:
        body = {}

    question = body.get("question") or req.params.get("question")
    if not question:
        return func.HttpResponse(
            json.dumps({"error": "Missing 'question' in body or query string."}),
            status_code=400,
            mimetype="application/json",
        )

    try:
        # Coordinator decides plan (simple for now).
        plan = coordinator_agent(question)

        search_results = []
        if plan.get("call_search"):
            search_results = search_agent(question)

        summary = ""
        if plan.get("call_summarization"):
            summary = summarization_agent(question, search_results)

        extraction = {}
        if plan.get("call_extraction"):
            extraction = data_extraction_agent(question, summary)

        citations = ""
        if plan.get("call_citation"):
            citations = citation_agent(search_results, summary)

        final_html = ""
        if plan.get("call_document_builder"):
            final_html = document_builder_agent(
                question, summary, extraction, citations
            )

        doc_url, file_name = upload_document_to_blob(final_html, question)
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"

        result = {
            "question": question,
            "document_url": doc_url,
            "file_name": file_name,
            "generated_at_utc": timestamp,
            "summary_preview": summary[:500],
            "plan": plan,
        }

        return func.HttpResponse(
            json.dumps(result, ensure_ascii=False),
            status_code=200,
            mimetype="application/json",
        )

    except Exception as ex:
        logging.exception("Error in ResearchOrchestrator")
        return func.HttpResponse(
            json.dumps({"error": str(ex)}),
            status_code=500,
            mimetype="application/json",
        )