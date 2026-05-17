"""
PDF incident report generator.
Takes the full pipeline result and renders a professional HTML -> PDF report.
"""
import logging
from datetime import datetime, timezone

from weasyprint import HTML

logger = logging.getLogger(__name__)

_SEVERITY_COLORS = {
    "critical": "#e74c3c",
    "high":     "#e67e22",
    "medium":   "#f39c12",
    "low":      "#27ae60",
}

_SEVERITY_BG = {
    "critical": "#fdf0ef",
    "high":     "#fef5ec",
    "medium":   "#fefaec",
    "low":      "#edfaf3",
}


def _sev_color(sev: str) -> str:
    return _SEVERITY_COLORS.get(sev.lower(), "#7f8c8d")


def _sev_bg(sev: str) -> str:
    return _SEVERITY_BG.get(sev.lower(), "#f4f4f4")


def _e(text) -> str:
    if not text:
        return ""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def _list_html(items: list) -> str:
    if not items:
        return "<p style='color:#888;margin:0;'>None</p>"
    rows = "".join(f"<li>{_e(str(i))}</li>" for i in items)
    return f"<ul style='margin:4px 0;padding-left:20px;'>{rows}</ul>"


def _code_html(text: str) -> str:
    if not text:
        return "<p style='color:#888;margin:0;'>&#x2014;</p>"
    return (
        "<pre style='background:#1e1e2e;color:#cdd6f4;padding:14px;"
        "border-radius:6px;font-size:11px;white-space:pre-wrap;"
        f"overflow-wrap:break-word;margin:0;'>{_e(text)}</pre>"
    )


def _card(label: str, body: str, highlight: bool = False, extra_style: str = "") -> str:
    cls = "card highlight" if highlight else "card"
    return (
        f"<div class='{cls}' style='{extra_style}'>"
        f"<div class='card-label'>{label}</div>"
        f"<div class='card-value'>{body}</div>"
        "</div>"
    )


def _subsection(title: str, body: str) -> str:
    return (
        "<div class='subsection'>"
        f"<div class='subsection-title'>{title}</div>"
        f"{body}"
        "</div>"
    )


def _log_evidence_html(evidence: list, sev_color: str) -> str:
    if not evidence:
        return ""
    parts = []
    for hit in evidence:
        log_path = _e(hit.get("log_path") or hit.get("file", ""))
        line_no  = hit.get("line", "")
        matched  = _e(hit.get("matched_line", ""))
        context  = hit.get("context", "")
        loc = f"{log_path}" + (f" &mdash; line {line_no}" if line_no else "")
        ctx_html = _code_html(context) if context else ""
        parts.append(
            f"<div style='margin-bottom:10px;border-left:3px solid {sev_color};padding-left:12px;'>"
            f"<div style='font-family:monospace;font-size:11px;color:#718096;margin-bottom:4px;'>{loc}</div>"
            f"<div style='font-family:monospace;font-size:12px;background:#f8f9fa;"
            f"border:1px solid #e2e8f0;border-radius:4px;padding:6px 10px;"
            f"color:#c0392b;font-weight:600;'>{matched}</div>"
            f"{ctx_html}"
            "</div>"
        )
    return "".join(parts)


def _affected_code_html(aff_code: list, sev_color: str) -> str:
    if not aff_code:
        return ""
    parts = []
    for ac in aff_code:
        file_loc = _e(ac.get("file", ""))
        line_no  = ac.get("line", "")
        snippet  = ac.get("snippet", "")
        issue    = _e(ac.get("issue", ""))
        parts.append(
            f"<div style='margin-bottom:12px;border-left:3px solid {sev_color};padding-left:12px;'>"
            f"<div style='font-family:monospace;font-size:12px;color:#555;margin-bottom:4px;'>"
            f"{file_loc}:{line_no}</div>"
            f"{_code_html(snippet)}"
            f"<div style='color:#c0392b;font-size:12px;margin-top:6px;'>&#x26A0; {issue}</div>"
            "</div>"
        )
    return "".join(parts)


def _health_badge(status: str) -> str:
    color = {"up": "#27ae60", "down": "#e74c3c", "degraded": "#e67e22"}.get(
        status.lower(), "#7f8c8d"
    )
    return (
        f"<span style='display:inline-block;padding:2px 10px;border-radius:12px;"
        f"background:{color};color:white;font-size:11px;font-weight:700;"
        f"text-transform:uppercase;'>{_e(status)}</span>"
    )


def _build_html(result: dict) -> str:
    triage    = result.get("triage", {})
    invest    = result.get("investigation", {})
    code      = result.get("code_analysis", {})
    pid       = result.get("pipeline_id", "&#x2014;")
    started   = result.get("started_at", "")
    completed = result.get("completed_at", "")

    # ── Triage fields ─────────────────────────────────────────────────────────
    severity  = (triage.get("severity") or "unknown").lower()
    svc       = _e(triage.get("service_name") or triage.get("service") or "unknown")
    err_type  = _e(triage.get("error_type") or "")
    alert     = _e(triage.get("error_summary") or triage.get("error_message") or "")
    key_inds  = triage.get("key_indicators") or []
    actions   = triage.get("actions_taken") or []
    rec_inv   = _e(triage.get("recommended_investigation") or "")
    triage_raw = triage.get("raw_output", "")

    # ── Investigation fields ──────────────────────────────────────────────────
    svc_health    = invest.get("service_health") or {}
    health_status = (svc_health.get("status") or "").strip()
    health_detail = _e(svc_health.get("details") or "")
    log_evidence  = (invest.get("log_evidence") or
                     invest.get("error_log_evidence") or
                     invest.get("api_log_evidence") or [])
    hypothesis    = _e(invest.get("root_cause_hypothesis") or invest.get("hypothesis") or "&#x2014;")
    confidence    = _e(invest.get("confidence") or "&#x2014;")
    inference     = _e(invest.get("inference") or invest.get("analysis") or "&#x2014;")
    stack         = invest.get("stack_trace") or ""
    aff_comps     = invest.get("affected_components") or invest.get("affected_endpoints") or []
    suggested     = invest.get("suggested_files_to_check") or []
    invest_raw    = invest.get("raw_output", "")

    # ── Code analysis fields ──────────────────────────────────────────────────
    root_cause = _e(code.get("root_cause") or "&#x2014;")
    fix        = _e(code.get("fix_suggestion") or code.get("fix") or "&#x2014;")
    depth      = _e(code.get("analysis_depth") or "&#x2014;")
    complexity = _e(code.get("complexity_assessment") or "&#x2014;")
    next_steps = code.get("recommended_next_steps") or code.get("next_steps") or []
    alt_sol    = code.get("alternative_solutions") or []
    aff_code   = code.get("affected_code") or []
    code_raw   = code.get("raw_output", "")

    sc = _sev_color(severity)
    sb = _sev_bg(severity)

    # ── Pre-build complex fragments ───────────────────────────────────────────
    summary_bar = ""
    if alert:
        focus = f"<br/><strong>Recommended focus:</strong> {rec_inv}" if rec_inv else ""
        summary_bar = (
            f"<div class='summary-bar'><strong>Summary:</strong> {alert}{focus}</div>"
        )

    # Section 1 — triage
    triage_body = (
        "<div class='two-col'>"
        + _card("Key Indicators", _list_html(key_inds) if key_inds else "<p style='color:#888;margin:0;'>&#x2014;</p>")
        + _card("Actions Taken", _list_html(actions) if actions else "<p style='color:#888;margin:0;'>&#x2014;</p>")
        + "</div>"
        + (_card("Raw Agent Output", _code_html(triage_raw)) if triage_raw and not alert else "")
    )

    # Section 2 — investigation: health + hypothesis + confidence row
    health_cell = ""
    if health_status:
        detail_span = (
            f"<br/><span style='font-size:12px;color:#555;margin-top:4px;display:block;'>{health_detail}</span>"
            if health_detail else ""
        )
        health_cell = _card("Service Health", _health_badge(health_status) + detail_span)

    hyp_conf_row = (
        "<div class='two-col'>"
        + _card("Root Cause Hypothesis", hypothesis)
        + _card("Confidence", f"<span class='confidence-{confidence.lower()}'>{confidence.upper()}</span>")
        + "</div>"
    )

    invest_body = (
        (("<div class='three-col'>" + health_cell + _card("Root Cause Hypothesis", hypothesis)
          + _card("Confidence", f"<span class='confidence-{confidence.lower()}'>{confidence.upper()}</span>")
          + "</div>") if health_status else hyp_conf_row)
        + _card("Inference", inference)
        + (_card("Affected Components", _list_html(aff_comps)) if aff_comps else "")
        + (_subsection("Log Evidence", _log_evidence_html(log_evidence, sc)) if log_evidence else "")
        + (_subsection("Stack Trace", _code_html(stack)) if stack else "")
        + (_card("Suggested Files to Check", _list_html(suggested)) if suggested else "")
        + (_card("Raw Agent Output", _code_html(invest_raw))
           if invest_raw and hypothesis in ("&#x2014;", "—", "") else "")
    )

    # Section 3 — code analysis
    code_body = (
        _card("Root Cause", root_cause, highlight=True)
        + (_subsection("Affected Code", _affected_code_html(aff_code, sc)) if aff_code else "")
        + "<div class='fix-box'>"
        + "<div class='fix-label'>&#x25B6; Fix Suggestion</div>"
        + f"<div class='card-value'>{fix}</div>"
        + "</div>"
        + (_card("Alternative Solutions", _list_html(alt_sol), extra_style="margin-top:10px;") if alt_sol else "")
        + _card("Recommended Next Steps", _list_html(next_steps), extra_style="margin-top:10px;")
        + (_card("Raw Agent Output", _code_html(code_raw), extra_style="margin-top:10px;")
           if code_raw and root_cause in ("&#x2014;", "—", "") else "")
    )

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: Helvetica, Arial, sans-serif; color: #1a1a2e; background: #fff; font-size: 13px; }}

  .header {{ background: #1a1a2e; color: white; padding: 32px 40px 24px; }}
  .header-top {{ display: flex; justify-content: space-between; align-items: flex-start; }}
  .header h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 4px; }}
  .header .sub {{ font-size: 13px; color: #a0aec0; }}
  .badge {{ display: inline-block; padding: 4px 14px; border-radius: 20px; font-size: 12px;
             font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase;
             background: {sc}; color: white; }}

  .meta-bar {{ background: #f8f9fa; border-bottom: 1px solid #e2e8f0; padding: 12px 40px;
               display: flex; gap: 40px; flex-wrap: wrap; }}
  .meta-item {{ font-size: 12px; }}
  .meta-item .label {{ color: #718096; margin-bottom: 2px; }}
  .meta-item .value {{ font-weight: 600; color: #1a1a2e; }}

  .summary-bar {{ background: {sb}; border-left: 4px solid {sc};
                  padding: 14px 40px; font-size: 13px; color: #1a1a2e; line-height: 1.6; }}
  .summary-bar strong {{ color: {sc}; }}

  .content {{ padding: 28px 40px; }}
  .section {{ margin-bottom: 32px; }}
  .section-header {{ display: flex; align-items: center; gap: 10px;
                     border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; margin-bottom: 14px; }}
  .section-header h2 {{ font-size: 15px; font-weight: 700; color: #1a1a2e; }}
  .section-num {{ width: 24px; height: 24px; border-radius: 50%; background: {sc};
                  color: white; font-size: 12px; font-weight: 700; flex-shrink: 0;
                  display: flex; align-items: center; justify-content: center; }}

  .subsection {{ margin-top: 14px; margin-bottom: 8px; }}
  .subsection-title {{ font-size: 11px; font-weight: 700; text-transform: uppercase;
                        letter-spacing: 0.6px; color: #718096; margin-bottom: 8px;
                        padding-bottom: 4px; border-bottom: 1px dashed #e2e8f0; }}

  .card {{ background: #f8f9fa; border: 1px solid #e2e8f0; border-radius: 8px;
            padding: 14px 16px; margin-bottom: 10px; }}
  .card.highlight {{ background: {sb}; border-color: {sc}; }}
  .card-label {{ font-size: 11px; color: #718096; text-transform: uppercase;
                  letter-spacing: 0.5px; margin-bottom: 4px; }}
  .card-value {{ font-size: 13px; color: #1a1a2e; line-height: 1.5; }}

  .two-col {{ display: flex; gap: 12px; }}
  .two-col .card {{ flex: 1; }}
  .three-col {{ display: flex; gap: 12px; }}
  .three-col .card {{ flex: 1; }}

  .confidence-high   {{ color: #27ae60; font-weight: 700; }}
  .confidence-medium {{ color: #e67e22; font-weight: 700; }}
  .confidence-low    {{ color: #e74c3c; font-weight: 700; }}

  .fix-box {{ background: #edfaf3; border: 1px solid #27ae60; border-radius: 8px;
               padding: 14px 16px; margin-top: 10px; }}
  .fix-box .fix-label {{ color: #1e8449; font-size: 11px; font-weight: 700;
                          text-transform: uppercase; margin-bottom: 6px; }}

  .footer {{ margin-top: 32px; padding: 16px 40px; background: #f8f9fa;
              border-top: 1px solid #e2e8f0; text-align: center;
              font-size: 11px; color: #a0aec0; }}
</style>
</head>
<body>

<div class="header">
  <div class="header-top">
    <div>
      <h1>Incident Report</h1>
      <div class="sub">Pipeline ID: {pid}</div>
    </div>
    <div class="badge">{severity}</div>
  </div>
</div>

<div class="meta-bar">
  <div class="meta-item"><div class="label">Service</div><div class="value">{svc}</div></div>
  <div class="meta-item"><div class="label">Error Type</div><div class="value">{err_type}</div></div>
  <div class="meta-item"><div class="label">Started</div><div class="value">{started}</div></div>
  <div class="meta-item"><div class="label">Completed</div><div class="value">{completed}</div></div>
  <div class="meta-item"><div class="label">Analysis</div><div class="value">{depth} / {complexity}</div></div>
</div>

{summary_bar}

<div class="content">

  <div class="section">
    <div class="section-header">
      <div class="section-num">1</div>
      <h2>Triage</h2>
    </div>
    {triage_body}
  </div>

  <div class="section">
    <div class="section-header">
      <div class="section-num">2</div>
      <h2>Investigation</h2>
    </div>
    {invest_body}
  </div>

  <div class="section">
    <div class="section-header">
      <div class="section-num">3</div>
      <h2>Code Analysis</h2>
    </div>
    {code_body}
  </div>

</div>

<div class="footer">
  Generated by Incident Response Agent &mdash; {generated}
</div>

</body>
</html>"""


def generate_pdf(pipeline_result: dict) -> bytes:
    """Render the pipeline result as a PDF and return the raw bytes."""
    html_content = _build_html(pipeline_result)
    pdf_bytes = HTML(string=html_content).write_pdf()
    logger.info(
        "PDF generated for pipeline_id=%s (%d bytes)",
        pipeline_result.get("pipeline_id"), len(pdf_bytes),
    )
    return pdf_bytes
