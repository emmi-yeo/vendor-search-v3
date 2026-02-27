import streamlit as st
import pandas as pd
import os
import json
import hashlib
from dotenv import load_dotenv
import uuid
import re 
import time
from src.build_index import build_vendor_documents, build_faiss_and_bm25
from src.query_parser import parse_query
from src.retrieval import search
from src.export import export_to_csv, export_to_excel, export_to_pdf
from src.vendor_context import get_vendor_context
from src.duplicate_detection import find_duplicate_vendors
from src.file_processor import process_uploaded_files, format_file_content_for_llm
from src.vendor_context_query import detect_context_query, answer_context_query
from src.external_enrichment import build_enrichment_profile, is_enrichment_enabled
from src.intent_router import route_intent
from src.vendor_context import get_vendor_fact
from src.query_translation import translate_query_to_english
from src.ai_intent import classify_intent
from src.ai_planner import generate_search_plan
from src.ai_responder import generate_response
from src.aggregation import aggregate_vendors
from src.azure_sql_loader import load_vendor_tables

def is_malicious_sql_input(text: str) -> bool:
    dangerous_patterns = [
        r"drop\s+table",
        r"delete\s+from",
        r"insert\s+into",
        r"update\s+.+set",
        r"union\s+select",
        r"--",
        r";",
        r"xp_",
        r"exec\s",
    ]

    text_lower = text.lower()

    for pattern in dangerous_patterns:
        if re.search(pattern, text_lower):
            return True

    return False

# Load environment variables from .env file
load_dotenv()

# Deep link configuration
VENDOR_PROFILE_BASE_URL = os.getenv("VENDOR_PROFILE_BASE_URL", "")
EXTERNAL_ENRICHMENT_ENABLED = os.getenv("EXTERNAL_ENRICHMENT_ENABLED", "false").lower() == "true"

def hash_filters(d: dict) -> str:
    s = json.dumps(d, sort_keys=True)
    return hashlib.md5(s.encode("utf-8")).hexdigest()

st.set_page_config(page_title="Vendor AI Search POC", layout="wide")

@st.cache_data(ttl=300)
def load_data():
    #profiles = pd.read_csv("data/vendor_profiles.csv")
    #attachments = pd.read_csv("data/vendor_attachments.csv")
    #txns = pd.read_csv("data/vendor_transactions.csv")
    profiles, attachments = load_vendor_tables()
    txns = pd.DataFrame(columns=[
    "vendor_id",
    "total_spend",
    "performance_score",
    "compliance_score",
    "risk_score"
    ])
    # placeholder until we map transaction table
    return profiles, attachments, txns


@st.cache_resource
def init_index():
    profiles, attachments, txns = load_data()
    docs, meta = build_vendor_documents(profiles, attachments, txns)
    # embed_model parameter is kept for compatibility but not used (uses local_embedder)
    index, bm25, dim = build_faiss_and_bm25(docs, "")
    return docs, meta, index, bm25

docs, meta, index, bm25 = init_index()
profiles, attachments, txns = load_data()

# Sort options
SORT_OPTIONS = {
    "Relevance (default)": "relevance",
    "Compliance Score": "compliance",
    "Risk Score": "risk",
    "Performance Score": "performance",
    "Total Spend": "spend"
}

# Default sort by relevance
sort_by = "Relevance (default)"

if "request_timestamps" not in st.session_state:
    st.session_state.request_timestamps = []

# ---- Chat state ----
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! Describe the vendor you need (capabilities, industry, location, certifications). I’ll search vendor profiles + attachments + transactions."}
    ]
if "last_query" not in st.session_state:
    st.session_state.last_query = None
if "last_results" not in st.session_state:
    st.session_state.last_results = None
if "results_page" not in st.session_state:
    st.session_state.results_page = 0

# Pagination state - track per render_id
if "pagination_state" not in st.session_state:
    st.session_state.pagination_state = {}

# Unique user session ID (unchanged for duration of browser session)
if "user_session_id" not in st.session_state:
    st.session_state.user_session_id = str(uuid.uuid4())

RESULTS_PER_PAGE = 10
def render_search_results_in_chat(
        results,
        query_json,
        presentation=None
    ):
        """
        Render search results with pagination, including tables, pagination controls, and export.
        """
        if presentation is None:
            presentation = {}

        import hashlib
        import json

        render_id = query_json.get("render_id")

        if not render_id:
            render_id = f"auto_{uuid.uuid4()}"

        # Initialize pagination for this table if not exists
        if render_id not in st.session_state.pagination_state:
            st.session_state.pagination_state[render_id] = 0

        mode = presentation.get("mode", "table")

        # 🔒 Guardrail
        if len(results) >= 2:
            mode = "table"

        st.markdown("### 🔍 Search Results")

        if not results:
            st.info("No vendors found.")
            return
        
        presentation = presentation or {}

        fields = presentation.get("fields") or [
            "vendor_name", "industry", "location", "certifications", "final_score"
        ]

        limit = presentation.get("limit")
        sort_by = presentation.get("sort_by")
        sort_order = presentation.get("sort_order", "desc")

        df = pd.DataFrame(results)

        # Keep only requested fields
        df = df[[f for f in fields if f in df.columns]]

        # Sorting
        if sort_by and sort_by in df.columns:
            df = df.sort_values(sort_by, ascending=(sort_order == "asc"))

        # Limit rows (if specified in presentation)
        if limit:
            df = df.head(limit)

        # Calculate pagination
        total_rows = len(df)
        total_pages = (total_rows + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE
        current_page = st.session_state.pagination_state[render_id]

        # Ensure current page is valid
        if current_page >= total_pages:
            current_page = max(0, total_pages - 1)
            st.session_state.pagination_state[render_id] = current_page

        # Calculate start and end indices
        start_idx = current_page * RESULTS_PER_PAGE
        end_idx = min(start_idx + RESULTS_PER_PAGE, total_rows)

        # Get paginated data
        paginated_df = df.iloc[start_idx:end_idx]

        # Display table
        if len(paginated_df) > 0:
            st.markdown("**Results:**")
            st.dataframe(paginated_df, use_container_width=True)
        
        st.divider()

        # Pagination Controls
        st.markdown("#### 📄 Pagination")
        col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])

        with col1:
            if st.button("⬅️ Previous", key=f"prev_{render_id}", disabled=(current_page == 0)):
                st.session_state.pagination_state[render_id] = current_page - 1
                st.rerun()

        with col2:
            if st.button("Next ➡️", key=f"next_{render_id}", disabled=(current_page >= total_pages - 1)):
                st.session_state.pagination_state[render_id] = current_page + 1
                st.rerun()

        with col3:
            st.markdown(f"**Page {current_page + 1} of {total_pages}** | Showing {start_idx + 1}-{end_idx} of {total_rows} results")

        with col4:
            if st.button("⬅️⬅️ First", key=f"first_{render_id}", disabled=(current_page == 0)):
                st.session_state.pagination_state[render_id] = 0
                st.rerun()

        with col5:
            if st.button("Last ➡️➡️", key=f"last_{render_id}", disabled=(current_page >= total_pages - 1)):
                st.session_state.pagination_state[render_id] = total_pages - 1
                st.rerun()

        # Export - uses full dataframe, not paginated
        st.markdown("#### 📥 Export (Full Table)")
        c1, c2, c3 = st.columns(3)

        with c1:
            st.download_button(
                "CSV",
                export_to_csv(df),
                file_name="vendors.csv",
                mime="text/csv",
                key=f"csv_{render_id}"
            )

        with c2:
            st.download_button(
                "Excel",
                export_to_excel(df),
                file_name="vendors.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"xlsx_{render_id}"
            )

        with c3:
            st.download_button(
                "PDF",
                export_to_pdf(df),
                file_name="vendors.pdf",
                mime="application/pdf",
                key=f"pdf_{render_id}"
            )

st.title("🤖 Vendor Search v0.1")

# ===== SIDEBAR: Prompts =====
with st.sidebar:
    st.divider()

# Predefined prompts
with st.sidebar.expander("💡 Quick Prompts"):
    import json
    try:
        with open("data/prompts.json", "r") as f:
            prompts_data = json.load(f)
            
        for category, prompt_list in prompts_data.get("categories", {}).items():
            st.markdown(f"**{category.replace('_', ' ').title()}:**")
            for prompt in prompt_list[:3]:  # Show first 3
                if st.button(prompt, key=f"prompt_{category}_{prompt[:20]}", use_container_width=True):
                    # Store prompt to trigger search processing
                    st.session_state.pending_query = prompt
                    st.rerun()
    except Exception:
        pass

def push_assistant_message(md: str):
    st.session_state.messages.append({"role": "assistant", "content": md})

# Render chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        if msg["role"] == "assistant" and "table" in msg:
            render_search_results_in_chat(
                results=msg["table"]["results"],
                query_json=msg["table"]["query_json"],
                presentation=msg.get("presentation")
            )

def sort_results(results: list, sort_key: str) -> list:
    """Sort results by the specified key."""
    if sort_key == "relevance":
        return results  # Already sorted by relevance
    elif sort_key == "compliance":
        return sorted(results, key=lambda x: x.get("compliance_score", 0), reverse=True)
    elif sort_key == "risk":
        return sorted(results, key=lambda x: x.get("risk_score", 0), reverse=True)
    elif sort_key == "performance":
        return sorted(results, key=lambda x: x.get("performance_score", 0), reverse=True)
    elif sort_key == "spend":
        return sorted(results, key=lambda x: x.get("total_spend", 0), reverse=True)
    return results

def run_search_from_query(query_json: dict):
    search_text = query_json["search_text"]
    filters = query_json["filters"]
    constraints = query_json.get("constraints", {})
    capabilities = query_json.get("capabilities", [])
    performance_query = query_json.get("performance_query", {})
    compliance_query = query_json.get("compliance_query", {})
    logic_operators = query_json.get("logic_operators", {})

    results, filter_warning, show_only_top = search(
        index, bm25, docs, meta,
        search_text, filters, constraints, capabilities,
        "", top_k=50,  # Retrieve many results for dynamic threshold filtering
        performance_query=performance_query,
        compliance_query=compliance_query,
        logic_operators=logic_operators
    )
        
    # Apply sorting
    sort_key = SORT_OPTIONS.get(sort_by, "relevance")
    results = sort_results(results, sort_key)

    st.session_state.last_query = query_json
    st.session_state.last_results = results

    return results, filter_warning, show_only_top
    
def is_presentation_only_request(text: str) -> bool:
    keywords = [
        "show", "format", "layout", "column", "remove",
        "add column", "reorder", "table", "markdown",
        "date format", "group by", "sort by"
    ]
    return any(k in text.lower() for k in keywords)


# Check for pending query from prompt button (before chat input)
pending_query = None
if "pending_query" in st.session_state and st.session_state.pending_query:
    pending_query = st.session_state.pending_query
    # Clear it after reading
    del st.session_state.pending_query

ALLOWED_FILE_TYPES = ["pdf", "docx", "xlsx", "xls", "png", "jpg", "jpeg"]
ALLOWED_EXTENSIONS = {f".{ext}" for ext in ALLOWED_FILE_TYPES}
MAX_UPLOAD_SIZE_MB = 10

def validate_uploaded_file(uploaded_file):
    filename = uploaded_file.name.lower()

    # 1️⃣ Extension validation
    _, ext = os.path.splitext(filename)

    if not ext:
        return False, "File has no extension."

    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Unsupported file type: {ext}. Allowed types: {', '.join(ALLOWED_FILE_TYPES)}"

    # 2️⃣ Size validation
    file_size_mb = uploaded_file.size / (1024 * 1024)

    if file_size_mb > MAX_UPLOAD_SIZE_MB:
        return False, f"File too large ({file_size_mb:.2f}MB). Maximum allowed size is {MAX_UPLOAD_SIZE_MB}MB."

    # 3️⃣ Empty file validation
    if uploaded_file.size == 0:
        return False, "Uploaded file is empty."

    return True, "Valid"

supporting_files = st.file_uploader(
    "📎 Upload supporting files",
    type=ALLOWED_FILE_TYPES,
    accept_multiple_files=True,
    key="file_uploader"
)

# Initialize file validation state
if "file_validation_error" not in st.session_state:
    st.session_state.file_validation_error = None
if "validated_files" not in st.session_state:
    st.session_state.validated_files = []
if "file_contents" not in st.session_state:
    st.session_state.file_contents = {}
if "last_uploaded_files" not in st.session_state:
    st.session_state.last_uploaded_files = None

# Only revalidate if files changed
if supporting_files != st.session_state.last_uploaded_files:

    st.session_state.file_validation_error = None
    st.session_state.validated_files = []
    st.session_state.file_contents = {}

    if supporting_files:
        for file in supporting_files:
            is_valid, message = validate_uploaded_file(file)

            if not is_valid:
                st.session_state.file_validation_error = message
                break

            st.session_state.validated_files.append(file)

        if not st.session_state.file_validation_error:
            with st.spinner("Processing uploaded files..."):
                st.session_state.file_contents = process_uploaded_files(
                    st.session_state.validated_files
                )

            if not st.session_state.file_contents:
                st.session_state.file_validation_error = (
                    "The uploaded file contains no readable content."
                )

    st.session_state.last_uploaded_files = supporting_files
def is_rate_limited(max_requests=10, window_seconds=60):
    now = time.time()

    # Keep only timestamps within window
    st.session_state.request_timestamps = [
        ts for ts in st.session_state.request_timestamps
        if now - ts < window_seconds
    ]

    if len(st.session_state.request_timestamps) >= max_requests:
        return True

    st.session_state.request_timestamps.append(now)
    return False
# Show error if exists
if st.session_state.file_validation_error:
    st.error(st.session_state.file_validation_error)
def llm_prompt_quality_check(text: str):
    """
    Ask LLM whether the prompt is meaningful enough
    to proceed with vendor search.
    Returns: ("valid" | "invalid", explanation)
    """

    from src.azure_llm import azure_chat

    messages = [
        {
            "role": "system",
            "content": (
                "You are a prompt validator for a vendor search system.\n"
                "Determine if the user's input is meaningful enough to run a vendor search.\n\n"
                "If the input is empty, whitespace, emoji-only, too vague, or meaningless,\n"
                "respond with JSON: {\"status\": \"invalid\", \"message\": \"<friendly clarification message>\"}\n\n"
                "If the input is meaningful and actionable,\n"
                "respond with JSON: {\"status\": \"valid\"}"
            )
        },
        {"role": "user", "content": text}
    ]

    response = azure_chat(messages, temperature=0)

    try:
        result = json.loads(response)
        return result.get("status"), result.get("message", "")
    except Exception:
        # fallback safe behavior
        return "valid", ""

# New user input - always at the bottom
user_input = st.chat_input("Ask for vendors in natural language…")   
    
# Handle user input (text and/or files) OR pending query from prompt button
if user_input or pending_query:

    user_text = pending_query if pending_query else user_input

    # ✅ Always show user message first
    st.session_state.messages.append({
        "role": "user",
        "content": user_text
    })

    # 🔐 SQL Injection Guard
    if is_malicious_sql_input(user_text):
        st.session_state.messages.append({
            "role": "assistant",
            "content": "⚠️ Your query contains potentially unsafe SQL-like patterns and was blocked for security reasons."
        })
        st.rerun()

    # 🚦 Rate Limit Guard
    if is_rate_limited():
        st.session_state.messages.append({
            "role": "assistant",
            "content": "🚦 Too many requests. Please wait a moment before trying again."
        })
        st.rerun()
    # 🚨 Block search if file validation failed
    if st.session_state.file_validation_error:
        st.warning("Please fix the file upload issue before searching.")
        st.stop()

    # ------------------------------------------------------------------
    # 📂 FILE CONTEXT — COMPUTED EARLY so all LLM calls can see it
    # ------------------------------------------------------------------
    file_context = ""
    if st.session_state.file_contents:
        file_context = format_file_content_for_llm(st.session_state.file_contents, max_length=8000)

    # Build an enriched query that carries file content for all LLM-facing calls.
    # The raw user_text is kept for display; effective_query is used for LLM operations.
    if file_context:
        file_names = ", ".join(st.session_state.file_contents.keys())
        effective_query = (
            f"{user_text}\n\n"
            f"[The user attached the following file(s): {file_names}]\n"
            f"[Attached File Content]\n{file_context}"
        )
    else:
        effective_query = user_text

    # 🤖 LLM-based prompt quality validation (uses enriched query so it sees file context)
    status, message = llm_prompt_quality_check(effective_query)

    if status == "invalid":
        st.session_state.messages.append({
            "role": "assistant",
            "content": message or "Could you clarify your request?"
        })
        st.rerun()

    # --------------------------------------------------
    # 🎨 PRESENTATION-ONLY COMMAND (NEW TABLE, SAME DATA)
    # --------------------------------------------------

    if is_presentation_only_request(user_text):
        # we need previous results to re-render with a different layout
        if not st.session_state.get("last_results"):
            st.session_state.messages.append({
                "role": "assistant",
                "content": "There are no previous search results to format yet."
            })
            st.rerun()

        from src.presentation_instructions import parse_presentation_instructions

        instructions = parse_presentation_instructions(user_text)
        # safe fallback if last_query is None
        q = dict(st.session_state.last_query or {})
        q["render_id"] = str(uuid.uuid4())

        # Create a NEW assistant message with SAME results, NEW presentation
        st.session_state.messages.append({
            "role": "assistant",
            "content": "Here's the updated view based on your request:",
            "table": {
                "results": st.session_state.last_results,
                "query_json": q
            },
            "presentation": instructions
        })

        st.rerun()

    # ------------------------------------------------------------------
    # 🌍 QUERY TRANSLATION LAYER (BM / EN / MIXED → EN)
    # Translate user text only (not file content — avoid corrupting documents)
    # ------------------------------------------------------------------

    translated_text = translate_query_to_english(user_text)

    # Optional: show translation transparently (recommended)
    if translated_text.lower() != user_text.lower():
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"_🔄 Interpreted your query as:_ **{translated_text}**"
        })

    # Build enriched translated text for downstream LLM calls.
    # translated_text = clean user query (for FAISS/BM25 search)
    # effective_translated = translated query + file content (for all LLM calls)
    if file_context:
        file_names = ", ".join(st.session_state.file_contents.keys())
        effective_translated = (
            f"{translated_text}\n\n"
            f"[The user attached the following file(s): {file_names}]\n"
            f"[Attached File Content]\n{file_context}"
        )
    else:
        effective_translated = translated_text

    # ------------------------------------------------------------------
    # 🔥 INTENT ROUTER (LLM-based) — uses enriched query so it knows about files
    # ------------------------------------------------------------------

    recent_vendor_ids = []
    intent_result = route_intent(effective_translated, recent_vendor_ids)
    intent = intent_result.get("intent")


    # ---- 1️⃣ GREETING / SMALL TALK ----
    if intent == "greeting":
        st.session_state.messages.append({
            "role": "assistant",
            "content": (
                "Hi 👋 I can help you with:\n\n"
                "- 🔍 Finding vendors by capability, industry, location\n"
                "- 📄 Checking a vendor's certifications or profile\n"
                "- 📊 Reviewing spend, performance, and compliance\n\n"
                "Try something like:\n"
                "_"Cybersecurity vendors in Malaysia with ISO27001"_"
            )
        })
        st.rerun()


    # ---- 2️⃣ VENDOR FACT LOOKUP (NO SEARCH) ----
    if intent == "vendor_fact":
        vendor_identifier = intent_result.get("vendor_name_or_id")
        requested_field = intent_result.get("requested_field")

        answer = get_vendor_fact(
            vendor_identifier,
            requested_field,
            profiles
        )

        st.session_state.messages.append({
            "role": "assistant",
            "content": answer
        })
        st.rerun()

    # ---- 3️⃣ OTHERWISE → CONTINUE (vendor_search) ----
    # Check if user is asking about the file content itself (not searching for vendors)
    file_analysis_queries = [
        "what's in", "what is in", "what's this file", "what is this file",
        "what company", "which company", "who is this file for", "what organization",
        "summarize", "summary", "describe", "explain", "analyze this file",
        "what does this file", "tell me about this file", "what's in the file",
        "what information", "what details", "what data", "extract information"
    ]
        
    is_file_analysis_query = supporting_files and file_context and any(
        phrase in user_text.lower() for phrase in file_analysis_queries
    )
        
    # If user is asking about the file, analyze it directly
    if is_file_analysis_query:
        # Route to file analysis instead of vendor search
        analysis_prompt = f"""Analyze the uploaded file(s) and answer the user's question in detail.

User question: {translated_text}

File content:
{file_context}

Please provide a clear, comprehensive answer about the file content. If the question is about a company/organization, extract and identify it. If asking for a summary, provide a structured overview of the document."""
            
        from src.azure_llm import azure_chat as groq_chat
        messages = [
            {"role": "system", "content": "You are a helpful assistant that analyzes documents and answers questions about their content. Provide detailed, accurate answers based on the file content."},
            {"role": "user", "content": analysis_prompt}
        ]
            
        with st.spinner("Analyzing file content..."):
            analysis_response = groq_chat(messages, temperature=0.3)
            
        # Display the analysis directly
        st.session_state.messages.append({
            "role": "assistant", 
            "content": analysis_response
        })
        st.rerun()
        
    # Check if user is asking about vendor context (performance, sourcing events, etc.)
    # Only check if not a file analysis query
    context_query_handled = False

    # ------------------------------------------------------------------
    # 🤖 AI-DRIVEN SEARCH EXECUTION (REPLACES OLD PARSE LOGIC)
    # ------------------------------------------------------------------

    if not is_file_analysis_query and not context_query_handled:

        # 🔒 Prevent full database dump
        dangerous_phrases = [
            "all vendors",
            "entire database",
            "full list",
            "everything",
            "show all"
        ]

        if any(p in translated_text.lower() for p in dangerous_phrases):
            st.session_state.messages.append({
                "role": "assistant",
                "content": (
                    "For governance and performance reasons, "
                    "I cannot display the full vendor database at once.\n\n"
                    "Please narrow your request by industry, location, "
                    "certification, or capability."
                )
            })
            st.rerun()

        # 🧠 1️⃣ Intent Classification (uses enriched query)
        intent_data = classify_intent(effective_translated)
        ai_intent = intent_data.get("intent", "search_vendors")

        # 🧮 2️⃣ Aggregation Requests
        if ai_intent == "aggregate":
            plan = generate_search_plan(effective_translated)

            aggregation_result = aggregate_vendors(meta, plan["filters"])

            ai_reply = generate_response(
                effective_translated,
                results=[],
                aggregation=aggregation_result
            )

            st.session_state.messages.append({
                "role": "assistant",
                "content": ai_reply
            })

            st.rerun()

        # 🔍 3️⃣ Vendor Search
        if ai_intent == "search_vendors":

            # Planner sees enriched query (with file content) to extract filters
            plan = generate_search_plan(effective_translated)

            filters = plan.get("filters", {})
            # Dynamic threshold - retrieve all relevant results, pagination handles display
            limit = 50

            # FAISS/BM25 search uses clean translated_text (no file content)
            # to keep vector/keyword matching accurate
            results, filter_warning, show_only_top = search(
                index,
                bm25,
                docs,
                meta,
                translated_text,
                filters,
                {},
                [],
                "",
                top_k=limit
            )

            sort_key = SORT_OPTIONS.get(sort_by, "relevance")
            results = sort_results(results, sort_key)

            st.session_state.last_results = results
            st.session_state.last_query = plan

            # Responder sees enriched query so it can reference file content
            ai_reply = generate_response(
                effective_translated,
                results=results
            )

            st.session_state.messages.append({
                "role": "assistant",
                "content": ai_reply,
                "table": {
                    "results": results,
                    "query_json": {
                        "render_id": str(uuid.uuid4())
                    }
                }
            })

            st.rerun()

        else:
            st.session_state.messages.append({
                "role": "assistant",
                "content": "I couldn't interpret that request clearly. Could you rephrase it?"
            })
            st.rerun()
