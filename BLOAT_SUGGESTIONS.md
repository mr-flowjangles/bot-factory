# Package Bloat Suggestions

Based on a quick static scan of imports vs. `requirements.txt`, here are likely bloat reductions:

## 1) Remove unused `openai` dependency (high confidence)

- `openai` is listed in:
  - `api/requirements.txt`
  - `factory/requirements.txt`
  - `factory/bots/requirements.txt`
- I did not find any `import openai` usage in Python source files.
- Embedding generation currently uses AWS Bedrock (`boto3.client('bedrock-runtime')`) rather than OpenAI.

**Suggestion:** Remove `openai` from requirements unless you plan to reintroduce OpenAI embedding calls.

## 2) Remove duplicate requirements files or consolidate (medium confidence)

- There are three near-identical requirements files:
  - `api/requirements.txt`
  - `factory/requirements.txt`
  - `factory/bots/requirements.txt`
- This increases maintenance overhead and drift risk.

**Suggestion:** Prefer a shared base requirements file + per-service overlays, or one canonical requirements file if runtime environments are identical.

## 3) Review `botocore.session` pinned as a top-level package (medium confidence)

- `botocore.session>=1.28.0` appears in two requirements files.
- `botocore` is normally brought transitively by `boto3`; explicit pinning can create dependency conflicts unless strictly needed.

**Suggestion:** If you only use `boto3` and simple `botocore.session` imports, try removing explicit `botocore.session` from top-level requirements and rely on `boto3`'s compatible `botocore` version.

## 4) Minor code-level cleanup opportunities

- There is at least one suspicious/likely-unused import: `from pyexpat.errors import messages` in `factory/core/chatbot.py`.

**Suggestion:** Remove unused imports and run a linter (`ruff`/`flake8`) to keep dependency and import surface clean.

---

## Suggested next validation steps

1. Remove `openai` from requirements files in a branch.
2. Rebuild and run the app/services.
3. Run smoke tests for embedding generation and chat endpoints.
4. If all green, keep it removed.

