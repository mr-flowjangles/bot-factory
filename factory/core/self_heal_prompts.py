"""
Self-Healing Knowledge Base — LLM Prompt Templates

Prompts used by the self-heal pipeline for boundary checking,
YML data generation, and content validation.
"""

BOUNDARY_CHECK_PROMPT = """You are a boundary checker for a chatbot called "{bot_name}".

The bot's domain boundaries are:
{boundaries}

The bot's personality is: {personality}

A user asked: "{question}"

First, determine if this is a clear, coherent question that someone would actually want an answer to.
Reject anything that is:
- Gibberish, incomplete, or incoherent (e.g. "hi can you tell me how", "asdf", "what about the")
- A greeting or small talk (e.g. "hi", "thanks", "hello there")
- Too vague to identify a topic (e.g. "tell me stuff", "what do you think")

Then, if it IS a clear question, determine if it's within the bot's domain.

Answer with ONLY "yes" or "no" followed by a brief reason.

Examples:
yes — this is a clear question about guitar tuning which is within the music domain
no — this is about cooking which is outside the guitar/music domain
no — this is an incomplete/incoherent message, not a real question"""


YML_GENERATION_PROMPT = """You are a knowledge base author for a chatbot called "{bot_name}".

Generate a YAML data entry to answer this question: "{question}"

The entry must follow this exact format (this is a real example from the existing knowledge base):

```yaml
entries:
  - id: {entry_id}
    format: text
    category: {category}
    heading: {heading}
    search_terms: "{search_terms}"
    content: |
      [Your detailed, accurate content here. Write in a clear, informative style.
      Include specific details, examples, and practical advice where appropriate.
      Keep it factual and helpful.]
```

Requirements:
- The `id` must be: {entry_id}
- Pick an appropriate `category` from: {categories}
- The `heading` should be a clear, descriptive title
- `search_terms` should include relevant keywords and phrases users might search for
- `content` should be thorough but concise (2-4 paragraphs)
- Write factual, accurate information only
- Use the "text" format (not "structured")
- Output ONLY the valid YAML block, no extra text before or after"""


VALIDATION_PROMPT = """You are a fact-checker reviewing auto-generated content for a chatbot knowledge base.

The bot "{bot_name}" generated this content to answer: "{question}"

Generated content:
---
{content}
---

Review this content for:
1. Factual accuracy — are there any incorrect statements?
2. Completeness — does it adequately address the question?
3. Quality — is it well-written and helpful?

Answer with ONLY "pass" or "fail" followed by a brief explanation.

Examples:
pass — content is factually accurate and addresses the question well
fail — the content incorrectly states that standard tuning is DADGAD"""
