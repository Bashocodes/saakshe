#!/usr/bin/env python
"""arivu — live Vertex connectivity probe (the riskiest vertical slice).

Run this the moment Vertex ADC is set up. It proves, end to end, that the two
model families arivu needs can actually answer in YOUR project + region:

  1. Gemini via Vertex     (the chair-orchestrator + the five mantris)
  2. Claude via Vertex      (the verdict synthesiser + the prosecutor)

Claude-on-Vertex is the most setup-sensitive piece — Model Garden enablement is
per-project, and the model is region-restricted. So if the configured id/region
fails, the probe SWEEPS a fallback matrix and tells you exactly which
(model, region) pairs your project will actually serve.

Usage:
    gcloud auth application-default login
    export GOOGLE_CLOUD_PROJECT=your-project
    python scripts/probe_vertex.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from arivu import config  # noqa: E402

OK, FAIL, INFO = "\033[32m✓\033[0m", "\033[31m✗\033[0m", "\033[2m·\033[0m"


def _project() -> str | None:
    return config.GOOGLE_CLOUD_PROJECT or os.environ.get("GOOGLE_CLOUD_PROJECT")


# Preference-ordered Gemini candidates (NEWEST FIRST). The sweep reports which this
# project actually serves, so we run the BEST available Pro + Flash — the user has
# hackathon credit and wants the strongest showcase. DISCOVER, don't guess: we also
# list what the project actually serves (list_served_gemini) before sweeping, so a
# model id we didn't think to name still surfaces. Keep this list newest→oldest.
PRO_CANDIDATES = [
    "gemini-3.1-pro", "gemini-3.1-pro-preview",
    "gemini-3-pro", "gemini-3-pro-preview",
    "gemini-pro-latest",
    "gemini-2.5-pro",
]
FLASH_CANDIDATES = [
    "gemini-3.5-flash-preview", "gemini-3.5-flash",
    "gemini-3-flash-preview", "gemini-3-flash",
    "gemini-flash-latest",
    "gemini-2.5-flash",
]


def list_served_gemini(project: str) -> list[str]:
    """List the Gemini model ids this project + region actually serves.

    This is the DISCOVER step the user asked for — don't guess from a candidate
    list alone; ask Vertex what it serves. Prints every gemini* id (publishers/
    google/models/* and bare ids), so a newer model we didn't name still shows up.
    Returns the bare ids (best-effort) for convenience.
    """
    try:
        from google import genai
    except Exception as e:  # noqa: BLE001
        print(f"  {FAIL} could not import google-genai: {e}")
        return []
    client = genai.Client(vertexai=True, project=project, location=config.GEMINI_LOCATION)
    ids: list[str] = []
    try:
        for m in client.models.list():
            name = getattr(m, "name", "") or ""
            bare = name.rsplit("/", 1)[-1]
            if "gemini" in name.lower() or "gemini" in bare.lower():
                ids.append(bare)
    except Exception as e:  # noqa: BLE001
        print(f"  {FAIL} models.list() failed: {type(e).__name__}: {str(e)[:160]}")
        return []
    # De-dup, keep first-seen order, print.
    seen: set[str] = set()
    uniq = [x for x in ids if not (x in seen or seen.add(x))]
    if uniq:
        print(f"  {OK} project serves {len(uniq)} Gemini ids @ {config.GEMINI_LOCATION}:")
        for x in uniq:
            print(f"      {INFO} {x}")
    else:
        print(f"  {INFO} models.list() returned no gemini ids (some Vertex projects don't list; the sweep below still proves what answers).")
    return uniq


def _try_gemini(project: str, model: str) -> tuple[bool, str]:
    from google import genai

    client = genai.Client(vertexai=True, project=project, location=config.GEMINI_LOCATION)
    resp = client.models.generate_content(model=model, contents="Reply with the single word: OK")
    return True, (resp.text or "").strip()


def _sweep(project: str, candidates: list[str], label: str) -> str | None:
    best: str | None = None
    for model in candidates:
        try:
            _, text = _try_gemini(project, model)
            print(f"  {OK} {label}  {model} @ {config.GEMINI_LOCATION} → {text[:30]!r}")
            if best is None:
                best = model
        except Exception as e:  # noqa: BLE001
            print(f"  {FAIL} {label}  {model} @ {config.GEMINI_LOCATION}: {type(e).__name__}: {str(e)[:120]}")
    return best


def probe_gemini(project: str) -> bool:
    """Sweep Gemini Pro + Flash candidates NEWEST-FIRST; report the newest each that
    answers. The candidate lists are newest→oldest and `_sweep` keeps the FIRST that
    answers, so `best` is the newest available — the configured id is only appended
    as a final fallback so it's still exercised, never preferred over a newer one."""
    pro_order = PRO_CANDIDATES + ([config.MODEL_CHAIR] if config.MODEL_CHAIR not in PRO_CANDIDATES else [])
    flash_order = FLASH_CANDIDATES + ([config.MODEL_MANTRI] if config.MODEL_MANTRI not in FLASH_CANDIDATES else [])
    best_pro = _sweep(project, pro_order, "Pro  ")
    print()
    best_flash = _sweep(project, flash_order, "Flash")
    if best_pro and best_flash:
        if best_pro != config.MODEL_CHAIR or best_flash != config.MODEL_MANTRI:
            print(f"\n  → best available — set in .env (arivu/.env + saakshe/.env):")
            print(f"      ARIVU_MODEL_CHAIR={best_pro}   SAAKSHE_MODEL_PRO={best_pro}")
            print(f"      ARIVU_MODEL_MANTRI={best_flash}   SAAKSHE_MODEL_FLASH={best_flash}")
        return True
    return False


def _try_claude(project: str, model: str, region: str) -> tuple[bool, str]:
    from anthropic import AnthropicVertex

    client = AnthropicVertex(project_id=project, region=region)
    msg = client.messages.create(
        model=model,
        max_tokens=64,
        messages=[{"role": "user", "content": "Reply with the single word: OK"}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    return True, text


def probe_claude(project: str) -> bool:
    """Try the configured Claude id/region, then sweep fallbacks to discover what
    Model Garden actually serves for this project."""
    candidates = [
        (config.MODEL_VERDICT, config.CLAUDE_LOCATION),
        # Sonnet 4.6 enabled in Model Garden; the GLOBAL quota was raised, and 4.6
        # supports the global endpoint — try global first, then us-east5. Both the
        # "@default" alias and the bare form, since the SDK can be picky about "@".
        ("claude-sonnet-4-6@default", "global"),
        ("claude-sonnet-4-6", "global"),
        ("claude-sonnet-4-6@default", "us-east5"),
        ("claude-sonnet-4-6", "us-east5"),
        # broader fallbacks, in case a different Anthropic model is what's enabled.
        ("claude-sonnet-4-5@20250929", "us-east5"),
        ("claude-opus-4-5@20251101", "us-east5"),
    ]
    seen = set()
    first_ok: tuple[str, str] | None = None
    for model, region in candidates:
        if (model, region) in seen:
            continue
        seen.add((model, region))
        try:
            _, text = _try_claude(project, model, region)
            print(f"  {OK} Claude  {model} @ {region} → {text[:40]!r}")
            if first_ok is None:
                first_ok = (model, region)
        except Exception as e:  # noqa: BLE001
            print(f"  {FAIL} Claude  {model} @ {region}: {type(e).__name__}: {str(e)[:160]}")
    if first_ok:
        m, r = first_ok
        if (m, r) != (config.MODEL_VERDICT, config.CLAUDE_LOCATION):
            print(f"\n  → set these in .env:")
            print(f"      ARIVU_MODEL_VERDICT={m}")
            print(f"      ARIVU_MODEL_PROSECUTOR={m}")
            print(f"      ARIVU_CLAUDE_LOCATION={r}")
        return True
    print("\n  → No Claude model answered. In Google Cloud console → Vertex AI → Model Garden,")
    print("    enable an Anthropic model (Opus/Sonnet) for this project, then re-run.")
    return False


def main() -> int:
    project = _project()
    print(f"\n◈ arivu Vertex probe — project={project or '(unset)'}  "
          f"gemini_region={config.GEMINI_LOCATION}  claude_region={config.CLAUDE_LOCATION}\n")
    if not project:
        print(f"  {FAIL} GOOGLE_CLOUD_PROJECT is not set. Export it (and run "
              f"`gcloud auth application-default login`) first.")
        return 2
    print("◈ discover — what Gemini ids does this project actually serve?\n")
    list_served_gemini(project)
    print()
    g = probe_gemini(project)
    print()
    c = probe_claude(project)
    print()
    if g and c:
        print(f"{OK} Both families answer. Set ARIVU_MODE=live and run: python run_demo.py --approve")
        return 0
    print(f"{INFO} Fix the failing family above, then re-run. arivu still runs in demo mode meanwhile.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
