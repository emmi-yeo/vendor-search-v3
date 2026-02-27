import io
import os
import base64
import json
from typing import List, Optional

import pandas as pd
from PyPDF2 import PdfReader
import docx

# Allowed types and limits
ALLOWED_EXTENSIONS = {"pdf", "docx", "xlsx", "xls", "png", "jpg", "jpeg"}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
MAX_TEXT_LENGTH = 15_000  # characters; rough token budget


def validate_file(uploaded_file) -> bool:
    """Raise ValueError if the uploaded file is not permitted."""
    name = uploaded_file.name
    size = getattr(uploaded_file, "size", None)
    if size is None:
        # `UploadedFile` from streamlit has .size attribute
        size = len(uploaded_file.read())
        uploaded_file.seek(0)

    ext = name.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"{name}: unsupported file type. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    if size > MAX_FILE_SIZE:
        raise ValueError(
            f"{name}: file too large ({size} bytes). Max {MAX_FILE_SIZE} bytes."
        )
    return True


def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    """Return a textual representation suitable for sending to the LLM.

    Image files are encoded as a base64 data URI so the model can at least
    "see" that an image was present; OCR is not performed.
    """
    ext = filename.rsplit(".", 1)[-1].lower()
    text = ""
    try:
        if ext == "pdf":
            reader = PdfReader(io.BytesIO(file_bytes))
            pages = [p.extract_text() or "" for p in reader.pages]
            text = "\n".join(pages)
        elif ext == "docx":
            doc = docx.Document(io.BytesIO(file_bytes))
            text = "\n".join(p.text for p in doc.paragraphs)
        elif ext in ("xlsx", "xls"):
            with io.BytesIO(file_bytes) as bio:
                sheets = pd.read_excel(bio, sheet_name=None)
            parts: List[str] = []
            for name, df in sheets.items():
                parts.append(f"Sheet: {name}")
                parts.append(df.to_csv(index=False))
            text = "\n".join(parts)
        elif ext in ("png", "jpg", "jpeg"):
            b64 = base64.b64encode(file_bytes).decode("ascii")
            text = f"[Image file {filename}]\ndata:image/{ext};base64,{b64}"
        else:
            text = ""
    except Exception as exc:
        raise ValueError(f"Failed to extract text from {filename}: {exc}")

    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH] + "\n...[truncated]"
    return text


def _build_llm_prompt(
    file_texts: List[str], filenames: List[str], user_query: Optional[str]
) -> List[dict]:
    system = {
        "role": "system",
        "content": (
            "You are an assistant that helps process user-uploaded documents. "
            "Given one or more documents (plaintext or base64 for images) and an optional query, decide "
            "whether to: 1) perform a vendor search, 2) summarize the document(s), "
            "3) ask the user for clarification, or 4) answer directly. "
            "Return a JSON object with an 'action' field: "
            "'search' (include 'search_query'), "
            "'summary' (include 'text'), "
            "'clarify' (include 'text'), "
            "or 'respond' (include 'text'). "
            "Do not wrap the JSON in markdown or code fences."
        ),
    }
    user_content = ""
    for name, txt in zip(filenames, file_texts):
        user_content += f"\n---\nFilename: {name}\n{txt}\n"
    if user_query:
        user_content += f"\nUser query: {user_query}\n"
    return [system, {"role": "user", "content": user_content}]


def interpret_files(
    file_texts: List[str], filenames: List[str], user_query: Optional[str]
) -> dict:
    """Ask the LLM what should be done with the supplied documents.

    Returns the parsed JSON response or a fallback when the model returns
    something unparseable.
    """
    from src.azure_llm import azure_chat

    messages = _build_llm_prompt(file_texts, filenames, user_query)
    resp = azure_chat(messages, temperature=0.2, max_tokens=1024)
    try:
        return json.loads(resp)
    except Exception:
        return {"action": "respond", "text": resp}


def handle_uploaded_files(uploaded_files, user_query: Optional[str] = None) -> dict:
    """Process a list of Streamlit UploadedFile objects.

    Validation and extraction happen here; the function returns a dict with one
    of the standard actions.  Searching itself is left to the caller so that the
    function is not tightly coupled to the Streamlit session.
    """
    filenames: List[str] = []
    texts: List[str] = []
    for f in uploaded_files:
        validate_file(f)
        content = f.read()
        filenames.append(f.name)
        texts.append(extract_text_from_file(content, f.name))
    decision = interpret_files(texts, filenames, user_query)
    return decision
