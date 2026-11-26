"""Central LLM wrapper for all Claude calls.

Features
--------
- One entry point: llm.call(stage, system, messages, schema, temperature, model, images)
- Structured output via tool use with schema validation (Pydantic)
- Retry with exponential backoff on rate limits and 5xx
- One validation retry with the error text appended
- Cost logging to jobs/<job_id>/cost_log.json (and stdout)
- MAX_JOB_COST_USD abort
- MOCK_LLM=1 mode returns fixture files so CI never calls the network

Usage
-----
    from aivideo.llm import call

    result = call(
        stage      = "analysis",
        system     = "You are ...",
        messages   = [{"role": "user", "content": "..."}],
        schema     = AnalysisSchema,          # optional Pydantic model
        temperature= 0.3,
        images     = ["/path/to/frame.png"],  # optional base64 image blocks
    )
    # result is a dict (validated against schema if provided)
"""

import base64
import json
import os
import time
from pathlib import Path
from typing import Optional, Type

# Pydantic v2
try:
    from pydantic import BaseModel, ValidationError
    PYDANTIC_OK = True
except ImportError:
    PYDANTIC_OK = False
    BaseModel    = object
    ValidationError = Exception

# Cost estimates (USD per 1M tokens) — update when pricing changes
COST_PER_M = {
    "claude-sonnet-4-5":  {"in": 3.0,  "out": 15.0},
    "claude-haiku-3-5":   {"in": 0.25, "out": 1.25},
    "claude-opus-4-5":    {"in": 15.0, "out": 75.0},
}

_DEFAULT_MODEL = None


def _model() -> str:
    global _DEFAULT_MODEL
    if _DEFAULT_MODEL is None:
        _DEFAULT_MODEL = os.environ.get("AIVIDEO_MODEL", "claude-sonnet-4-5")
    return _DEFAULT_MODEL


def _max_cost() -> float:
    return float(os.environ.get("MAX_JOB_COST_USD", "2.00"))


# ── cost log ─────────────────────────────────────────────────────────────────

_COST_LOG_PATH: Optional[str] = None
_TOTAL_COST_USD: float = 0.0


def set_cost_log(path: str) -> None:
    """Point the cost log at a job-specific file."""
    global _COST_LOG_PATH, _TOTAL_COST_USD
    _COST_LOG_PATH = path
    _TOTAL_COST_USD = 0.0


def _log_cost(stage: str, model: str, in_tokens: int, out_tokens: int,
              latency: float, cost_usd: float) -> None:
    global _TOTAL_COST_USD
    _TOTAL_COST_USD += cost_usd
    entry = {
        "stage":     stage,
        "model":     model,
        "in_tokens": in_tokens,
        "out_tokens": out_tokens,
        "latency_s": round(latency, 2),
        "cost_usd":  round(cost_usd, 5),
        "total_usd": round(_TOTAL_COST_USD, 5),
        "ts":        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    print(f"[llm] {stage}  {model}  "
          f"in={in_tokens} out={out_tokens}  "
          f"${cost_usd:.4f}  total=${_TOTAL_COST_USD:.4f}  {latency:.1f}s")
    if _COST_LOG_PATH:
        log_file = Path(_COST_LOG_PATH)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        entries: list = []
        if log_file.exists():
            try:
                entries = json.loads(log_file.read_text())
            except Exception:
                pass
        entries.append(entry)
        log_file.write_text(json.dumps(entries, indent=2))


def _estimate_cost(model: str, in_tokens: int, out_tokens: int) -> float:
    rates = COST_PER_M.get(model, {"in": 3.0, "out": 15.0})
    return (in_tokens * rates["in"] + out_tokens * rates["out"]) / 1_000_000


# ── mock mode ────────────────────────────────────────────────────────────────

_MOCK_FIXTURES: dict[str, dict] = {}


def register_mock(stage: str, response: dict) -> None:
    """Register a fixture for a stage — used in tests."""
    _MOCK_FIXTURES[stage] = response


def _mock_response(stage: str) -> dict:
    if stage in _MOCK_FIXTURES:
        return _MOCK_FIXTURES[stage]
    # Return a minimal valid-looking dict
    return {
        "topic":  "Mock Topic",
        "scenes": [],
        "mock":   True,
        "stage":  stage,
    }


# ── image helpers ─────────────────────────────────────────────────────────────

def _image_block(path: str) -> dict:
    """Convert an image file to an Anthropic base64 image block."""
    ext   = Path(path).suffix.lower().lstrip(".")
    media = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
             "png": "image/png", "gif": "image/gif",
             "webp": "image/webp"}.get(ext, "image/png")
    data  = base64.standard_b64encode(Path(path).read_bytes()).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}}


# ── main call function ────────────────────────────────────────────────────────

def call(
    stage:       str,
    system:      str,
    messages:    list[dict],
    schema:      Optional[Type] = None,
    temperature: float = 0.3,
    model:       Optional[str] = None,
    images:      Optional[list[str]] = None,
    max_tokens:  int = 8000,
    _attempt:    int = 0,
) -> dict:
    """Make a Claude API call.

    Parameters
    ----------
    stage       : Label for cost/debug logging (e.g. "analysis", "storyboard")
    system      : System prompt text
    messages    : List of {"role": "user"|"assistant", "content": "..."}
    schema      : Optional Pydantic model — if provided, response is validated
    temperature : 0.0–1.0
    model       : Override AIVIDEO_MODEL
    images      : List of local image file paths to include in the last user message
    max_tokens  : Max output tokens

    Returns
    -------
    dict  — parsed JSON (validated against schema if provided)

    Raises
    ------
    RuntimeError  if MAX_JOB_COST_USD is exceeded
    RuntimeError  if validation fails after retry
    """
    # Mock mode
    if os.environ.get("MOCK_LLM", "0") == "1":
        print(f"[llm] MOCK_LLM=1 — returning fixture for stage '{stage}'")
        return _mock_response(stage)

    # Budget check
    if _TOTAL_COST_USD >= _max_cost():
        raise RuntimeError(
            f"[llm] Job cost ${_TOTAL_COST_USD:.4f} exceeds MAX_JOB_COST_USD={_max_cost():.2f}. Aborting."
        )

    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "anthropic package not installed. Run: pip install anthropic"
        )

    model_name = model or _model()
    client     = anthropic.Anthropic()

    # Attach images to the last user message if provided
    final_messages = list(messages)
    if images:
        last_msg = final_messages[-1]
        if last_msg["role"] == "user":
            content = last_msg["content"]
            if isinstance(content, str):
                content = [{"type": "text", "text": content}]
            else:
                content = list(content)
            for img_path in images:
                try:
                    content.append(_image_block(img_path))
                except Exception as e:
                    print(f"[llm] Could not attach image {img_path}: {e}")
            final_messages[-1] = {"role": "user", "content": content}

    # Build tool-use schema if provided
    tools = None
    tool_choice = None
    if schema is not None and PYDANTIC_OK:
        tool_schema = schema.model_json_schema() if hasattr(schema, "model_json_schema") \
                      else {"type": "object", "properties": {}}
        tools = [{
            "name":        "output",
            "description": f"Structured output for stage: {stage}",
            "input_schema": tool_schema,
        }]
        tool_choice = {"type": "tool", "name": "output"}

    # Retry loop
    backoff = 2.0
    for attempt in range(3):
        t0 = time.time()
        try:
            kwargs: dict = dict(
                model=model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=final_messages,
            )
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = tool_choice

            resp = client.messages.create(**kwargs)

        except Exception as e:
            err_str = str(e)
            # Rate limit or server error — retry
            if any(code in err_str for code in ["429", "529", "500", "503", "overloaded"]):
                wait = backoff * (2 ** attempt)
                print(f"[llm] {stage} attempt {attempt+1} error: {e} — retrying in {wait:.0f}s")
                time.sleep(wait)
                continue
            raise

        latency    = time.time() - t0
        in_tokens  = getattr(resp.usage, "input_tokens",  0)
        out_tokens = getattr(resp.usage, "output_tokens", 0)
        cost_usd   = _estimate_cost(model_name, in_tokens, out_tokens)
        _log_cost(stage, model_name, in_tokens, out_tokens, latency, cost_usd)

        # Extract text
        raw = ""
        if tools:
            # tool-use response
            for block in resp.content:
                if getattr(block, "type", "") == "tool_use" and block.name == "output":
                    raw_dict = block.input
                    if schema is not None and PYDANTIC_OK:
                        try:
                            validated = schema.model_validate(raw_dict)
                            return validated.model_dump()
                        except ValidationError as ve:
                            if _attempt == 0:
                                # One validation retry: append error to messages
                                retry_msgs = final_messages + [{
                                    "role": "user",
                                    "content": (
                                        f"Your previous output failed validation:\n{ve}\n"
                                        "Please fix it and return a valid response."
                                    )
                                }]
                                return call(stage, system, retry_msgs, schema,
                                            temperature, model, None, max_tokens, _attempt=1)
                            raise RuntimeError(f"[llm] Validation failed after retry: {ve}")
                    return raw_dict if isinstance(raw_dict, dict) else {"result": raw_dict}
        else:
            # plain text response — parse JSON
            for block in resp.content:
                if hasattr(block, "text"):
                    raw += block.text
            raw = raw.strip()
            # Strip markdown fences
            import re
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.M).strip()
            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                # Try to find JSON object in the response
                m = re.search(r"\{.*\}", raw, re.DOTALL)
                if m:
                    try:
                        result = json.loads(m.group(0))
                    except Exception:
                        result = {"raw": raw}
                else:
                    result = {"raw": raw}

            if schema is not None and PYDANTIC_OK:
                try:
                    validated = schema.model_validate(result)
                    return validated.model_dump()
                except ValidationError as ve:
                    if _attempt == 0:
                        retry_msgs = final_messages + [{
                            "role": "user",
                            "content": (
                                f"Your previous output failed validation:\n{ve}\n"
                                "Please fix and return valid JSON."
                            )
                        }]
                        return call(stage, system, retry_msgs, schema,
                                    temperature, model, None, max_tokens, _attempt=1)
                    raise RuntimeError(f"[llm] Validation failed after retry: {ve}")
            return result

    raise RuntimeError(f"[llm] All retries exhausted for stage '{stage}'")


# ── convenience wrappers ──────────────────────────────────────────────────────

def call_cheap(stage: str, system: str, messages: list[dict], **kwargs) -> dict:
    """Use Haiku for fast/cheap checks (rubric scoring, grounding checks)."""
    return call(stage, system, messages,
                model=os.environ.get("AIVIDEO_CHEAP_MODEL", "claude-haiku-3-5"),
                **kwargs)


def call_vision(stage: str, system: str, messages: list[dict],
                images: list[str], **kwargs) -> dict:
    """Convenience wrapper that always includes image blocks."""
    return call(stage, system, messages, images=images, **kwargs)
