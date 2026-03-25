import os
import json
import time
import uuid
import logging
from groq import Groq
from tavily import TavilyClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("search-agent")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
CLASSIFIER_MODEL = "llama-3.1-8b-instant"  # fast, cheap model for classification

groq_client = Groq(api_key=GROQ_API_KEY)
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

CLASSIFICATION_PROMPT = """Determine if the following user message requires a web search to answer accurately.

A web search IS needed for:
- Current events, news, recent happenings
- Weather forecasts or current conditions
- Stock prices, sports scores, or other live data
- Questions about specific products, services, or companies that may have recent updates
- Factual questions where the answer may have changed recently
- Questions the model likely cannot answer from training data alone

A web search is NOT needed for:
- General knowledge questions (math, science, history, definitions)
- Creative tasks (writing, brainstorming, coding)
- Conversational messages (greetings, opinions, advice)
- Questions about well-established facts unlikely to change

Respond with ONLY a JSON object, nothing else:
{"needs_search": true, "search_query": "optimized search query"} or {"needs_search": false}

User message: """


def classify_query(user_message: str) -> dict:
    """Use a fast model to decide if web search is needed."""
    try:
        response = groq_client.chat.completions.create(
            model=CLASSIFIER_MODEL,
            messages=[{"role": "user", "content": CLASSIFICATION_PROMPT + user_message}],
            temperature=0,
            max_tokens=150,
        )
        content = response.choices[0].message.content.strip()
        # Parse the JSON response
        # Handle potential markdown code fences
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(content)
        logger.info(f"Classification result: {result}")
        return result
    except Exception as e:
        logger.error(f"Classification failed: {e}, defaulting to no search")
        return {"needs_search": False}


def search_web(query: str) -> list:
    """Search the web using Tavily."""
    logger.info(f"🔍 Searching web for: {query}")
    try:
        response = tavily_client.search(query=query)
        results = response.get("results", [])
        logger.info(f"📄 Found {len(results)} results")
        return results
    except Exception as e:
        logger.error(f"Tavily search failed: {e}")
        return []


def format_search_context(results: list) -> str:
    """Format search results into a context block for the LLM."""
    if not results:
        return ""
    
    context_parts = ["Here are relevant web search results to help answer the user's question:\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "Untitled")
        url = r.get("url", "")
        content = r.get("content", "")
        context_parts.append(f"[{i}] {title}\nURL: {url}\n{content}\n")
    
    context_parts.append(
        "\nUse the above search results to provide an accurate, up-to-date answer. "
        "At the end of your response, include a '## Sources' section listing the sources "
        "you referenced as markdown links, e.g. `- [Title](URL)`."
    )
    return "\n".join(context_parts)


def run_agent(messages: list, model: str) -> str:
    """
    Main agent logic:
    1. Classify the user's query
    2. If search is needed, search and inject results
    3. Call Groq for the final response
    """
    # Get the last user message
    last_user_msg = ""
    for m in reversed(messages):
        if m["role"] == "user":
            last_user_msg = m["content"]
            break
    
    logger.info(f"💬 User: {last_user_msg}")
    
    # Step 1: Classify
    classification = classify_query(last_user_msg)
    
    # Step 2: Search if needed
    final_messages = list(messages)  # copy
    if classification.get("needs_search"):
        search_query = classification.get("search_query", last_user_msg)
        results = search_web(search_query)
        
        if results:
            context = format_search_context(results)
            # Inject search context as a system message before the last user message
            final_messages.insert(-1, {
                "role": "system",
                "content": context
            })
            logger.info("✅ Search context injected into prompt")
    else:
        logger.info("⏭️  No search needed for this query")
    
    # Step 3: Call Groq for final response
    logger.info(f"🤖 Generating response with model: {model}")
    response = groq_client.chat.completions.create(
        model=model,
        messages=final_messages,
        temperature=0.7,
    )
    
    answer = response.choices[0].message.content
    logger.info(f"✅ Response generated ({len(answer)} chars)")
    return answer
