"""Bounded browser-declared formative reports shared by the two learner adapters."""

import json
import math

MAX_REPORT = 128 * 1024


def encode_report(value):
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError, RecursionError) as error:
        raise ValueError("Invalid JSON report") from error
    if len(encoded.encode()) > MAX_REPORT:
        raise ValueError("Report exceeds 128 KiB")
    return encoded


def validate_result(result, kind):
    if not isinstance(result, dict) or set(result) != {"score", "maximum", "completed"}:
        raise ValueError("Invalid formative result schema")
    score, maximum = result["score"], result["maximum"]
    if (
        type(score) not in (int, float)
        or type(maximum) not in (int, float)
        or not 0 <= score <= maximum <= 100000
        or not math.isfinite(score)
        or not math.isfinite(maximum)
        or type(result["completed"]) is not bool
        or kind not in ("h5p", "scorm12")
    ):
        raise ValueError("Invalid formative result")
    if kind == "h5p" and (score not in (0, 1) or maximum != 1):
        raise ValueError("TrueFalse requires a whole-content result out of one")
    return result
