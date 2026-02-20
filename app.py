import streamlit as st
import pandas as pd
import os
import json
import hashlib
from dotenv import load_dotenv
import uuid

from src.build_index import build_vendor_documents, build_faiss_and_bm25
from src.query_parser import parse_query
from src.retrieval import search
from src.feedback import add_feedback, get_feedback_summary
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

# ---- Sidebar filters (dynamic) ----
# st.sidebar.header("Filters")

# Sort option
# sort_by = st.sidebar.selectbox("Sort by", list(SORT_OPTIONS.keys()), index=0)

# all_industries = sorted({str(x) for x in profiles["industry"].dropna().unique()})
# all_countries = sorted({str(x) for x in profiles["country"].dropna().unique()})
# all_states = sorted({str(x) for x in profiles["state"].dropna().unique()})
# all_cities = sorted({str(x) for x in profiles["city"].dropna().unique()})

# industry = st.sidebar.multiselect("Industry", all_industries)
# country = st.sidebar.selectbox("Country", [""] + all_countries)
# state = st.sidebar.multiselect("State", all_states)
# city = st.sidebar.multiselect("City", all_cities)

# certifications could be multi-value; for POC, let user type or choose from extracted tokens
# cert_input = st.sidebar.text_input("Certifications (comma separated)", value="")

# ui_filters = {
#     "industry": industry,
#     "country": country,
#     "state": state,
#     "city": city,
#     "certifications": [c.strip() for c in cert_input.split(",") if c.strip()]
# }

# current_filter_hash = hash_filters(ui_filters)
# if "last_filter_hash" not in st.session_state:
#     st.session_state.last_filter_hash = current_filter_hash

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

RESULTS_PER_PAGE = 10
def render_search_results_in_chat(
        results,
        query_json,
        presentation=None
    ):
        """
        Render search results as a ChatGPT-style assistant response,
        including tables, copy formats, and export.
        """
        if presentation is None:
            presentation = {}

        import hashlib
        import json

        render_id = query_json.get("render_id")

        if not render_id:
            render_id = f"auto_{uuid.uuid4()}"


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

        # Limit rows
        if limit:
            df = df.head(limit)

        # Render
        st.dataframe(df, use_container_width=True)


        st.markdown("#### 📥 Export")
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
        "", top_k=8,  # embed_model parameter kept for compatibility but not used
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


# Auto-rerun ONLY when filters actually changed (and we have a prior query)
if st.session_state.last_query and (current_filter_hash != st.session_state.last_filter_hash):
    # model parameter kept for compatibility but not used (uses Groq from env)
    # refreshed = parse_query("", st.session_state.last_query["search_text"], ui_filters)
    # results, filter_warning, show_only_top = run_search_from_query(refreshed)

    # Append as a real assistant message (conversation-friendly)
    lines = []
    if filter_warning:
        lines.append("⚠️ No vendors matched the current filters exactly. Showing closest matches globally.")
    lines.append("**Updated results (based on current filters):**")
    if show_only_top:
        lines.append("_High-confidence match found — showing top results only._")

    if not results:
        lines.append("No strong matches under the current filters. Try loosening location/certifications or adding capability keywords.")
    else:
        # Show logic interpretation if available
        if refreshed.get("logic_operators"):
            logic_info = []
            for key, op in refreshed["logic_operators"].items():
                if op:
                    logic_info.append(f"{key}: {op}")
            if logic_info:
                lines.append(f"_Logic: {', '.join(logic_info)}_")
            
        for r in results:
            score_info = f"score `{r['final_score']}`"
            if r.get('compliance_score') is not None:
                score_info += f" | Compliance: {r['compliance_score']} | Risk: {r['risk_score']} | Performance: {r['performance_score']}"
            lines.append(
                f"- **{r['vendor_name']}** (ID: `{r['vendor_id']}`) — {score_info}  \n"
                f"  {r['industry']} | {r['location']}  \n"
                f"  Certs: {r['certifications']}"
            )
            # Add ranking reasons if available
            if r.get('ranking_reasons'):
                reasons_text = " • ".join(r['ranking_reasons'])
                lines.append(f"  _Ranked high because: {reasons_text}_")
            if r.get('matched_attachments'):
                att_text = ", ".join(r['matched_attachments'])
                lines.append(f"  📎 _Matched attachments: {att_text}_")

    msg = "\n".join(lines)
    q_with_render = dict(q)
    q_with_render["render_id"] = str(uuid.uuid4())

    st.session_state.messages.append({
        "role": "assistant",
        "content": msg,
        "table": {
            "results": results,
            "query_json": q_with_render
        }
    })


    # Update last_filter_hash so it doesn't rerun repeatedly
    st.session_state.last_filter_hash = current_filter_hash

    # Re-render messages after appending
    st.rerun()


# Check for pending query from prompt button (before chat input)
pending_query = None
if "pending_query" in st.session_state and st.session_state.pending_query:
    pending_query = st.session_state.pending_query
    # Clear it after reading
    del st.session_state.pending_query

ALLOWED_FILE_TYPES = ["pdf", "docx", "xlsx", "xls", "png", "jpg", "jpeg"]
MAX_UPLOAD_SIZE_MB = 10

def validate_uploaded_file(uploaded_file):
    # Extension validation
    filename = uploaded_file.name
    _, ext = os.path.splitext(filename)
    ext = ext.lower()

    if ext not in ALLOWED_FILE_TYPES:
        return False, f"Unsupported file type: {ext}. Allowed types: {', '.join(ALLOWED_FILE_TYPES)}"

    # Size validation
    file_size_mb = uploaded_file.size / (1024 * 1024)
    if file_size_mb > MAX_UPLOAD_SIZE_MB:
        return False, f"File too large ({file_size_mb:.2f}MB). Maximum allowed size is {MAX_UPLOAD_SIZE_MB}MB."

    # Empty file validation
    if uploaded_file.size == 0:
        return False, "Uploaded file is empty."

    return True, "Valid"
 
# New user input - always at the bottom
user_input = st.chat_input(
    "Ask for vendors in natural language…",
    accept_file=True,
    file_type=ALLOWED_FILE_TYPES,  # restrict extensions at UI level
    max_upload_size=MAX_UPLOAD_SIZE_MB
)   
    
# Handle user input (text and/or files) OR pending query from prompt button
if user_input or pending_query:
    # Use pending_query if available, otherwise extract from user_input
    if pending_query:
        user_text = pending_query
        uploaded_files = []
    else:
        # Extract text and files from input
        # When accept_file=True, user_input is a dict-like object with 'text' and 'files' attributes
        if hasattr(user_input, "text") or hasattr(user_input, "files"):
            # Dict-like object (ChatInputValue) when files are enabled - supports attribute notation
            user_text = getattr(user_input, "text", "") or ""
            uploaded_files = getattr(user_input, "files", []) or []
        elif isinstance(user_input, (dict, str)):
            # Dictionary or string (backward compatibility)
            if isinstance(user_input, dict):
                user_text = user_input.get("text", "")
                uploaded_files = user_input.get("files", [])
            else:
                user_text = str(user_input)
                uploaded_files = []
        else:
            # Fallback
            user_text = str(user_input) if user_input else ""
            uploaded_files = []
        
    file_contents = {}
    validated_files = []

    if uploaded_files:
        for file in uploaded_files:
            is_valid, message = validate_uploaded_file(file)

            if not is_valid:
                st.error(message)
            else:
                validated_files.append(file)

        # If all files invalid → stop
        if not validated_files:
            st.stop()

        # Only process validated files
        with st.spinner("Processing uploaded files..."):
            file_contents = process_uploaded_files(validated_files)
            
        # Store file info for processing
        if "uploaded_files" not in st.session_state:
            st.session_state.uploaded_files = []
        for file in validated_files:
            st.session_state.uploaded_files.append({
                "name": file.name,
                "size": file.size,
                "type": file.type,
                "data": file.getvalue()
            })
            
        # Show file processing results
        if file_contents:
            file_summary = []
            for file_name, content in file_contents.items():
                content_preview = content[:200] + "..." if len(content) > 200 else content
                file_summary.append(f"📎 {file_name} ({len(content)} chars)")
            if file_summary:
                st.info("Processed files: " + " | ".join(file_summary))
        
    # Process text input (or file-only input)
    if user_text or uploaded_files:
        # Add user message to session state (will be rendered in the loop above on rerun)
        message_content = user_text
        if uploaded_files:
            file_info = " | Files: " + ", ".join([f.name for f in uploaded_files])
            message_content += file_info
        st.session_state.messages.append({"role": "user", "content": message_content})
        
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
            "content": "Here’s the updated view based on your request:",
            "table": {
                "results": st.session_state.last_results,
                "query_json": q
            },
            "presentation": instructions
        })

        st.rerun()


    # Format file content for LLM (include in query context)
    file_context = ""
    if file_contents:
        file_context = format_file_content_for_llm(file_contents, max_length=8000)
    # ------------------------------------------------------------------
    # 🔥 INTENT ROUTER (LLM-based) — MUST RUN BEFORE ANY SEARCH / CONTEXT
    # ------------------------------------------------------------------

    recent_vendor_ids = []

    # ------------------------------------------------------------------
    # 🌍 QUERY TRANSLATION LAYER (BM / EN / MIXED → EN)
    # ------------------------------------------------------------------

    translated_text = translate_query_to_english(user_text)

    # Optional: show translation transparently (recommended)
    if translated_text.lower() != user_text.lower():
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"_🔄 Interpreted your query as:_ **{translated_text}**"
        })

    # ------------------------------------------------------------------
    # 🔥 INTENT ROUTER (LLM-based)
    # ------------------------------------------------------------------

    intent_result = route_intent(translated_text, recent_vendor_ids)
    intent = intent_result.get("intent")


    # ---- 1️⃣ GREETING / SMALL TALK ----
    if intent == "greeting":
        st.session_state.messages.append({
            "role": "assistant",
            "content": (
                "Hi 👋 I can help you with:\n\n"
                "- 🔍 Finding vendors by capability, industry, location\n"
                "- 📄 Checking a vendor’s certifications or profile\n"
                "- 📊 Reviewing spend, performance, and compliance\n\n"
                "Try something like:\n"
                "_“Cybersecurity vendors in Malaysia with ISO27001”_"
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
        
    is_file_analysis_query = uploaded_files and file_context and any(
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
            
        #from src.groq_client import groq_chat
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
    #if not is_file_analysis_query:
        # Get recent vendor IDs from last search results for context
    #    recent_vendor_ids = []

        # Detect if this is a vendor context query
    #    context_detection = detect_context_query(translated_text, recent_vendor_ids)
            
    #    if context_detection.get('is_context_query') and context_detection.get('vendor_identifier'):
    #        vendor_identifier = context_detection['vendor_identifier']
    #        context_type = context_detection.get('context_type', 'general')
    #        query_intent = context_detection.get('query_intent', user_text)
                
            # Find vendor by ID, name, or "this vendor"/"that vendor"
    #        from src.vendor_context_query import find_vendor_by_identifier
    #        vendor_found = find_vendor_by_identifier(vendor_identifier, profiles, recent_vendor_ids)
                
    #        if vendor_found:
                # Generate context answer (optionally with external enrichment)
    #            enrichment = None
    #            if EXTERNAL_ENRICHMENT_ENABLED and is_enrichment_enabled():
    #                try:
    #                    v_row = profiles[profiles["vendor_id"] == vendor_found].iloc[0]
    #                    vendor_profile = {
    #                        "vendor_id": vendor_found,
    #                        "vendor_name": v_row.get("vendor_name", ""),
    #                        "country": v_row.get("country", ""),
    #                        "city": v_row.get("city", ""),
    #                        "industry": v_row.get("industry", ""),
    #                    }
    #                    enrichment = build_enrichment_profile(vendor_profile)
    #                except Exception:
    #                    enrichment = None

    #            with st.spinner(f"Analyzing vendor context for {vendor_found}..."):
    #                context_answer = answer_context_query(
    #                    vendor_found,
    #                    context_type,
    #                    query_intent,
    #                    profiles,
    #                    txns,
    #                    attachments,
    #                    enrichment=enrichment,
    #                )
    #                
    #            # Display the context answer
    #            st.session_state.messages.append({
    #                "role": "assistant",
    #                "content": context_answer
    #            })
    #            context_query_handled = True
    #            st.rerun()
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

        # 🧠 1️⃣ Intent Classification
        intent_data = classify_intent(translated_text)
        ai_intent = intent_data.get("intent", "search_vendors")

        # 🧮 2️⃣ Aggregation Requests
        if ai_intent == "aggregate":
            plan = generate_search_plan(translated_text)

            aggregation_result = aggregate_vendors(meta, plan["filters"])

            ai_reply = generate_response(
                translated_text,
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

            plan = generate_search_plan(translated_text)

            filters = plan.get("filters", {})
            limit = min(plan.get("limit", 10), 20)

            # Run hybrid search
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

            # Apply sidebar sorting
            sort_key = SORT_OPTIONS.get(sort_by, "relevance")
            results = sort_results(results, sort_key)

            # Save state
            st.session_state.last_results = results
            st.session_state.last_query = plan

            # 🤖 Generate AI explanation
            ai_reply = generate_response(
                translated_text,
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

        # 🧾 Fallback
        st.session_state.messages.append({
            "role": "assistant",
            "content": "I couldn’t interpret that request clearly. Could you rephrase it?"
        })

        st.rerun()

    if not is_file_analysis_query and not context_query_handled:
        # q = parse_query("", translated_text, ui_filters, file_context=file_context)
        # results, filter_warning, show_only_top = run_search_from_query(q)
        st.session_state.last_filter_hash = current_filter_hash
        if show_only_top:
            st.markdown("_High-confidence match found — showing top results only._")

        lines = []

        if q.get("needs_clarification"):
            lines.append(f"Before I search deeply: **{q.get('clarifying_question','What constraints should I use?')}**")
            lines.append("_Meanwhile, here are the best-guess matches:_")

        if filter_warning:
            lines.append("⚠️ No vendors matched **all** requested constraints. Showing closest matches (some may be near-misses).")

        if show_only_top:
            lines.append("_High-confidence match found — showing top results only._")
            
        if q.get("logic_operators"):
            logic_info = []
            for key, op in q["logic_operators"].items():
                if op:
                    logic_info.append(f"{key}: {op}")
            if logic_info:
                lines.append(f"_Interpreted logic: {', '.join(logic_info)}_")

        if not results:
            lines.append("No **strong** matches found under current constraints. Try loosening filters (location/certifications) or add more capability keywords (e.g., SOC, SIEM, OT, audit).")
        else:
            total_results = len(results)
            total_pages = (total_results + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE
            current_page = st.session_state.results_page
                
            if total_pages > 1:
                lines.append(f"_Showing page {current_page + 1} of {total_pages} ({total_results} total results)_")
                start_idx = current_page * RESULTS_PER_PAGE
                end_idx = min(start_idx + RESULTS_PER_PAGE, total_results)
                paginated_results = results[start_idx:end_idx]
            else:
                paginated_results = results
                
            if paginated_results:
                exact_paginated = [r for r in paginated_results if r.get("is_exact_match")]
                near_paginated = [r for r in paginated_results if not r.get("is_exact_match")]
                    
                if exact_paginated:
                    lines.append("**Exact / strong matches:**")
                    for r in exact_paginated:
                        score_info = f"score `{r['final_score']}`"
                        if r.get('compliance_score') is not None:
                            score_info += f" | Compliance: {r['compliance_score']} | Risk: {r['risk_score']} | Performance: {r['performance_score']}"
                        lines.append(
                            f"- **{r['vendor_name']}** (ID: `{r['vendor_id']}`) — {score_info}  \n"
                            f"  {r['industry']} | {r['location']}  \n"
                            f"  Certs: {r['certifications']}"
                        )
                        if r.get('ranking_reasons'):
                            reasons_text = " • ".join(r['ranking_reasons'])
                            lines.append(f"  _Ranked high because: {reasons_text}_")
                        if r.get('matched_attachments'):
                            att_text = ", ".join(r['matched_attachments'])
                            lines.append(f"  📎 _Matched attachments: {att_text}_")

                if near_paginated:
                    lines.append("")
                    lines.append("**Near matches (don't meet all constraints):**")
                    for r in near_paginated:
                        score_info = f"score `{r['final_score']}`"
                        if r.get('compliance_score') is not None:
                            score_info += f" | Compliance: {r['compliance_score']} | Risk: {r['risk_score']} | Performance: {r['performance_score']}"
                        lines.append(
                            f"- **{r['vendor_name']}** (ID: `{r['vendor_id']}`) — {score_info}  \n"
                            f"  {r['industry']} | {r['location']}  \n"
                            f"  Certs: {r['certifications']}"
                        )
                        if r.get('ranking_reasons'):
                            reasons_text = " • ".join(r['ranking_reasons'])
                            lines.append(f"  _Ranked high because: {reasons_text}_")
                        if r.get('matched_attachments'):
                            att_text = ", ".join(r['matched_attachments'])
                            lines.append(f"  📎 _Matched attachments: {att_text}_")
                            
                        lines.append(f"  [View Context](#vendor_{r['vendor_id']})")
                            
                        result_key = f"result_{r['vendor_id']}"
                        if result_key not in st.session_state:
                            st.session_state[result_key] = r

        msg = "\n".join(lines)

        if st.session_state.get("_last_handled_query") == user_text:
            st.stop()

        st.session_state.messages.append({
            "role": "assistant",
            "content": msg,
            "table": {
                "results": results,
                "query_json": q
            }
        })

        st.session_state["_last_handled_query"] = user_text

        st.rerun()

