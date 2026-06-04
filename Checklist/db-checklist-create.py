#!/usr/bin/env python3
#
# db-checklist-create.py
#
# Reads a plaintext version of the GMP checklist and
# outputs a HTML version specified with --output.
#

import re
import json
import argparse
import os
import sys

def get_args():
    parser = argparse.ArgumentParser(description="Convert GMP plain text to interactive HTML.")
    parser.add_argument("input", help="Path to the input plain text file")
    parser.add_argument("-o", "--output", help="Path to the output HTML file")
    return parser.parse_args()

def parse_text(file_path):
    if not os.path.exists(file_path):
        print(f"Error: Input file '{file_path}' not found.")
        sys.exit(1)
    with open(file_path, 'r', encoding='utf-8') as f:
        full_content = f.read()
    content_part = full_content.split("CONTENT", 1)[-1] if "CONTENT" in full_content else full_content
    sections = []
    section_blocks = re.split(r'\n(?=\d+\.\s+[A-Z])', content_part)
    for block in section_blocks:
        lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
        if not lines: continue
        section_title = lines[0]
        questions = []
        q_blocks = re.split(r'\n(?=\d+\.\d+\.\s+)', '\n'.join(lines[1:]))
        for q_text in q_blocks:
            q_lines = [l.strip() for l in q_text.strip().split('\n') if l.strip()]
            if not q_lines: continue
            header = q_lines[0]
            num_match = re.match(r'^(\d+\.\d+)', header)
            q_id = num_match.group(1) if num_match else header
            reqs = {"a": "", "b": "", "c": "", "d": ""}
            refs = []
            for line in q_lines[1:]:
                match = re.match(r'^([a-d])\.\s*(?:CFR:|Requirement:|Significance:|Fix:)?\s*(.*)', line, re.IGNORECASE)
                if match:
                    label, text = match.groups()
                    reqs[label.lower()] = text
                else:
                    clean_line = re.sub(r'^[e-z]\.\s*', '', line, flags=re.IGNORECASE)
                    url_match = re.search(r'(https?://[^\s]+)', clean_line)
                    if url_match:
                        url = url_match.group(1)
                        display_text = clean_line.replace(url, "").strip().rstrip(':').strip()
                        refs.append({"text": display_text or "Link", "url": url})
                    else:
                        refs.append({"text": clean_line, "url": None})
            questions.append({"id": q_id, "title": header, "reqs": reqs, "refs": refs})
        if questions:
            sections.append({"title": section_title, "questions": questions})
    return sections

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>FSMA/GMP Auditor</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; display: flex; margin: 0; height: 100vh; background: #f0f2f5; }
        #sidebar { width: 320px; background: #1a252f; color: #bfcbd9; display: flex; flex-direction: column; flex-shrink: 0; }
        .sidebar-header { padding: 25px 15px 10px 15px; font-size: 1.6em; font-weight: bold; color: #fff; border-bottom: 1px solid #2c3e50; }
        #menu { flex-grow: 1; overflow-y: auto; padding: 10px; }
        .menu-item { cursor: pointer; padding: 12px 15px; border-bottom: 1px solid #2c3e50; font-size: 0.9em; transition: 0.2s; }
        .menu-item:hover { background: #2c3e50; color: #fff; }
        .menu-item.active { background: #409eff; color: #fff; font-weight: bold; }
        #main { flex-grow: 1; display: flex; flex-direction: column; overflow: hidden; }
        .top-nav { background: #fff; padding: 15px 30px; border-bottom: 1px solid #dcdfe6; display: flex; justify-content: space-between; align-items: center; z-index: 10; }
        #content { flex-grow: 1; overflow-y: auto; padding: 40px; }
        .question-block { background: #fff; padding: 30px; margin-bottom: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); border: 1px solid #ebeef5; }
        .q-title { font-size: 1.5em; font-weight: bold; margin-bottom: 20px; border-bottom: 2px solid #409eff; padding-bottom: 5px; color: #303133; }
        .line { margin: 10px 0; line-height: 1.5; }
        .bold-label { font-weight: bold; color: #606266; }
        .ref-section { margin-top: 20px; padding: 15px; background: #f8f9fa; border-left: 4px solid #409eff; border-radius: 0 4px 4px 0; }
        .hidden { display: none !important; }
        button { padding: 9px 20px; cursor: pointer; border-radius: 4px; border: 1px solid #dcdfe6; background: #fff; font-weight: 600; }
        .save-btn { background: #67c23a; color: white; border: none; }
        .filter-btn { margin: 20px; background: #409eff; color: white; border: none; }
        .notes-area { width: 100%; box-sizing: border-box; margin-top: 10px; padding: 10px; border: 1px solid #dcdfe6; border-radius: 4px; font-family: inherit; resize: vertical; min-height: 80px; }
        input[type="text"] { border: 1px solid #dcdfe6; padding: 8px 12px; border-radius: 4px; outline: none; }
        input[type="text"]:focus { border-color: #409eff; }
    </style>
</head>
<body>
    <div id="sidebar">
        <div class="sidebar-header">GMP Checklist</div>
        <div id="menu"></div>
        <button class="filter-btn" id="filterBtn" onclick="toggleFilter()">Filter Selected</button>
    </div>
    <div id="main">
        <div class="top-nav">
            <div><strong>Company:</strong> <input type="text" id="companyName" placeholder="Enter company name" oninput="globalState.company=this.value"></div>
            <div>
                <button class="save-btn" onclick="saveJSON()">Save Session</button>
                <button onclick="document.getElementById('loadInput').click()">Load Session</button>
                <input type="file" id="loadInput" class="hidden" onchange="loadJSON(event)">
            </div>
        </div>
        <div id="content"></div>
    </div>
    <script>
        const sections = JSON.parse('JSON_DATA_HERE');
        let globalState = { company: "", results: {}, isFiltered: false, currentSectionIdx: 0 };

        function init() {
            if (!sections.length) return;
            renderMenu(); renderSection();
        }

        function renderMenu() {
            const menu = document.getElementById('menu');
            menu.innerHTML = "";
            sections.forEach((sec, idx) => {
                const hasSel = sec.questions.some(q => globalState.results[q.id]?.selected);
                if (globalState.isFiltered && !hasSel) return;
                const item = document.createElement('div');
                item.className = 'menu-item' + (globalState.currentSectionIdx === idx ? ' active' : '');
                item.innerText = sec.title;
                item.onclick = () => { globalState.currentSectionIdx = idx; renderMenu(); renderSection(); };
                menu.appendChild(item);
            });
        }

        function renderSection() {
            const container = document.getElementById('content');
            const sec = sections[globalState.currentSectionIdx];
            if (!sec) return;
            container.innerHTML = `<h1 style="margin-top:0; color:#303133;">${sec.title}</h1>`;
            sec.questions.forEach(q => {
                const res = globalState.results[q.id] || { selected: false, corrected: false, notes: "" };
                if (globalState.isFiltered && !res.selected) return;
                const div = document.createElement('div');
                div.className = 'question-block';
                const refs = q.refs.map(r => r.url ? `<li><a href="${r.url}" target="_blank">${r.text}</a></li>` : `<li>${r.text}</li>`).join('');
                div.innerHTML = `
                    <div class="q-title">${q.title}</div>
                    <div class="line"><span class="bold-label">a. CFR:</span> ${q.reqs.a}</div>
                    <div class="line"><span class="bold-label">b. Requirement:</span> ${q.reqs.b}</div>
                    <div class="line"><span class="bold-label">c. Significance:</span> ${q.reqs.c}</div>
                    <div class="line"><span class="bold-label">d. Fix:</span> ${q.reqs.d}</div>
                    <div class="ref-section"><span class="bold-label">e. REFERENCES:</span><ul>${refs || 'None'}</ul></div>
                    <div style="margin-top:20px; border-top:1px solid #eee; padding-top:15px;">
                        <label style="cursor:pointer; display:flex; align-items:center;">
                            <input type="checkbox" onchange="upd('${q.id}', 'selected', this.checked)" ${res.selected ? 'checked' : ''} style="margin-right:10px; transform:scale(1.2);"> 
                            <strong>Select Question</strong>
                        </label>
                        <div id="carea-${q.id}" class="${res.selected ? '' : 'hidden'}" style="margin-top:15px;">
                            <div style="margin-bottom:12px; padding-left:25px;">
                                <label style="cursor:pointer; display:flex; align-items:center; color:#e6a23c;">
                                    <input type="checkbox" onchange="upd('${q.id}', 'corrected', this.checked)" ${res.corrected ? 'checked' : ''} style="margin-right:10px; transform:scale(1.2);"> 
                                    <strong>Corrected</strong>
                                </label>
                            </div>
                            <div class="bold-label" style="padding-left:2px;">Notes:</div>
                            <textarea class="notes-area" placeholder="Enter observations or corrective actions taken..." oninput="upd('${q.id}', 'notes', this.value)">${res.notes || ""}</textarea>
                        </div>
                    </div>`;
                container.appendChild(div);
            });
            container.scrollTop = 0;
        }

        function upd(id, key, val) {
            if (!globalState.results[id]) globalState.results[id] = {selected:false, corrected:false, notes:""};
            globalState.results[id][key] = val;
            if (key === 'selected') {
                const area = document.getElementById(`carea-${id}`);
                if (area) area.classList.toggle('hidden', !val);
                if (globalState.isFiltered) { renderMenu(); renderSection(); }
            }
        }

        function toggleFilter() {
            globalState.isFiltered = !globalState.isFiltered;
            document.getElementById('filterBtn').innerText = globalState.isFiltered ? "Unfilter" : "Filter Selected";
            renderMenu(); renderSection();
        }

        function saveJSON() {
            const blob = new Blob([JSON.stringify(globalState, null, 2)], {type:'application/json'});
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = (globalState.company || "audit") + ".json";
            a.click();
        }

        function loadJSON(e) {
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (event) => {
                const loaded = JSON.parse(event.target.result);
                globalState.company = loaded.company || "";
                globalState.results = loaded.results || {};
                globalState.isFiltered = loaded.isFiltered || false;
                globalState.currentSectionIdx = loaded.currentSectionIdx || 0;
                document.getElementById('companyName').value = globalState.company;
                document.getElementById('filterBtn').innerText = globalState.isFiltered ? "Unfilter" : "Filter Selected";
                renderMenu(); renderSection();
            };
            reader.readAsText(file);
            e.target.value = ""; 
        }
        window.onload = init;
    </script>
</body>
</html>"""

def main():
    args = get_args()
    out = args.output if args.output else args.input.rsplit('.', 1)[0] + ".html"
    if not out.endswith(".html"): out += ".html"
    if os.path.exists(out) and input(f"Overwrite '{out}'? (y/n): ").lower() != 'y': return
    data = parse_text(args.input)
    json_str = json.dumps(data).replace("\\", "\\\\").replace("'", "\\'")
    with open(out, "w", encoding='utf-8') as f:
        f.write(HTML_TEMPLATE.replace("JSON_DATA_HERE", json_str))
    print(f"Success: {out}")
    
if __name__ == "__main__":
    main()
