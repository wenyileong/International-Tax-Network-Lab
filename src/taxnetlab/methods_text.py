"""Methods appendix (plan F8): one stored run described in prose, with citations, as Markdown, HTML or Word.

Everything is written from the immutable run record and its stored outputs, so the appendix states exactly what
was run. The software and every data source are cited in OSCOLA form. The Word file is Office Open XML written
with the standard library (headings, paragraphs, lists and tables only), so no dependency is added.
"""

from __future__ import annotations

import html
import io
import json
import zipfile
from typing import Any
from xml.sax.saxutils import escape

from taxnetlab.buildinfo import software_citation

PREVIEW_ROWS = 40
VERIFIED = {"verified", "replicated", "replicated_with_discrepancies", "robust", "empirically_tested"}


def _value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False, sort_keys=True)
    if v is None:
        return ""
    return str(v)


def _source_citation(s: dict[str, Any]) -> str:
    if s.get("oscola_citation"):
        return s["oscola_citation"]
    parts = [s.get("custodian") or "", f"'{s['title']}'"]
    text = ", ".join(p for p in parts if p)
    if s.get("url"):
        text += f" <{s['url']}>"
    if s.get("retrieval_date"):
        text += f" accessed {_oscola_date(s['retrieval_date'])}"
    return text


def _oscola_date(iso: str) -> str:
    import datetime as dt

    try:
        d = dt.date.fromisoformat(str(iso))
    except ValueError:
        return str(iso)
    return f"{d.day} {d.strftime('%B')} {d.year}"


def appendix(record: dict[str, Any], outputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The appendix as blocks: ("h1"|"h2"|"p", text), ("list", [items]), ("table", columns, rows)."""
    eng, ds = record["engine"], record["dataset"]
    blocks: list[tuple] = [("h1", f"Methods appendix: research run {record['run_id']}")]
    q = record.get("research_question")
    if q:
        blocks.append(("p", f"Research question: {q}"))
    blocks.append(("h2", "Method"))
    sentence = (f"The analysis applied {eng['display_name']} (engine {eng['engine_id']}, {eng['variant']} variant, "
                f"version {eng['version']}) as specified in {eng['spec_ref']}. The run finished with the outcome "
                f"'{record['outcome']}'.")
    blocks.append(("p", sentence))
    if eng["status"] not in VERIFIED:
        blocks.append(("p", f"The engine's status is '{eng['status']}': its specification has not yet been verified "
                            "against the source, so the results are not a citable reproduction of the published "
                            "method."))
    if eng.get("track") == "demonstration":
        blocks.append(("p", "This is a demonstration engine, not a research method."))
    if eng.get("boundary"):
        blocks.append(("p", f"Boundary of the method: {eng['boundary']}"))
    blocks.append(("h2", "Data"))
    status = {"synthetic": "synthetic (every jurisdiction, company, value and rate is fictional)",
              "real": "real", "mixed": "a mixture of synthetic and real data"}.get(ds["data_status"], ds["data_status"])
    blocks.append(("p", f"The data were the dataset '{ds['name']}' (identifier {ds['dataset_id']}), whose content "
                        f"hash is {ds['content_hash']}; the data are {status}."))
    sources = ds.get("sources") or []
    if sources:
        blocks.append(("table", ["source", "title", "licence class"],
                       [[s["source_id"], s["title"], s["licence_class"]] for s in sources]))
    blocks.append(("h2", "Parameters"))
    blocks.append(("p", "Every parameter, including those left at their defaults, was:"))
    blocks.append(("table", ["parameter", "value"], [[k, _value(v)] for k, v in sorted(record["parameters"].items())]))
    if record.get("assumptions"):
        blocks += [("h2", "Assumptions"), ("list", list(record["assumptions"]))]
    if record.get("warnings"):
        blocks += [("h2", "Warnings recorded by the run"), ("list", list(record["warnings"]))]
    blocks.append(("h2", "Results"))
    for name, info in record["outputs"].items():
        out = outputs.get(name, {"columns": [], "rows": []})
        rows = out["rows"]
        shown = f"; the first {PREVIEW_ROWS} are shown" if len(rows) > PREVIEW_ROWS else ""
        blocks.append(("p", f"Output '{name}': {len(rows)} rows, SHA-256 {info['sha256']}{shown}."))
        cols = list(out["columns"])
        if cols and rows:
            blocks.append(("table", cols, [[_value(r.get(c)) for c in cols] for r in rows[:PREVIEW_ROWS]]))
    env = record.get("environment") or {}
    blocks.append(("h2", "Reproduction"))
    blocks.append(("p", f"The run was made with International Tax Network Lab version "
                        f"{env.get('taxnetlab_version', '')} on {record['started_utc']} (UTC). It can be replayed with "
                        f"'taxnetlab replay {record['run_id']}' in a workspace holding dataset {ds['dataset_id']}; the "
                        "replay re-executes the engine and compares every output hash. The run record's hash is "
                        f"{record.get('record_sha256')}."))
    blocks.append(("h2", "References"))
    refs = [software_citation()] + [_source_citation(s) for s in sources]
    blocks.append(("list", refs))
    return {"title": blocks[0][1], "blocks": blocks}


# ------------------------------------------------------------------ Markdown
def _md_cell(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def to_markdown(doc: dict[str, Any]) -> str:
    out = []
    for b in doc["blocks"]:
        if b[0] == "h1":
            out.append(f"# {b[1]}\n")
        elif b[0] == "h2":
            out.append(f"## {b[1]}\n")
        elif b[0] == "p":
            out.append(f"{b[1]}\n")
        elif b[0] == "list":
            out.append("\n".join(f"* {x}" for x in b[1]) + "\n")
        elif b[0] == "table":
            cols, rows = b[1], b[2]
            out.append("| " + " | ".join(_md_cell(c) for c in cols) + " |")
            out.append("|" + "---|" * len(cols))
            out.append("\n".join("| " + " | ".join(_md_cell(c) for c in r) + " |" for r in rows) + "\n")
    return "\n".join(out)


# ------------------------------------------------------------------ HTML (static: no script, no external resource)
CSS = ("body{font-family:Georgia,'Times New Roman',serif;max-width:900px;margin:32px auto;padding:0 20px;line-height:1.5}"
       "table{border-collapse:collapse;font-size:12.5px;margin:8px 0}th,td{border:1px solid #bbb;padding:3px 6px;"
       "text-align:left;vertical-align:top}th{background:#f3f3f3}")


def to_html(doc: dict[str, Any]) -> str:
    e = html.escape
    parts = [f"<!doctype html><html lang='en-GB'><head><meta charset='utf-8'><title>{e(doc['title'])}</title>"
             f"<style>{CSS}</style></head><body>"]
    for b in doc["blocks"]:
        if b[0] in ("h1", "h2"):
            parts.append(f"<{b[0]}>{e(b[1])}</{b[0]}>")
        elif b[0] == "p":
            parts.append(f"<p>{e(b[1])}</p>")
        elif b[0] == "list":
            parts.append("<ul>" + "".join(f"<li>{e(x)}</li>" for x in b[1]) + "</ul>")
        elif b[0] == "table":
            head = "".join(f"<th>{e(str(c))}</th>" for c in b[1])
            body = "".join("<tr>" + "".join(f"<td>{e(str(c))}</td>" for c in r) + "</tr>" for r in b[2])
            parts.append(f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")
    parts.append("</body></html>")
    return "\n".join(parts)


# ------------------------------------------------------------------ Word (Office Open XML)
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CONTENT_TYPES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                 '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                 '<Default Extension="xml" ContentType="application/xml"/>'
                 '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.'
                 'wordprocessingml.document.main+xml"/>'
                 '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.'
                 'wordprocessingml.styles+xml"/></Types>')
RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        'officeDocument" Target="word/document.xml"/></Relationships>')
DOC_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
            'Target="styles.xml"/></Relationships>')


def _style(sid: str, name: str, size: int, bold: bool = False, kind: str = "paragraph", extra: str = "") -> str:
    b = "<w:b/>" if bold else ""
    return (f'<w:style w:type="{kind}" w:styleId="{sid}"><w:name w:val="{name}"/>'
            f'{extra}<w:rPr>{b}<w:sz w:val="{size}"/></w:rPr></w:style>')


STYLES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          f'<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Times New Roman" '
          'w:hAnsi="Times New Roman" w:eastAsia="SimSun" w:cs="Times New Roman"/><w:sz w:val="24"/><w:lang w:val="en-GB"/>'
          '</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr>'
          '</w:pPrDefault></w:docDefaults>'
          + _style("Normal", "Normal", 24)
          + _style("Title", "Title", 32, True, extra='<w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="240"/></w:pPr>')
          + _style("Heading1", "heading 1", 28, True, extra='<w:basedOn w:val="Normal"/><w:pPr><w:keepNext/>'
                   '<w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr>')
          + _style("TableText", "Table Text", 18, extra='<w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="0"/></w:pPr>')
          + '<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:tblPr><w:tblBorders>'
          + "".join(f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
                    for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
          + '</w:tblBorders></w:tblPr></w:style></w:styles>')


def _para(text: str, style: str | None = None, bold: bool = False, bullet: bool = False) -> str:
    ppr = f'<w:pStyle w:val="{style}"/>' if style else ""
    if bullet:
        ppr += '<w:ind w:left="360" w:hanging="360"/>'
        text = "\u2022\t" + text
    rpr = "<w:rPr><w:b/></w:rPr>" if bold else ""
    runs = "".join(f'<w:r>{rpr}<w:t xml:space="preserve">{escape(part)}</w:t></w:r>' + ("<w:r><w:tab/></w:r>" if i < len(
        text.split("\t")) - 1 else "") for i, part in enumerate(text.split("\t")))
    return f"<w:p><w:pPr>{ppr}</w:pPr>{runs}</w:p>"


def _table(cols: list[Any], rows: list[list[Any]]) -> str:
    def cell(text: Any, header: bool) -> str:
        return f'<w:tc><w:tcPr><w:tcW w:w="0" w:type="auto"/></w:tcPr>{_para(str(text), "TableText", header)}</w:tc>'

    head = "<w:tr><w:trPr><w:tblHeader/></w:trPr>" + "".join(cell(c, True) for c in cols) + "</w:tr>"
    body = "".join("<w:tr>" + "".join(cell(c, False) for c in r) + "</w:tr>" for r in rows)
    return ('<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="5000" w:type="pct"/></w:tblPr>'
            f'<w:tblGrid>{"<w:gridCol/>" * len(cols)}</w:tblGrid>{head}{body}</w:tbl>' + _para(""))


def to_docx(doc: dict[str, Any]) -> bytes:
    body = []
    for b in doc["blocks"]:
        if b[0] == "h1":
            body.append(_para(b[1], "Title"))
        elif b[0] == "h2":
            body.append(_para(b[1], "Heading1"))
        elif b[0] == "p":
            body.append(_para(b[1]))
        elif b[0] == "list":
            body.extend(_para(x, bullet=True) for x in b[1])
        elif b[0] == "table":
            body.append(_table(b[1], b[2]))
    document = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{W}"><w:body>'
                + "".join(body)
                + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" '
                  'w:left="1440" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr></w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in (("[Content_Types].xml", CONTENT_TYPES), ("_rels/.rels", RELS),
                           ("word/_rels/document.xml.rels", DOC_RELS), ("word/styles.xml", STYLES),
                           ("word/document.xml", document)):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, text.encode("utf-8"))
    return buf.getvalue()
