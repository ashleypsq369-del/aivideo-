"""Generate a structured HTML report from a ScenePlan."""
import html
import os


def _esc(s):
    return html.escape(str(s))


FORMAT_LABELS = {
    "deep_dive": "Deep Dive",
    "brief":     "Brief Overview",
    "critique":  "Critique",
    "debate":    "Debate",
}

ICON_SVG = {
    "book":    "📚", "health": "🏥", "money": "💰", "science": "🔬",
    "code":    "💻", "globe":  "🌍", "people": "👥", "idea":    "💡",
    "warning": "⚠️", "check":  "✅",
}


def render_report(plan, path):
    fmt_label = FORMAT_LABELS.get(plan.format, plan.format.replace("_", " ").title())

    # build scene HTML
    scene_html = ""
    for i, scene in enumerate(plan.scenes):
        if scene.kind == "title":
            continue
        icon = ICON_SVG.get(scene.icon, "📄")
        kind_label = scene.kind.replace("_", " ").title()
        bullets_html = ""
        if scene.bullets:
            items = "".join(f"<li>{_esc(b)}</li>" for b in scene.bullets)
            bullets_html = f"<ul class='bullets'>{items}</ul>"
        quiz_html = ""
        if scene.kind == "quiz" and scene.question:
            opts = "".join(
                f"<li class='opt {'correct' if j == scene.answer_index else ''}'>"
                f"{'ABCD'[j]}. {_esc(o)}</li>"
                for j, o in enumerate(scene.options)
            )
            quiz_html = f"<div class='quiz'><p class='q'>{_esc(scene.question)}</p><ul>{opts}</ul></div>"
        fc_html = ""
        if scene.kind == "flashcard" and scene.flashcards:
            cards = "".join(
                f"<div class='fc'><div class='fc-front'>{_esc(c['front'])}</div>"
                f"<div class='fc-back'>{_esc(c['back'])}</div></div>"
                for c in scene.flashcards
            )
            fc_html = f"<div class='flashcards'>{cards}</div>"
        dialogue_html = ""
        if scene.dialogue:
            lines = "".join(
                f"<div class='line host-{d['host'].lower()}'>"
                f"<span class='name'>{_esc(d.get('name', d['host']))}</span>"
                f"<span class='speech'>{_esc(d['text'])}</span></div>"
                for d in scene.dialogue
            )
            dialogue_html = f"<div class='dialogue'>{lines}</div>"
        takeaway_html = ""
        if scene.takeaway:
            takeaway_html = f"<div class='takeaway'>💡 {_esc(scene.takeaway)}</div>"

        scene_html += f"""
        <section class='scene scene-{scene.kind}'>
          <div class='scene-header'>
            <span class='icon'>{icon}</span>
            <h2>{_esc(scene.title)}</h2>
            <span class='badge'>{kind_label}</span>
          </div>
          {bullets_html}
          {quiz_html}
          {fc_html}
          {dialogue_html}
          {takeaway_html}
        </section>"""

    html_out = f"""<!DOCTYPE html>
<html lang="{_esc(plan.language)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(plan.topic)} — Report</title>
<style>
:root{{--bg:#0A1223;--card:#141E32;--accent:#38BDF8;--gold:#FBB724;--green:#4ADE80;
  --text:#F1F5F9;--muted:#94A3B8;--red:#F87171;--border:#1E2D45;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font:16px/1.6 var(--sans);padding:0 0 60px}}
header{{background:linear-gradient(135deg,#0f172a,#1e3a5f);padding:48px clamp(20px,5vw,80px) 36px;
  border-bottom:2px solid var(--accent)}}
header h1{{font-size:clamp(28px,4vw,52px);font-weight:800;line-height:1.1;margin-bottom:12px}}
.meta{{display:flex;gap:14px;flex-wrap:wrap;margin-top:14px}}
.badge{{display:inline-block;padding:4px 14px;border-radius:999px;font-size:13px;font-weight:600;
  background:var(--accent);color:#0A1223}}
.badge.fmt{{background:var(--gold);color:#0A1223}}
main{{max-width:860px;margin:0 auto;padding:40px clamp(16px,5vw,40px)}}
.scene{{background:var(--card);border-radius:16px;padding:28px;margin-bottom:28px;
  border-left:4px solid var(--accent)}}
.scene-quiz{{border-left-color:var(--gold)}}
.scene-summary{{border-left-color:var(--green)}}
.scene-flashcard{{border-left-color:var(--muted)}}
.scene-header{{display:flex;align-items:center;gap:14px;margin-bottom:18px}}
.scene-header .icon{{font-size:28px}}
.scene-header h2{{font-size:22px;font-weight:700;flex:1}}
.scene-header .badge{{background:var(--border);color:var(--muted);font-size:12px}}
.bullets{{margin:0 0 16px 20px}}
.bullets li{{margin-bottom:8px;color:var(--text)}}
.quiz .q{{font-weight:600;margin-bottom:12px;font-size:17px}}
.quiz ul{{list-style:none;display:flex;flex-direction:column;gap:8px}}
.quiz .opt{{padding:12px 18px;border-radius:8px;border:1px solid var(--border);font-size:15px}}
.quiz .correct{{border-color:var(--green);background:rgba(74,222,128,.12);color:var(--green);font-weight:600}}
.flashcards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px;margin-top:12px}}
.fc{{background:var(--bg);border:1px solid var(--border);border-radius:10px;padding:16px}}
.fc-front{{font-weight:600;color:var(--accent);margin-bottom:8px;font-size:14px}}
.fc-back{{color:var(--text);font-size:15px}}
.dialogue{{display:flex;flex-direction:column;gap:10px;margin:12px 0}}
.line{{display:flex;gap:12px;align-items:flex-start}}
.name{{font-weight:700;min-width:60px;font-size:13px;padding-top:3px}}
.host-a .name{{color:var(--accent)}}
.host-b .name{{color:var(--gold)}}
.speech{{background:var(--bg);border-radius:10px;padding:10px 14px;font-size:15px;flex:1}}
.takeaway{{margin-top:14px;padding:12px 16px;background:rgba(56,189,248,.1);
  border-radius:8px;border-left:3px solid var(--accent);font-size:15px;color:var(--accent)}}
footer{{text-align:center;margin-top:40px;color:var(--muted);font-size:14px}}
@media print{{body{{background:#fff;color:#000}}header,.scene{{background:#f8f8f8}}}}
</style>
</head>
<body>
<header>
  <h1>{_esc(plan.topic)}</h1>
  <div class="meta">
    <span class="badge fmt">{_esc(fmt_label)}</span>
    <span class="badge">{_esc(plan.length.title())} length</span>
    {f'<span class="badge">{_esc(plan.focus)}</span>' if plan.focus else ''}
  </div>
</header>
<main>
{scene_html}
</main>
<footer>Generated by aivideo Studio &nbsp;•&nbsp; {_esc(plan.topic)}</footer>
</body>
</html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html_out)
    return path
