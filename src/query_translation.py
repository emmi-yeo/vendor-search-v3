#from src.groq_client import groq_chat
from src.azure_llm import azure_chat as groq_chat

def translate_query_to_english(user_text: str) -> str:
    """
    Translate Malay / mixed-language procurement queries into clear English,
    preserving vendor names, certifications, acronyms, and intent.
    """

    system_prompt = (
        "You are a procurement search assistant.\n"
        "Translate the user's query into clear, natural English.\n\n"
        "Rules:\n"
        "- Preserve vendor names exactly\n"
        "- Preserve certifications (ISO27001, SOC2, PCI-DSS, etc.)\n"
        "- Preserve acronyms and technical terms\n"
        "- Do NOT add new constraints\n"
        "- Do NOT explain\n"
        "- Output ONLY the translated query\n"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]

    translated = groq_chat(messages, temperature=0)

    return translated.strip()

