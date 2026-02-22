# Written Answers — ClearPath RAG Chatbot

---

## Q1 — Routing Logic

### The Exact Rules

The router applies eight rules in order; the first match wins:

| # | Name | Condition | Classification |
|---|------|-----------|----------------|
| R1 | Greeting | Query is a social opener (hi, hello, thanks, bye…) with ≤5 words | simple |
| R2 | Very short | Word count ≤ 6 AND ≤ 1 question mark | simple |
| R3 | Single-fact lookup | Matches phrases like "what is / who is / how many / list" AND word count < 15 AND no complaint keywords | simple |
| R4 | Long query | Word count ≥ 25 | complex |
| R5 | Multiple questions | ≥ 2 question marks | complex |
| R6 | Reasoning keyword | Contains any of: why, how does, explain, compare, difference between, troubleshoot, integrate, configure, best practice, recommend, step-by-step… | complex |
| R7 | Complaint signal | Contains: not working, broken, error, bug, can't, issue, problem… | complex |
| R8 | Conditional multi-step | Contains if/when/unless AND then/should/will/can in the same query | complex |
| Default | — | None of the above matched | simple |

**Why this boundary?**  
The boundary is intentionally aggressive about catching complexity. The 8B model is fast and cheap, so the system tilts toward it for anything that looks like a single retrieval task. The moment a query requires reasoning across multiple pieces of evidence (comparisons, how-to explanations, debugging chains) or signals dissatisfaction (complaint keywords), the larger model is invoked. This matches intuition: a user who types "price?" just needs a lookup, while a user who types "why isn't the webhook firing after I updated the endpoint URL?" needs multi-step reasoning.

**A real misclassification:**  
Query: *"What integrations does ClearPath support?"*  
Classification: `simple` (R3 — "what" + "support" + short)  
What happened: The word "support" is short and looks like a single-fact lookup, so R3 fires. In practice this question requires synthesising the Integrations Catalog (doc 09) which lists 50+ tools across categories — the 8B model can still answer it, but a shorter, less organised response was observed compared to the 70B model. The fix would be to exclude queries mentioning "integrations" from R3 and always send them to complex, since they require catalogue synthesis.

**If I had more time (without an LLM):**  
I would add a token-budget heuristic: if the top-k chunk relevance scores are spread across more than N distinct documents (e.g. > 3 source PDFs), that is a signal the question requires multi-document synthesis, which is harder, and the query should be re-routed to complex regardless of which rule initially fired. This can be computed post-retrieval with no extra LLM cost.

---

## Q2 — Retrieval Failures

### Observed failure

**Query:** *"What is the refund policy?"*

**What the system retrieved:** Chunks from `14_Pricing_Sheet_2024.pdf` and `15_Enterprise_Plan_Details.pdf` discussing plan tiers and costs — not refund terms.

**Why retrieval failed:**  
ClearPath documentation does not appear to contain a dedicated "refund policy" section. The TF-IDF similarity between "refund policy" and the pricing chunks is non-zero (they share pricing vocabulary), so the retriever returns plausible-looking but ultimately wrong chunks. The LLM correctly noted it could not find refund information but cited chunks about pricing plans, which could mislead a user skimming the sources.

**Root cause:**  TF-IDF is a bag-of-words model. The query "refund policy" and the pricing docs share terms like "plan", "cost", and "enterprise", but the semantic concept of a refund policy is absent. A dense embedding model (e.g., sentence-transformers) would represent "refund policy" in a space where it is far from "monthly pricing", and either return a near-zero score (triggering the no-context flag) or be correctly close to a refund-specific passage if one existed.

**Fix:**  
1. Replace TF-IDF with dense retrieval (BGE-small or MiniLM via sentence-transformers): the improved semantic coverage would reduce false-positive chunk matches.  
2. Set a stricter minimum score threshold (current: 0.05) so that weakly matching chunks are excluded and the no_context flag fires, alerting the user immediately.

---

## Q3 — Cost and Scale

### Assumptions

| Parameter | Value |
|-----------|-------|
| Daily queries | 5,000 |
| Router split (estimated) | 70% simple, 30% complex |
| Average input tokens (simple) | ~1,200 (system prompt ≈ 250 + 5 chunks × ~180 chars ≈ 700 + query ≈ 250) |
| Average output tokens (simple) | ~150 |
| Average input tokens (complex) | ~1,800 (larger context + longer query) |
| Average output tokens (complex) | ~300 |

### Daily token calculation

| Model | Daily queries | Input T/query | Output T/query | Daily input tokens | Daily output tokens |
|-------|--------------|---------------|----------------|--------------------|---------------------|
| llama-3.1-8b-instant | 3,500 | 1,200 | 150 | 4,200,000 | 525,000 |
| llama-3.3-70b-versatile | 1,500 | 1,800 | 300 | 2,700,000 | 450,000 |
| **Total** | **5,000** | | | **6,900,000** | **975,000** |

**Total daily tokens ≈ 7.87 million**

### Biggest cost driver

Input tokens to the 70B model dominate. Even though it handles only 30% of queries, each call is 50% more expensive per token than the 8B model and each call carries a larger prompt. The 70B model accounts for ~39% of input tokens but likely 60–70% of proportional cost at commercial rates.

### Highest-ROI optimisation

**Reduce the context window sent to the LLM** — specifically the number of retrieved chunks from 5 to 3 for simple queries. This alone cuts simple-query input tokens by ~30% (saves ≈ 1.26M input tokens/day) with minimal quality loss, because simple queries need at most 2 well-matched chunks. This is low-risk, immediately deployable, and does not affect routing or evaluation logic.

### Optimisation I would avoid

**Prompt compression / token-shrinking the system prompt** using an LLM. While this can save tokens, it introduces a second LLM call per request, doubles latency for the pre-processing step, and adds a new failure mode. The savings per query are small  (maybe 50–80 tokens) and the operational complexity is disproportionate. Better to reduce chunk count than to compress the system prompt.

---

## Q4 — What Is Broken

### The Most Significant Flaw: TF-IDF Retrieval Misses Semantically Equivalent Queries

The RAG pipeline uses TF-IDF with cosine similarity. This is a term-overlap model — it only matches words that appear literally in both the query and the document chunks. It fails badly on:

- **Paraphrase variation**: "How do I cancel my subscription?" vs chunks containing "terminate account" or "end your plan"
- **Acronyms and synonyms**: "PM tool" vs "project management software"
- **Conceptual questions**: "Is ClearPath safe for sensitive data?" maps poorly to a Security & Privacy Policy that never uses the word "safe"

In a real deployment, 15–25% of queries would return irrelevant or zero chunks — every one of these is either a hallucinated answer or a blunt "I don't know" the user has to escalate to human support.

### Why I shipped with it

Building a dense retrieval pipeline (sentence-transformers + FAISS / cosine on embeddings) was achievable within the time constraints, but the assignment explicitly forbids external RAG-as-a-service tools. An embedding model like `all-MiniLM-L6-v2` runs locally but requires an additional Python package (sentence-transformers), a one-time encode step of ~30 seconds for 30 PDFs, and ~45 MB of model weights. I chose TF-IDF to keep the dependency surface minimal and the setup zero-cloud, which makes local evaluation simpler — the downside is obvious semantic brittleness.

### Single highest-impact fix

Replace the TF-IDF retriever with a local dense retriever using `sentence-transformers` (e.g., `all-MiniLM-L6-v2`). Encode all chunks once at startup, store numpy vectors, and use cosine similarity on 384-dimensional dense vectors. This requires changing < 40 lines in `rag_pipeline.py`, adds one dependency, and would dramatically reduce zero-chunk / wrong-chunk retrievals with no API calls.

---

## AI Usage

The following prompts were given to an AI assistant during this assignment:

1. **TF-IDF retrieval:** "In Python with sklearn, build a TF-IDF retriever over document chunks. Fit on a list of chunk strings, then for a query return top-k chunk indices by cosine similarity. No external RAG libraries."
2. **Router logic:** "Python function: given a query string, classify as 'simple' or 'complex' using only string/regex checks—no API calls. Rules: greeting (hi, hello, thanks) → simple; 2+ question marks → complex; words like explain, compare, troubleshoot, configure → complex; long query (e.g. ≥25 words) → complex. Return the label."
3. **Evaluator flags:** "Python: given the model answer text and the list of retrieved chunk texts, detect (a) refusal phrases like 'I don't have' or 'not mentioned', (b) answer has 3+ distinct dollar amounts. Return dict with boolean flags."
4. **Groq API:** "Call Groq chat completions API in Python: system prompt, user message, return response text and usage (input/output tokens). Model name as parameter."
5. **FastAPI + Pydantic:** "FastAPI POST endpoint: body has 'query' and optional 'conversation_id'. Response must include answer, sources list, model_used, tokens.input, tokens.output. Pydantic response model."

