"""Empat guardrail sebagai fungsi murni (Architecture.md 6.4). Konstanta tetap, jangan diubah tanpa evaluasi."""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

HALF_LIFE_HOURS = {"tweet": 36.0, "news": 120.0}
SOURCE_WEIGHT = {"tweet": 0.7, "news": 1.0}
MAX_AGE_HOURS = {"tweet": 96.0, "news": 720.0}
MIN_SIMILARITY = 0.78  # e5 memberi skor rapat; kalibrasi dengan evaluasi
MIN_EVIDENCE_PER_TICKER = 2
MAX_QUESTION_CHARS = 500

INJECTION = re.compile(
    r"ignore (all |any )?(previous|prior)|system prompt|you are now|"
    r"disregard (the )?(above|previous)|developer message|abaikan instruksi",
    re.I,
)
EXECUTION = re.compile(
    r"\b(place|execute|submit|pasang|eksekusi|kirim)\b.{0,30}\b(order|trade|transaksi)\b|"
    r"\b(beli|jual|buy|sell)\b.{0,40}\b(sekarang|now|untuk saya|for me|otomatis|automatically)\b",
    re.I,
)
# Rail cakupan: pola janji, arahan, dan topik di luar skrip
PROMISE = re.compile(
    r"guarantee|assured|risk[- ]free|expected return|price target|"
    r"will (?:definitely |certainly )?(?:go up|rise|reach|hit|double|moon|crash)|"
    r"pasti|dijamin|tanpa risiko|target harga|"
    r"akan (?:naik|turun|mencapai|menembus|melonjak|anjlok)",
    re.I,
)
ADVICE = re.compile(
    r"you should (?:buy|sell|invest|put)|you must|"
    r"anda (?:harus|wajib|sebaiknya)|sebaiknya anda|kamu (?:harus|sebaiknya)|"
    r"\ball[- ]in\b|leverage|margin|futures|derivatif|borrow|pinjam(?:an)?\b|"
    r"invest(?:ing)? your savings|tabungan anda|go (?:long|short)|"
    r"beli sekarang|jual sekarang|buy now|sell now",
    re.I,
)
OFF_SCRIPT = re.compile(
    r"tax (?:advice|treatment)|legal advice|pajak|hukum|"
    r"as your (?:financial )?advisor|sebagai penasihat keuangan",
    re.I,
)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
CARD = re.compile(r"\b\d{13,19}\b")
NUMBER = re.compile(r"[-+]?\d+(?:[.,]\d+)*")


def input_rail(question: str) -> tuple[str, str | None]:
    """Return (clean_question, block_reason). block_reason is None when allowed."""
    q = EMAIL.sub("[email]", CARD.sub("[number]", question.strip()))
    if len(q) > MAX_QUESTION_CHARS:
        return q, "too_long"
    if INJECTION.search(q):
        return q, "injection"
    if EXECUTION.search(q):
        return q, "execution_request"
    return q, None


def age_hours(published_ts: float, now: datetime) -> float:
    published = datetime.fromtimestamp(published_ts, tz=timezone.utc)
    return max((now - published).total_seconds() / 3600.0, 0.0)


@dataclass
class RailResult:
    kept: list = field(default_factory=list)
    dropped: list = field(default_factory=list)
    insufficient_tickers: list = field(default_factory=list)

    @property
    def sufficient(self) -> bool:
        return not self.insufficient_tickers


def retrieval_rail(matches: list[dict], tickers: list[str], now: datetime) -> RailResult:
    """matches: dicts with id, score, metadata (incl. text, ticker, source_type, published_at_ts)."""
    result = RailResult()
    for m in matches:
        md = m["metadata"]
        a = age_hours(md["published_at_ts"], now)
        if m["score"] < MIN_SIMILARITY:
            reason = "low_similarity"
        elif md["ticker"] not in tickers:
            reason = "ticker_mismatch"
        elif a > MAX_AGE_HOURS[md["source_type"]]:
            reason = "too_old"
        elif INJECTION.search(md.get("text", "")):
            reason = "injection_in_evidence"
        else:
            result.kept.append({**m, "age_hours": a})
            continue
        result.dropped.append({"id": m["id"], "reason": reason})
    for t in tickers:
        if sum(1 for k in result.kept if k["metadata"]["ticker"] == t) < MIN_EVIDENCE_PER_TICKER:
            result.insufficient_tickers.append(t)
    return result


def rerank(kept: list[dict], top_n: int = 8) -> list[dict]:
    for k in kept:
        st = k["metadata"]["source_type"]
        decay = 0.5 ** (k["age_hours"] / HALF_LIFE_HOURS[st])
        k["score_final"] = k["score"] * decay * SOURCE_WEIGHT[st]
    kept.sort(key=lambda k: k["score_final"], reverse=True)
    seen, top = set(), []
    for k in kept:
        h = k["metadata"]["chunk_hash"]
        if h in seen:
            continue
        seen.add(h)
        top.append(k)
        if len(top) == top_n:
            break
    top.sort(key=lambda k: k["metadata"]["published_at_ts"])
    return top


def _to_float(tok: str) -> float | None:
    t = tok.lstrip("+")
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def numbers_in(text: str) -> list[float]:
    return [v for v in (_to_float(t) for t in NUMBER.findall(text)) if v is not None]


def ungrounded_numbers(answer_text: str, context_text: str, rel_tol: float = 0.005) -> list[float]:
    allowed = numbers_in(context_text)
    bad = []
    for x in numbers_in(answer_text):
        if not any(abs(x - y) <= max(0.01, rel_tol * abs(y)) for y in allowed):
            bad.append(x)
    return bad


def output_rail(rec, allowed_ids: set[str], context_text: str, assessment_requested: bool) -> list[str]:
    """rec is a Recommendation. Return a list of error strings, empty when valid."""
    errors: list[str] = []
    if rec.assessment_requested != assessment_requested:
        errors.append("assessment_requested does not match the request")
    for p in rec.positions:
        unknown = [e for e in p.evidence_ids if e not in allowed_ids]
        if unknown:
            errors.append(f"{p.ticker}: unknown evidence ids {unknown}")
        if p.action in ("add", "reduce") and not p.evidence_ids:
            errors.append(f"{p.ticker}: action {p.action} requires evidence_ids")
        text = p.summary + " " + " ".join(p.risks)
        bad = ungrounded_numbers(text, context_text)
        if bad:
            errors.append(f"{p.ticker}: numbers not found in context {bad}")
    return errors


def scope_rail(rec, assessment_requested: bool) -> list[str]:
    """Return reasons that require handoff to a human. Empty when inside the approved script."""
    reasons: list[str] = []
    texts = [rec.portfolio_notes]
    for p in rec.positions:
        texts.append(p.summary)
        texts.extend(p.risks)
        if p.action is not None and not assessment_requested:
            reasons.append(f"{p.ticker}: unsolicited_assessment")
    blob = " ".join(texts)
    if PROMISE.search(blob):
        reasons.append("promise_or_prediction")
    if ADVICE.search(blob):
        reasons.append("directive_or_leveraged_advice")
    if OFF_SCRIPT.search(blob):
        reasons.append("outside_approved_scope")
    return reasons
