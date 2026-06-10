"""kalai — the media crew's deterministic brain: router + pricer + receipt.

The router is honest v1: a rule with a recorded rationale (an LLM seat can
replace ``route()`` later without changing the quote/receipt contract).
All media prices live HERE and nowhere else.

Paths: A = generate (Vertex pixels), B = compute (deterministic FX + HDR),
A->B = generate a still then compute motion + HDR on it. HDR is always a
compute capability — no generative model outputs HDR today, which is exactly
why the router exists.
"""
from __future__ import annotations

IMAGEN_USD = 0.04                      # vertex imagen-4.0 still, published price
VEO_USD_PER_SEC = 0.40                 # vertex veo, low tier, per output second
CPU_USD_PER_VCPU_SEC = 0.000024        # cloud run tier-1 vCPU-second
RENDER_VCPU_SEC_PER_OUTPUT_SEC = 11.0  # measured locally 2026-06-10 (1080x1920@24)
MAX_SECONDS = 8


def route(*, has_source_image: bool, wants_hdr: bool) -> tuple[str, str]:
    """Pick the path; return (path, rationale). The agentic decision, recorded."""
    if has_source_image:
        return "B", ("source image exists and HDR is a compute capability — "
                     "no generation needed, deterministic FX+HDR path")
    return "A->B", ("no source image — generate a still (Imagen), then the "
                    "compute path adds motion + HDR (Veo cannot output HDR)")


def _lines(path: str, seconds: int) -> list[dict]:
    lines = []
    if path.startswith("A"):
        lines.append({"item": "imagen_still", "usd": IMAGEN_USD})
    cpu_sec = seconds * RENDER_VCPU_SEC_PER_OUTPUT_SEC
    lines.append({"item": "render_cpu", "vcpu_sec": cpu_sec,
                  "usd": cpu_sec * CPU_USD_PER_VCPU_SEC})
    return lines


def quote(*, seconds: int, budget_usd: float, has_source_image: bool,
          wants_hdr: bool) -> dict:
    seconds = max(1, min(MAX_SECONDS, int(seconds)))
    path, rationale = route(has_source_image=has_source_image, wants_hdr=wants_hdr)
    lines = _lines(path, seconds)
    total = round(sum(l["usd"] for l in lines), 6)
    out = {"path": path, "seconds": seconds, "lines": lines, "total_usd": total,
           "budget_usd": budget_usd, "fits_budget": total <= budget_usd,
           "rationale": rationale,
           "est_wall_sec": int(seconds * RENDER_VCPU_SEC_PER_OUTPUT_SEC / 2) + 12}
    if not out["fits_budget"]:
        out["counter_offer"] = None
        for s in range(seconds, 0, -1):
            t = sum(l["usd"] for l in _lines(path, s))
            if t <= budget_usd:
                out["counter_offer"] = {"seconds": s, "total_usd": round(t, 6)}
                break
    return out


def receipt(quote_: dict, *, measured_vcpu_sec: float, vertex_usd: float) -> dict:
    """The honest invoice: estimate vs measured, line by line."""
    cpu_usd = round(measured_vcpu_sec * CPU_USD_PER_VCPU_SEC, 6)
    return {"estimated_usd": quote_["total_usd"], "vertex_usd": round(vertex_usd, 6),
            "measured_vcpu_sec": round(measured_vcpu_sec, 1), "cpu_usd": cpu_usd,
            "total_usd": round(vertex_usd + cpu_usd, 6), "path": quote_["path"],
            "seconds": quote_["seconds"]}
