<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Interview Intelligence Platform — Docs</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0A0F1E;
  --panel:#111A2E;
  --panel-2:#0D1526;
  --line:#212D45;
  --text:#E8ECF7;
  --muted:#8B96B5;
  --blue:#4C8DFF;
  --teal:#22D3B6;
  --amber:#F5A623;
  --red:#FF6B6B;
  --grad: linear-gradient(135deg,#4C8DFF 0%, #22D3B6 100%);
  --radius:14px;
  --mono: 'JetBrains Mono', monospace;
  --display: 'Space Grotesk', sans-serif;
  --body: 'Inter', sans-serif;
}

*{box-sizing:border-box;}
html{scroll-behavior:smooth;}
body{
  margin:0;
  background:
    radial-gradient(ellipse 1200px 600px at 15% -10%, rgba(76,141,255,0.14), transparent 60%),
    radial-gradient(ellipse 900px 500px at 100% 0%, rgba(34,211,182,0.10), transparent 55%),
    var(--bg);
  color:var(--text);
  font-family:var(--body);
  line-height:1.6;
  -webkit-font-smoothing:antialiased;
}

::selection{background:rgba(76,141,255,0.35); color:#fff;}

@media (prefers-reduced-motion: reduce){
  *{animation-duration:0.01ms !important; animation-iteration-count:1 !important; transition-duration:0.01ms !important; scroll-behavior:auto !important;}
}

a{color:inherit;}
h1,h2,h3,h4{font-family:var(--display); margin:0; letter-spacing:-0.01em;}
code, pre, .mono{font-family:var(--mono);}
.wrap{max-width:1120px; margin:0 auto; padding:0 28px;}

/* ---------- Skip link ---------- */
.skip-link{position:absolute; left:-999px; top:0; background:var(--blue); color:#00131F; padding:10px 16px; border-radius:8px; z-index:999;}
.skip-link:focus{left:16px; top:16px;}

/* ---------- Top Nav ---------- */
.topnav{
  position:sticky; top:0; z-index:100;
  background:rgba(10,15,30,0.78);
  backdrop-filter: blur(14px) saturate(140%);
  border-bottom:1px solid var(--line);
}
.topnav-inner{
  max-width:1120px; margin:0 auto; padding:14px 28px;
  display:flex; align-items:center; justify-content:space-between; gap:20px;
}
.brand{display:flex; align-items:center; gap:10px; font-family:var(--display); font-weight:700; font-size:1.05rem;}
.brand-mark{width:30px; height:30px; flex:none;}
.navlinks{display:flex; gap:22px; font-size:0.88rem; color:var(--muted);}
.navlinks a{text-decoration:none; transition:color .15s ease; padding:4px 0; border-bottom:1px solid transparent;}
.navlinks a:hover, .navlinks a:focus-visible{color:var(--text); border-color:var(--blue);}
.nav-cta{
  background:var(--grad); color:#00131F; font-weight:700; font-size:0.85rem;
  padding:9px 16px; border-radius:999px; text-decoration:none; white-space:nowrap;
  box-shadow:0 6px 20px -6px rgba(76,141,255,0.55);
}
@media (max-width:820px){ .navlinks{display:none;} }

/* ---------- Hero ---------- */
.hero{padding:88px 0 40px;}
.eyebrow{
  display:inline-flex; align-items:center; gap:8px;
  font-family:var(--mono); font-size:0.76rem; letter-spacing:0.08em; text-transform:uppercase;
  color:var(--teal); background:rgba(34,211,182,0.08); border:1px solid rgba(34,211,182,0.28);
  padding:6px 12px; border-radius:999px; margin-bottom:22px;
}
.eyebrow .dot{width:6px; height:6px; border-radius:50%; background:var(--teal); box-shadow:0 0 0 0 rgba(34,211,182,0.6); animation:pulse-dot 2s infinite;}
@keyframes pulse-dot{
  0%{box-shadow:0 0 0 0 rgba(34,211,182,0.55);}
  70%{box-shadow:0 0 0 8px rgba(34,211,182,0);}
  100%{box-shadow:0 0 0 0 rgba(34,211,182,0);}
}
.hero h1{
  font-size:clamp(2.2rem, 5vw, 3.6rem); font-weight:700; line-height:1.06; max-width:820px;
}
.hero h1 span{
  background:var(--grad); -webkit-background-clip:text; background-clip:text; color:transparent;
}
.hero p.lead{
  color:var(--muted); font-size:1.12rem; max-width:640px; margin-top:20px;
}
.hero-actions{display:flex; gap:14px; margin-top:32px; flex-wrap:wrap;}
.btn{
  display:inline-flex; align-items:center; gap:8px; font-weight:600; font-size:0.92rem;
  padding:12px 20px; border-radius:10px; text-decoration:none; border:1px solid transparent; cursor:pointer;
  transition:transform .15s ease, box-shadow .15s ease, border-color .15s ease, background .15s ease;
  font-family:var(--body);
}
.btn:active{transform:translateY(1px);}
.btn-primary{background:var(--grad); color:#00131F; box-shadow:0 10px 26px -10px rgba(76,141,255,0.6);}
.btn-primary:hover{box-shadow:0 14px 30px -8px rgba(76,141,255,0.75);}
.btn-ghost{background:var(--panel); color:var(--text); border-color:var(--line);}
.btn-ghost:hover{border-color:var(--blue);}

/* ---------- Stat strip ---------- */
.stat-strip{
  display:grid; grid-template-columns:repeat(4,1fr); gap:1px;
  background:var(--line); border:1px solid var(--line); border-radius:var(--radius);
  overflow:hidden; margin-top:56px;
}
.stat{background:var(--panel); padding:20px 22px;}
.stat .num{font-family:var(--display); font-size:1.7rem; font-weight:700;}
.stat .lbl{color:var(--muted); font-size:0.8rem; margin-top:4px;}
@media (max-width:720px){ .stat-strip{grid-template-columns:repeat(2,1fr);} }

/* ---------- Section shell ---------- */
section{padding:76px 0;}
.section-head{margin-bottom:44px; max-width:640px;}
.section-head .tag{
  font-family:var(--mono); font-size:0.75rem; text-transform:uppercase; letter-spacing:0.08em;
  color:var(--blue);
}
.section-head h2{font-size:clamp(1.6rem, 3vw, 2.1rem); margin-top:10px;}
.section-head p{color:var(--muted); margin-top:12px; font-size:1rem;}
.divider{height:1px; background:linear-gradient(90deg, transparent, var(--line), transparent);}

/* ---------- Pipeline (signature element) ---------- */
.pipeline{
  position:relative; padding:34px 20px 46px; border:1px solid var(--line); border-radius:20px;
  background:linear-gradient(180deg, rgba(255,255,255,0.02), transparent);
  overflow:hidden;
}
.pipeline-track{
  position:relative; display:flex; align-items:flex-start; justify-content:space-between;
  gap:6px; overflow-x:auto; padding-bottom:6px;
}
.pipeline-line{
  position:absolute; top:27px; left:26px; right:26px; height:2px;
  background:linear-gradient(90deg, var(--blue), var(--teal), var(--amber));
  opacity:0.35; z-index:0;
}
.pipeline-pulse{
  position:absolute; top:23px; left:26px; width:10px; height:10px; border-radius:50%;
  background:#fff; box-shadow:0 0 12px 3px rgba(76,141,255,0.9);
  animation:travel 7s linear infinite; z-index:1;
}
@keyframes travel{
  0%{left:26px; opacity:0;}
  4%{opacity:1;}
  96%{opacity:1;}
  100%{left:calc(100% - 36px); opacity:0;}
}
.node{
  position:relative; z-index:2; flex:1 1 0; min-width:128px; text-align:center;
  display:flex; flex-direction:column; align-items:center; gap:10px; cursor:default;
}
.node-dot{
  width:54px; height:54px; border-radius:14px; display:flex; align-items:center; justify-content:center;
  background:var(--panel-2); border:1px solid var(--line); font-size:1.35rem;
  transition:transform .2s ease, border-color .2s ease, background .2s ease;
}
.node:hover .node-dot{transform:translateY(-4px) scale(1.06); border-color:var(--blue); background:var(--panel);}
.node-title{font-size:0.82rem; font-weight:600; color:var(--text);}
.node-desc{font-size:0.74rem; color:var(--muted); max-width:130px;}
.node-arrow{color:var(--line); font-size:1rem; align-self:center; padding-top:16px;}
@media (max-width:900px){
  .pipeline-track{flex-wrap:wrap; overflow-x:visible;}
  .pipeline-line, .pipeline-pulse{display:none;}
  .node{min-width:44%; flex:1 1 44%;}
  .node-arrow{display:none;}
}

/* ---------- Feature grid ---------- */
.grid{display:grid; grid-template-columns:repeat(3,1fr); gap:16px;}
@media (max-width:900px){ .grid{grid-template-columns:repeat(2,1fr);} }
@media (max-width:620px){ .grid{grid-template-columns:1fr;} }

.card{
  background:var(--panel); border:1px solid var(--line); border-radius:var(--radius);
  padding:22px; transition:border-color .15s ease, transform .15s ease;
}
.card:hover{border-color:var(--blue); transform:translateY(-3px);}
.card .icon{
  width:38px; height:38px; border-radius:10px; display:flex; align-items:center; justify-content:center;
  background:rgba(76,141,255,0.12); color:var(--blue); margin-bottom:14px; font-size:1.05rem;
}
.card.new .icon{background:rgba(34,211,182,0.14); color:var(--teal);}
.card h4{font-size:1rem; font-weight:600; margin-bottom:6px; display:flex; align-items:center; gap:8px;}
.badge-new{
  font-family:var(--mono); font-size:0.62rem; letter-spacing:0.05em; background:rgba(34,211,182,0.16);
  color:var(--teal); padding:2px 7px; border-radius:999px; border:1px solid rgba(34,211,182,0.35);
}
.card p{color:var(--muted); font-size:0.87rem; margin:0;}

/* ---------- Analytics preview ---------- */
.analytics-preview{
  display:grid; grid-template-columns:1.1fr 1fr; gap:20px; align-items:stretch;
}
@media (max-width:860px){ .analytics-preview{grid-template-columns:1fr;} }
.mock-panel{
  background:var(--panel); border:1px solid var(--line); border-radius:var(--radius); padding:20px;
}
.mock-kpis{display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:16px;}
.mock-kpi{background:var(--panel-2); border:1px solid var(--line); border-radius:10px; padding:12px;}
.mock-kpi .k-label{font-size:0.68rem; color:var(--muted); text-transform:uppercase; letter-spacing:0.04em;}
.mock-kpi .k-val{font-family:var(--display); font-size:1.3rem; font-weight:700; margin-top:4px;}
.chart-box{background:var(--panel-2); border:1px solid var(--line); border-radius:10px; padding:14px; height:170px;}
.side-copy h4{font-size:1.05rem; margin-bottom:10px;}
.side-copy ul{margin:0; padding-left:18px; color:var(--muted); font-size:0.9rem;}
.side-copy li{margin-bottom:8px;}
.side-copy li b{color:var(--text);}

/* ---------- Tabs (Quick start) ---------- */
.tabs{display:flex; gap:6px; border-bottom:1px solid var(--line); margin-bottom:0; flex-wrap:wrap;}
.tab-btn{
  font-family:var(--mono); font-size:0.82rem; color:var(--muted); background:transparent; border:none;
  padding:12px 16px; cursor:pointer; border-bottom:2px solid transparent; transition:color .15s ease, border-color .15s ease;
}
.tab-btn:hover{color:var(--text);}
.tab-btn.active{color:var(--teal); border-color:var(--teal);}
.tab-panel{display:none; padding-top:18px;}
.tab-panel.active{display:block;}

.codeblock{
  position:relative; background:#080C17; border:1px solid var(--line); border-radius:12px;
  padding:18px 50px 18px 18px; overflow-x:auto; font-family:var(--mono); font-size:0.84rem; color:#CDE0FF;
  line-height:1.7;
}
.codeblock .c{color:#5B6B8C;}
.copy-btn{
  position:absolute; top:10px; right:10px; background:var(--panel); border:1px solid var(--line);
  color:var(--muted); font-family:var(--body); font-size:0.72rem; padding:5px 9px; border-radius:7px;
  cursor:pointer; transition:all .15s ease;
}
.copy-btn:hover{color:var(--text); border-color:var(--blue);}
.copy-btn.copied{color:var(--teal); border-color:var(--teal);}
.note{
  margin-top:14px; font-size:0.85rem; color:var(--muted); background:rgba(76,141,255,0.06);
  border-left:3px solid var(--blue); padding:12px 14px; border-radius:0 8px 8px 0;
}
.note.warn{border-color:var(--amber); background:rgba(245,166,35,0.07);}

/* ---------- API table ---------- */
.api-table{width:100%; border-collapse:collapse; font-size:0.88rem;}
.api-table th{
  text-align:left; font-family:var(--mono); font-size:0.72rem; text-transform:uppercase; letter-spacing:0.05em;
  color:var(--muted); padding:10px 14px; border-bottom:1px solid var(--line);
}
.api-table td{padding:13px 14px; border-bottom:1px solid var(--line); vertical-align:top;}
.api-table tr:last-child td{border-bottom:none;}
.method{
  font-family:var(--mono); font-size:0.72rem; font-weight:700; padding:3px 8px; border-radius:6px;
  background:rgba(76,141,255,0.14); color:var(--blue);
}
.method.get{background:rgba(34,211,182,0.14); color:var(--teal);}
.api-table code{font-size:0.83rem; color:#CDE0FF;}

/* ---------- Structure tree (collapsible) ---------- */
.tree-wrap{background:#080C17; border:1px solid var(--line); border-radius:12px; padding:8px 4px;}
.tree{font-family:var(--mono); font-size:0.83rem; padding:8px 14px 14px;}
details{margin:2px 0;}
summary{cursor:pointer; color:var(--text); padding:5px 0; list-style:none; display:flex; align-items:center; gap:8px;}
summary::-webkit-details-marker{display:none;}
summary::before{content:"▸"; color:var(--blue); display:inline-block; transition:transform .15s ease; font-size:0.75rem;}
details[open] > summary::before{transform:rotate(90deg);}
.tree .file{padding:5px 0 5px 26px; color:var(--muted); display:flex; gap:10px;}
.tree .file .comment{color:#5B6B8C;}
.tree .indent{padding-left:20px; border-left:1px dashed var(--line); margin-left:5px;}

/* ---------- Contracts (JSON viewers) ---------- */
.contract-grid{display:grid; grid-template-columns:repeat(2,1fr); gap:16px;}
@media (max-width:760px){ .contract-grid{grid-template-columns:1fr;} }
.contract{background:var(--panel); border:1px solid var(--line); border-radius:12px; overflow:hidden;}
.contract h5{
  margin:0; padding:12px 16px; font-family:var(--mono); font-size:0.8rem; background:var(--panel-2);
  border-bottom:1px solid var(--line); color:var(--teal);
}
.contract pre{margin:0; padding:14px 16px; font-size:0.78rem; color:#CDE0FF; overflow-x:auto;}

/* ---------- Stack chips ---------- */
.chip-row{display:flex; flex-wrap:wrap; gap:10px;}
.chip{
  display:flex; align-items:center; gap:8px; background:var(--panel); border:1px solid var(--line);
  padding:9px 14px; border-radius:999px; font-size:0.84rem;
}
.chip .sw{width:9px; height:9px; border-radius:50%;}

/* ---------- Deploy card ---------- */
.deploy-card{
  border:1px solid var(--line); border-radius:var(--radius); overflow:hidden;
  background:linear-gradient(135deg, rgba(76,141,255,0.07), rgba(34,211,182,0.05));
}
.deploy-head{padding:24px 26px; display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap;}
.deploy-head h3{font-size:1.15rem;}
.live-pill{
  display:inline-flex; align-items:center; gap:7px; font-family:var(--mono); font-size:0.76rem;
  color:var(--teal); background:rgba(34,211,182,0.1); border:1px solid rgba(34,211,182,0.3);
  padding:6px 12px; border-radius:999px;
}
.live-pill .dot{width:6px; height:6px; border-radius:50%; background:var(--teal); animation:pulse-dot 2s infinite;}
.deploy-steps{padding:0 26px 26px; display:grid; grid-template-columns:repeat(5,1fr); gap:12px;}
@media (max-width:900px){ .deploy-steps{grid-template-columns:repeat(2,1fr);} }
.dstep{background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:14px;}
.dstep .n{font-family:var(--display); font-weight:700; color:var(--blue); font-size:0.85rem; margin-bottom:6px;}
.dstep p{font-size:0.78rem; color:var(--muted); margin:0;}

/* ---------- Footer ---------- */
footer{padding:50px 0 70px; border-top:1px solid var(--line); margin-top:20px;}
.footer-inner{display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px;}
.footer-inner .muted{color:var(--muted); font-size:0.85rem;}
.back-to-top{
  font-size:0.82rem; color:var(--muted); text-decoration:none; display:inline-flex; align-items:center; gap:6px;
  border:1px solid var(--line); padding:8px 14px; border-radius:999px; transition:border-color .15s ease, color .15s ease;
}
.back-to-top:hover{color:var(--text); border-color:var(--blue);}

/* scroll reveal */
.reveal{opacity:0; transform:translateY(16px); transition:opacity .6s ease, transform .6s ease;}
.reveal.in{opacity:1; transform:none;}
</style>
</head>
<body>

<a href="#main" class="skip-link">Skip to content</a>

<nav class="topnav">
  <div class="topnav-inner">
    <div class="brand">
      <svg class="brand-mark" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="32" height="32" rx="8" fill="url(#g)"/>
        <path d="M9 20L13 12L17 18L23 9" stroke="#00131F" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
        <defs><linearGradient id="g" x1="0" y1="0" x2="32" y2="32"><stop stop-color="#4C8DFF"/><stop offset="1" stop-color="#22D3B6"/></linearGradient></defs>
      </svg>
      Interview Intelligence
    </div>
    <div class="navlinks">
      <a href="#pipeline">Pipeline</a>
      <a href="#modules">Modules</a>
      <a href="#analytics">Analytics</a>
      <a href="#quickstart">Quick Start</a>
      <a href="#api">API</a>
      <a href="#deploy">Deploy</a>
    </div>
    <a class="nav-cta" href="https://interview-question-generator-skill-asseappr-task-1-ikw9yjgpvyw.streamlit.app/" target="_blank" rel="noopener">Live Demo ↗</a>
  </div>
</nav>

<main id="main">

  <!-- HERO -->
  <div class="wrap">
    <section class="hero" style="padding-bottom:0;">
      <div class="eyebrow"><span class="dot"></span> LLM-powered · PostgreSQL-backed · deployed on Streamlit Cloud</div>
      <h1>Prepare smarter.<br><span>Hire better.</span></h1>
      <p class="lead">
        Upload a resume and a job description. Get a weighted skill-match score, personalized
        interview questions, voice or text answers scored by AI, and a live analytics dashboard
        that tracks progress across every session — all wired end to end, not just individually functional.
      </p>
      <div class="hero-actions">
        <a class="btn btn-primary" href="https://interview-question-generator-skill-asseappr-task-1-ikw9yjgpvyw.streamlit.app/" target="_blank" rel="noopener">▶ Try the live app</a>
        <a class="btn btn-ghost" href="#quickstart">Run it locally</a>
        <a class="btn btn-ghost" href="#api">Explore the API</a>
      </div>

      <div class="stat-strip reveal">
        <div class="stat"><div class="num">9</div><div class="lbl">Wired modules, one pipeline</div></div>
        <div class="stat"><div class="num">7</div><div class="lbl">REST endpoints</div></div>
        <div class="stat"><div class="num">2</div><div class="lbl">Portals — Student &amp; Recruiter</div></div>
        <div class="stat"><div class="num">100%</div><div class="lbl">Degrades gracefully without a DB</div></div>
      </div>
    </section>
  </div>

  <!-- PIPELINE -->
  <div class="wrap">
    <section id="pipeline">
      <div class="section-head reveal">
        <div class="tag">// 01 — how data flows</div>
        <h2>One pipeline, five AI stages</h2>
        <p>Every module speaks the same JSON contracts, so a resume can travel from raw PDF to a scored interview report without a single manual hand-off.</p>
      </div>

      <div class="pipeline reveal">
        <div class="pipeline-track">
          <div class="pipeline-line"></div>
          <div class="pipeline-pulse"></div>

          <div class="node" tabindex="0">
            <div class="node-dot">📄</div>
            <div class="node-title">Resume</div>
            <div class="node-desc">PDF/DOCX → structured JSON</div>
          </div>
          <div class="node-arrow">→</div>
          <div class="node" tabindex="0">
            <div class="node-dot">🧾</div>
            <div class="node-title">JD Parsing</div>
            <div class="node-desc">Raw text → structured role</div>
          </div>
          <div class="node-arrow">→</div>
          <div class="node" tabindex="0">
            <div class="node-dot">🎯</div>
            <div class="node-title">Matching</div>
            <div class="node-desc">Weighted skill-gap score</div>
          </div>
          <div class="node-arrow">→</div>
          <div class="node" tabindex="0">
            <div class="node-dot">❓</div>
            <div class="node-title">Questions</div>
            <div class="node-desc">Personalized to the gap</div>
          </div>
          <div class="node-arrow">→</div>
          <div class="node" tabindex="0">
            <div class="node-dot">🎙️</div>
            <div class="node-title">Answer</div>
            <div class="node-desc">Voice or text response</div>
          </div>
          <div class="node-arrow">→</div>
          <div class="node" tabindex="0">
            <div class="node-dot">✅</div>
            <div class="node-title">Evaluation</div>
            <div class="node-desc">Scored feedback + report</div>
          </div>
        </div>
      </div>
    </section>

    <div class="divider"></div>

    <!-- MODULES -->
    <section id="modules">
      <div class="section-head reveal">
        <div class="tag">// 02 — what's inside</div>
        <h2>Nine modules, one shared contract</h2>
        <p>Each module is independently testable and independently importable — <code>app.py</code> and the FastAPI layer both call the exact same packages underneath.</p>
      </div>
      <div class="grid reveal">
        <div class="card"><div class="icon">📄</div><h4>Resume Processing</h4><p>PDF or DOCX → structured resume JSON: skills, education, experience, projects, certifications.</p></div>
        <div class="card"><div class="icon">🧾</div><h4>JD Parsing</h4><p>Raw job-description text → structured role, required/preferred skills, experience level.</p></div>
        <div class="card"><div class="icon">🎯</div><h4>Matching Engine</h4><p>Deterministic, weighted resume ↔ JD scoring with matched and missing skill breakdowns.</p></div>
        <div class="card"><div class="icon">❓</div><h4>Question Generation</h4><p>Resume + JD + match result → interview questions personalized to the candidate's actual gaps.</p></div>
        <div class="card"><div class="icon">✅</div><h4>Answer Evaluation</h4><p>Scores correctness, clarity, communication, completeness &amp; keyword coverage — with an ideal answer.</p></div>
        <div class="card"><div class="icon">🎙️</div><h4>Speech-to-Text</h4><p>Recorded voice answers transcribed before evaluation, so interviews aren't typing tests.</p></div>
        <div class="card"><div class="icon">🗄️</div><h4>Database</h4><p>PostgreSQL persistence for every stage — best-effort everywhere except auth, which needs it.</p></div>
        <div class="card"><div class="icon">🔌</div><h4>REST API</h4><p>A standalone FastAPI layer over the first five modules, for other frontends &amp; integrations.</p></div>
        <div class="card new"><div class="icon">📊</div><h4>Analytics <span class="badge-new">NEW</span></h4><p>Aggregates a user's own history into score trends, category breakdowns, and skill-gap charts.</p></div>
      </div>
    </section>

    <div class="divider"></div>

    <!-- ANALYTICS PREVIEW -->
    <section id="analytics">
      <div class="section-head reveal">
        <div class="tag">// 03 — the analytics dashboard</div>
        <h2>See progress, not just scores</h2>
        <p>Every completed interview and every screened candidate writes to Postgres — the Analytics page turns that history into charts, for both portals.</p>
      </div>

      <div class="analytics-preview reveal">
        <div class="mock-panel">
          <div class="mock-kpis">
            <div class="mock-kpi"><div class="k-label">Interviews</div><div class="k-val">14</div></div>
            <div class="mock-kpi"><div class="k-label">Avg Score</div><div class="k-val">78</div></div>
            <div class="mock-kpi"><div class="k-label">Best Score</div><div class="k-val">94</div></div>
          </div>
          <div class="chart-box">
            <svg viewBox="0 0 320 130" width="100%" height="100%" preserveAspectRatio="none">
              <defs>
                <linearGradient id="fillgrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#4C8DFF" stop-opacity="0.35"/>
                  <stop offset="100%" stop-color="#4C8DFF" stop-opacity="0"/>
                </linearGradient>
              </defs>
              <polyline fill="url(#fillgrad)" stroke="none" points="0,110 0,90 40,95 80,70 120,78 160,55 200,60 240,35 280,42 320,20 320,130 0,130"/>
              <polyline fill="none" stroke="#4C8DFF" stroke-width="2.5" points="0,90 40,95 80,70 120,78 160,55 200,60 240,35 280,42 320,20" />
              <circle cx="320" cy="20" r="4" fill="#22D3B6"/>
            </svg>
          </div>
        </div>
        <div class="side-copy">
          <h4>What you actually get</h4>
          <ul>
            <li><b>Students:</b> score trend over time, per-category breakdown (correctness, clarity, communication…), resume↔JD match trend, and your most common strengths &amp; improvement themes.</li>
            <li><b>Recruiters:</b> candidates screened, average &amp; best match score, shortlist rate, score distribution, and the most common missing skills across everyone you've screened.</li>
            <li>Built with Plotly on top of the same repository functions that already power your reports — no duplicated logic, no separate data pipeline.</li>
            <li>Shows a friendly empty state instead of breaking if there's no database configured yet.</li>
          </ul>
        </div>
      </div>
    </section>

    <div class="divider"></div>

    <!-- QUICK START -->
    <section id="quickstart">
      <div class="section-head reveal">
        <div class="tag">// 04 — get running</div>
        <h2>Quick start</h2>
        <p>Two independent ways to run this: the full Streamlit app, or the standalone REST API. Pick a tab.</p>
      </div>

      <div class="reveal">
        <div class="tabs" role="tablist">
          <button class="tab-btn active" data-tab="app" role="tab">streamlit app</button>
          <button class="tab-btn" data-tab="api" role="tab">rest api</button>
          <button class="tab-btn" data-tab="db" role="tab">postgresql</button>
        </div>

        <div class="tab-panel active" id="tab-app">
          <div class="codeblock" id="code-app"><button class="copy-btn" onclick="copyCode('code-app')">Copy</button><span class="c"># clone, install, configure</span>
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              <span class="c"># add GLM_API_KEY at minimum</span>
streamlit run app.py</div>
          <div class="note">Opens at <code>http://localhost:8501</code>. <b>DATABASE_URL is required to log in or sign up</b> — everything else (speech-to-text, saving history) degrades gracefully without one. The sidebar shows a live "Database connected" indicator.</div>
        </div>

        <div class="tab-panel" id="tab-api">
          <div class="codeblock" id="code-api"><button class="copy-btn" onclick="copyCode('code-api')">Copy</button><span class="c"># standalone FastAPI service</span>
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              <span class="c"># fill in GLM_API_KEY</span>
python main.py
<span class="c"># → http://127.0.0.1:8000/docs</span></div>
          <div class="note">Swagger UI at <code>/docs</code>, ReDoc at <code>/redoc</code>, health check at <code>GET /api/v1/health</code>. Same underlying modules as <code>app.py</code> — no duplicated business logic.</div>
        </div>

        <div class="tab-panel" id="tab-db">
          <div class="codeblock" id="code-db"><button class="copy-btn" onclick="copyCode('code-db')">Copy</button><span class="c"># after adding DATABASE_URL to .env</span>
python -m database.init_db</div>
          <div class="note warn">Streamlit Community Cloud has no persistent local disk — point <code>DATABASE_URL</code> at a hosted Postgres instance (Neon, Supabase, Render, Railway) before deploying.</div>
        </div>
      </div>
    </section>

    <div class="divider"></div>

    <!-- API TABLE -->
    <section id="api">
      <div class="section-head reveal">
        <div class="tag">// 05 — rest endpoints</div>
        <h2>API reference</h2>
        <p>Every error response shares one shape: <code>{"error_type": "...", "detail": "..."}</code>. Bad input → <code>422</code>. Unexpected errors → <code>500</code>.</p>
      </div>
      <div class="reveal" style="overflow-x:auto; border:1px solid var(--line); border-radius:var(--radius);">
        <table class="api-table">
          <thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead>
          <tbody>
            <tr><td><span class="method">POST</span></td><td><code>/api/v1/resume/parse</code></td><td>Upload a resume PDF → structured resume JSON</td></tr>
            <tr><td><span class="method">POST</span></td><td><code>/api/v1/jd/parse</code></td><td><code>{"jd_text": "..."}</code> → structured JD JSON</td></tr>
            <tr><td><span class="method">POST</span></td><td><code>/api/v1/match</code></td><td><code>{resume_json, jd_json}</code> → match score</td></tr>
            <tr><td><span class="method">POST</span></td><td><code>/api/v1/questions/generate</code></td><td>resume + JD + match JSON → generated questions</td></tr>
            <tr><td><span class="method">POST</span></td><td><code>/api/v1/interview/evaluate</code></td><td>question + candidate answer → scored evaluation</td></tr>
            <tr><td><span class="method">POST</span></td><td><code>/api/v1/pipeline/analyze</code></td><td>resume file + JD text → resume + JD + match, one call</td></tr>
            <tr><td><span class="method get">GET</span></td><td><code>/api/v1/health</code></td><td>Liveness check</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <div class="divider"></div>

    <!-- CONTRACTS -->
    <section id="contracts">
      <div class="section-head reveal">
        <div class="tag">// 06 — data contracts</div>
        <h2>What flows between modules</h2>
        <p>Convert Pydantic objects with <code>.model_dump()</code> before passing them onward — these shapes are the contract every module agrees on.</p>
      </div>
      <div class="contract-grid reveal">
        <div class="contract">
          <h5>ParsedResume</h5>
          <pre>{
  "name": "", "email": "", "phone": "",
  "linkedin": "", "github": "",
  "skills": [], "education": [],
  "experience": [], "projects": [],
  "certifications": []
}</pre>
        </div>
        <div class="contract">
          <h5>ParsedJD</h5>
          <pre>{
  "role": "", "required_skills": [],
  "preferred_skills": [],
  "responsibilities": [],
  "experience_level": "",
  "education_requirement": ""
}</pre>
        </div>
        <div class="contract">
          <h5>MatchResult</h5>
          <pre>{
  "score": 0.0,
  "required_coverage": 0.0,
  "preferred_coverage": 0.0,
  "matched_required": [],
  "missing_required": [],
  "matched_preferred": [],
  "missing_preferred": [],
  "inferred_skills": [],
  "skill_gap": [{"skill":"","type":"","priority":""}]
}</pre>
        </div>
        <div class="contract">
          <h5>EvaluationResult</h5>
          <pre>{
  "overall_score": 0, "correctness": 0,
  "keyword_coverage": 0, "clarity": 0,
  "communication": 0, "completeness": 0,
  "strengths": [], "improvements": [],
  "feedback": "", "ideal_answer": ""
}</pre>
        </div>
      </div>
    </section>

    <div class="divider"></div>

    <!-- STRUCTURE -->
    <section id="structure">
      <div class="section-head reveal">
        <div class="tag">// 07 — project structure</div>
        <h2>Where everything lives</h2>
        <p>Click a folder to expand it.</p>
      </div>
      <div class="tree-wrap reveal">
        <div class="tree">
          <div class="file">README.md<span class="comment"> · this file</span></div>
          <div class="file">requirements.txt<span class="comment"> · includes plotly + pandas for analytics</span></div>
          <div class="file">.env.example</div>
          <div class="file">main.py<span class="comment"> · python main.py → runs the API</span></div>

          <details>
            <summary>api/ <span class="comment" style="margin-left:6px;">— FastAPI layer</span></summary>
            <div class="indent">
              <div class="file">main.py<span class="comment"> · uvicorn api.main:app</span></div>
              <div class="file">schemas.py</div>
              <div class="file">exception_handlers.py</div>
              <div class="file">routes/ <span class="comment">resume · jd · matching · questions · evaluation · pipeline</span></div>
              <div class="file">tests/</div>
            </div>
          </details>

          <details>
            <summary>resume_processing/ <span class="comment" style="margin-left:6px;">— PDF → structured JSON</span></summary>
            <div class="indent">
              <div class="file">pdf_extractor.py · text_cleaner.py · resume_parser.py</div>
              <div class="file">validator.py · normalizer.py · process_resume.py</div>
              <div class="file">prompts/resume_parser_prompt.txt</div>
            </div>
          </details>

          <details>
            <summary>jd_parsing/ <span class="comment" style="margin-left:6px;">— raw text → structured JD</span></summary>
            <div class="indent">
              <div class="file">jd_parser.py · output_validator.py · parse_jd.py</div>
              <div class="file">prompts/jd_parser_prompt.txt</div>
            </div>
          </details>

          <details>
            <summary>matching_engine/ <span class="comment" style="margin-left:6px;">— deterministic scoring</span></summary>
            <div class="indent"><div class="file">matching_engine.py</div></div>
          </details>

          <details>
            <summary>question_generation/</summary>
            <div class="indent">
              <div class="file">prompt_builder.py · output_validator.py · generate_questions.py</div>
            </div>
          </details>

          <details>
            <summary>answer_evaluation/</summary>
            <div class="indent">
              <div class="file">evaluator.py · output_validator.py · evaluate_answer.py</div>
            </div>
          </details>

          <details>
            <summary>database/ <span class="comment" style="margin-left:6px;">— models, repositories, analytics</span></summary>
            <div class="indent">
              <div class="file">models.py · repositories.py · security.py · safe.py · init_db.py</div>
            </div>
          </details>

          <details>
            <summary>app.py <span class="comment" style="margin-left:6px;">— the Streamlit frontend</span></summary>
            <div class="indent">
              <div class="file">Home · Student &amp; Recruiter dashboards · Interview · Report</div>
              <div class="file">Candidates · <b style="color:var(--teal)">Analytics</b> · Settings</div>
            </div>
          </details>

          <div class="file">samples/</div>
          <div class="file">scripts/ <span class="comment">demo_parser.py · demo_matching.py</span></div>
        </div>
      </div>
    </section>

    <div class="divider"></div>

    <!-- DEPLOY -->
    <section id="deploy">
      <div class="section-head reveal">
        <div class="tag">// 08 — deployment</div>
        <h2>Live on Streamlit Community Cloud</h2>
      </div>
      <div class="deploy-card reveal">
        <div class="deploy-head">
          <h3>interview-intelligence-platform</h3>
          <a class="live-pill" href="https://interview-question-generator-skill-asseappr-task-1-ikw9yjgpvyw.streamlit.app/" target="_blank" rel="noopener"><span class="dot"></span> LIVE — open app ↗</a>
        </div>
        <div class="deploy-steps">
          <div class="dstep"><div class="n">01</div><p>Push to GitHub — <code>.env</code> stays out via <code>.gitignore</code>.</p></div>
          <div class="dstep"><div class="n">02</div><p>Create an app on share.streamlit.io pointing at <code>app.py</code>.</p></div>
          <div class="dstep"><div class="n">03</div><p>Paste <code>.env.example</code> keys into Settings → Secrets, filled in.</p></div>
          <div class="dstep"><div class="n">04</div><p>Point <code>DATABASE_URL</code> at a hosted Postgres (Neon/Supabase/Render).</p></div>
          <div class="dstep"><div class="n">05</div><p>Run <code>database.init_db</code> once locally against that same URL.</p></div>
        </div>
      </div>
    </section>

    <div class="divider"></div>

    <!-- STACK -->
    <section id="stack">
      <div class="section-head reveal">
        <div class="tag">// 09 — built with</div>
        <h2>Tech stack</h2>
      </div>
      <div class="chip-row reveal">
        <div class="chip"><span class="sw" style="background:#4C8DFF"></span>Python 3.11+</div>
        <div class="chip"><span class="sw" style="background:#22D3B6"></span>Streamlit</div>
        <div class="chip"><span class="sw" style="background:#F5A623"></span>FastAPI</div>
        <div class="chip"><span class="sw" style="background:#FF6B6B"></span>PostgreSQL + SQLAlchemy</div>
        <div class="chip"><span class="sw" style="background:#4C8DFF"></span>Pydantic</div>
        <div class="chip"><span class="sw" style="background:#22D3B6"></span>Plotly + Pandas</div>
        <div class="chip"><span class="sw" style="background:#F5A623"></span>GLM (LLM backend)</div>
        <div class="chip"><span class="sw" style="background:#FF6B6B"></span>pytest</div>
      </div>
    </section>

  </div>

  <footer>
    <div class="wrap footer-inner">
      <div class="muted">Interview Intelligence Platform · Python 3.11+ · MIT-style internal use</div>
      <a class="back-to-top" href="#main">↑ Back to top</a>
    </div>
  </footer>
</main>

<script>
// Tabs
document.querySelectorAll('.tab-btn').forEach(btn=>{
  btn.addEventListener('click', ()=>{
    document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-'+btn.dataset.tab).classList.add('active');
  });
});

// Copy to clipboard
function copyCode(id){
  const el = document.getElementById(id);
  const btn = el.querySelector('.copy-btn');
  const text = el.innerText.replace('Copy','').trim();
  navigator.clipboard.writeText(text).then(()=>{
    const old = btn.textContent;
    btn.textContent = 'Copied ✓';
    btn.classList.add('copied');
    setTimeout(()=>{ btn.textContent = old; btn.classList.remove('copied'); }, 1600);
  });
}

// Scroll reveal
const io = new IntersectionObserver((entries)=>{
  entries.forEach(e=>{ if(e.isIntersecting){ e.target.classList.add('in'); io.unobserve(e.target); } });
}, {threshold:0.12});
document.querySelectorAll('.reveal').forEach(el=>io.observe(el));
</script>

</body>
</html>
