#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""confirm.py —— 网页点选收集输入与原料，结果写成 JSON。

【用途】
    开工前把「用户说不清、但有穷举可能」的输入一次问完，同时收原料文件。
    表单只收事实与选项；需要判断的部分仍回对话。

【用法】
    python scripts/confirm.py --spec spec.json --out answers.json \
        [--intake 原料/] [--port 0] [--timeout 900]

    起服务后打印地址（含随机 token）。用户提交即写 `answers.json`、关服。
    超时则不写文件、关服退出，调用方回落到对话提问。
    给了 `--intake` 时，页面多出拖拽区；文件直接落进该目录，目录不存在则自动建。

【spec 格式】
    {
      "title": "页标题",
      "intro": "一句话说明",
      "questions": [
        {"id": "occasion", "type": "radio", "label": "场合", "required": true,
         "options": [{"value": "组会汇报", "hint": "每周例会"}]},
        {"id": "audience", "type": "multi", "label": "听众", "options": [...]},
        {"id": "notes", "type": "text", "label": "其他要求", "placeholder": "可留空"}
      ]
    }

    题型三种：`radio` / `multi` / `text`。`required` 为真时，未答不能提交。

【原料上传】
    POST /upload   文件名走请求头 `X-Filename`（URL 编码），请求体是文件原始字节
    POST /delete   JSON `{"k": token, "name": "文件名"}`
    GET  /files    列出当前 intake 目录里的文件

    文件名只取 basename，控制字符与 `<>:"|?*` 换成下划线，以点开头的被清掉。
    重名自动加 `-1`、`-2`。单文件上限 100 MB。删除只允许在 intake 目录内。

【退出码】
    0 已提交 · 2 超时未提交 · 3 spec 或端口有问题

【边界】
    · 只绑 127.0.0.1；地址带一次性随机 token，缺 token 返回 403
    · 不做鉴权、不存历史、不联网
    · 请求体必须是 UTF-8 的 JSON（上传接口除外，那里是原始字节）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

MAX_BYTES = 100 * 1024 * 1024
MANIFEST = "清单.json"
_BAD_CHARS = re.compile(r'[\x00-\x1f<>:"|?*]')

PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--ink:#1b1b1f;--mute:#6b6b76;--line:#e3e3e8;--accent:#2c5fd4;--bg:#f6f7f9}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font:15px/1.6 -apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:32px 20px 96px}
h1{font-size:22px;margin:0 0 6px}
.intro{color:var(--mute);margin:0 0 28px}
.q{background:#fff;border:1px solid var(--line);border-radius:12px;padding:18px 18px 14px;margin:0 0 14px}
.q h2{font-size:15px;margin:0 0 4px;font-weight:600}
.effect{color:var(--mute);font-size:13px;margin:0 0 12px;line-height:1.5}
.opts{display:grid;gap:8px}
label.opt{display:flex;gap:10px;align-items:flex-start;padding:10px 12px;border:1px solid var(--line);
 border-radius:9px;cursor:pointer;transition:.12s}
label.opt:hover{border-color:#c3cee6}
label.opt input{margin:3px 0 0}
label.opt.sel{border-color:var(--accent);background:#f3f6ff}
.val{font-weight:500}
.hint{color:var(--mute);font-size:13px;margin-top:2px}
input[type=text]{width:100%;padding:9px 11px;border:1px solid var(--line);border-radius:9px;font:inherit}
.drop{background:#fff;border:2px dashed #c9d2e4;border-radius:12px;padding:26px 18px;
 text-align:center;color:var(--mute);cursor:pointer;transition:.15s;margin:0 0 12px}
.drop.hot{border-color:var(--accent);background:#f3f6ff;color:var(--accent)}
.drop b{color:var(--ink);font-weight:600}
.files{list-style:none;padding:0;margin:0 0 14px}
.files li{display:flex;align-items:center;gap:10px;background:#fff;border:1px solid var(--line);
 border-radius:9px;padding:9px 12px;margin-bottom:6px;font-size:14px}
.files .sz{color:var(--mute);margin-left:auto;font-variant-numeric:tabular-nums}
.files button{background:none;border:0;color:#b3261e;cursor:pointer;font-size:16px;padding:0 4px}
.note{color:var(--mute);font-size:13px;margin:0 0 18px}
.bar{position:fixed;left:0;right:0;bottom:0;background:#fff;border-top:1px solid var(--line);
 padding:12px 20px;display:flex;gap:12px;align-items:center;justify-content:center}
button.main{background:var(--accent);color:#fff;border:0;border-radius:9px;padding:11px 26px;
 font:inherit;font-weight:600;cursor:pointer}
button.main:disabled{opacity:.45;cursor:default}
.ok{color:#1a7f4b;font-weight:600}
code{background:#eef1f6;border-radius:5px;padding:1px 6px;font-size:13px}
</style></head>
<body><div class="wrap">
<h1>__TITLE__</h1><p class="intro">__INTRO__</p>
<div id="qs"></div>
__DROP__
</div>
<div class="bar"><span id="msg"></span><button class="main" id="go">提交确认</button></div>
<script>
const SPEC = __SPEC__;
const INTAKE = __INTAKE__;
const TOKEN = new URLSearchParams(location.search).get('k');
const ANS = {};
const box = document.getElementById('qs');
SPEC.questions.forEach(function(q){
  const d = document.createElement('div'); d.className='q';
  const h = document.createElement('h2'); h.textContent = q.label; d.appendChild(h);
  if (q.effect) {
    const e = document.createElement('div'); e.className='effect'; e.textContent = q.effect;
    d.appendChild(e);
  }
  if (q.type === 'text') {
    const t = document.createElement('input');
    t.type = 'text'; t.placeholder = q.placeholder || '';
    ANS[q.id] = '';
    t.addEventListener('input', function(){ ANS[q.id] = t.value; });
    d.appendChild(t);
  } else {
    const wrap = document.createElement('div'); wrap.className='opts';
    q.options.forEach(function(o){
      const l = document.createElement('label'); l.className='opt';
      const i = document.createElement('input');
      i.type = q.type === 'multi' ? 'checkbox' : 'radio';
      i.name = q.id; i.value = o.value;
      i.addEventListener('change', function(){
        if (q.type === 'multi') {
          ANS[q.id] = Array.from(document.querySelectorAll('input[name="'+q.id+'"]:checked')).map(x=>x.value);
          i.parentElement.classList.toggle('sel', i.checked);
        } else {
          ANS[q.id] = o.value;
          Array.from(document.querySelectorAll('input[name="'+q.id+'"]')).forEach(function(x){
            x.parentElement.classList.toggle('sel', x.checked);
          });
        }
        refresh();
      });
      const col = document.createElement('div');
      const v = document.createElement('div'); v.className='val'; v.textContent = o.value;
      col.appendChild(v);
      if (o.hint) { const hh = document.createElement('div'); hh.className='hint'; hh.textContent = o.hint; col.appendChild(hh); }
      l.appendChild(i); l.appendChild(col); wrap.appendChild(l);
    });
    d.appendChild(wrap);
  }
  box.appendChild(d);
});

function fmt(n){
  if (n < 1024) return n + ' B';
  if (n < 1024*1024) return (n/1024).toFixed(0) + ' KB';
  return (n/1024/1024).toFixed(1) + ' MB';
}
function addRow(name, size){
  const ul = document.getElementById('files'); if (!ul) return;
  const li = document.createElement('li');
  const a = document.createElement('span'); a.textContent = name;
  const s = document.createElement('span'); s.className='sz'; s.textContent = fmt(size);
  const x = document.createElement('button'); x.textContent='×'; x.title='删除';
  x.addEventListener('click', function(){
    fetch('/delete', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({k: TOKEN, name: name})}).then(function(){ li.remove(); });
  });
  li.appendChild(a); li.appendChild(s); li.appendChild(x); ul.appendChild(li);
}
function upload(file){
  const note = document.getElementById('dropnote');
  if (note) note.textContent = '正在上传：' + file.name;
  fetch('/upload', {method:'POST', headers:{'X-Filename': encodeURIComponent(file.name)},
    body: file})
   .then(function(r){ return r.json().then(function(j){ return {s:r.status, j:j}; }); })
   .then(function(res){
     if (res.s === 200) { addRow(res.j.saved, res.j.size); if (note) note.textContent = ''; }
     else { if (note) note.textContent = '上传失败：' + (res.j.error || res.s); }
   })
   .catch(function(){ if (note) note.textContent = '上传失败'; });
}
const drop = document.getElementById('drop');
const pick = document.getElementById('pick');
if (drop) {
  drop.addEventListener('click', function(){ pick.click(); });
  ['dragenter','dragover'].forEach(function(e){
    drop.addEventListener(e, function(ev){ ev.preventDefault(); drop.classList.add('hot'); });
  });
  ['dragleave','drop'].forEach(function(e){
    drop.addEventListener(e, function(ev){ ev.preventDefault(); drop.classList.remove('hot'); });
  });
  drop.addEventListener('drop', function(ev){
    Array.from(ev.dataTransfer.files).forEach(upload);
  });
  pick.addEventListener('change', function(){
    Array.from(pick.files).forEach(upload); pick.value = '';
  });
  fetch('/files?k=' + encodeURIComponent(TOKEN)).then(function(r){ return r.json(); }).then(function(list){
    if (Array.isArray(list)) list.forEach(function(f){ addRow(f.name, f.size); });
  });
}

function missing(){
  return SPEC.questions.filter(function(q){
    if (!q.required) return false;
    const v = ANS[q.id];
    return v === undefined || v === '' || (Array.isArray(v) && v.length === 0);
  }).map(function(q){ return q.label; });
}
function refresh(){
  const m = missing();
  document.getElementById('go').disabled = m.length > 0;
  document.getElementById('msg').textContent = m.length ? ('以下必填项尚未填写：' + m.join('、')) : '';
}
document.getElementById('go').addEventListener('click', function(){
  if (missing().length) return;
  fetch('/submit', {method:'POST', headers:{'Content-Type':'application/json; charset=utf-8'},
    body: JSON.stringify({k: TOKEN, answers: ANS})})
   .then(function(r){ return r.json(); })
   .then(function(){
     const files = Array.from(document.querySelectorAll('#files li span:first-child')).map(function(x){ return x.textContent; });
     let html = '<h1>确认已提交</h1><p class="intro ok">请返回对话界面，制作将据此继续。</p>';
     if (INTAKE) {
       html += '<p class="note">文件已存至 <code>' + INTAKE + '</code>，共 ' + files.length + ' 项。缺失的材料将在对话中逐项列出。</p>';
     }
     document.querySelector('.wrap').innerHTML = html;
     document.getElementById('go').disabled = true;
     document.getElementById('msg').textContent = '';
   });
});
refresh();
</script></body></html>"""

DROP_HTML = """<div class="drop" id="drop">
  <div><b>将内容稿、图像或表格文件拖入此区域</b></div>
  <div>亦可点击选择文件 · 单一文件上限 100 MB</div>
  <div id="dropnote" class="note" style="margin:8px 0 0"></div>
  <input type="file" id="pick" multiple hidden>
</div>
<ul class="files" id="files"></ul>"""


def validate(spec) -> str | None:
    """返回错误说明；通过则返回 None。"""
    if not isinstance(spec, dict):
        return "spec 必须是对象"
    if not isinstance(spec.get("questions"), list) or not spec["questions"]:
        return "spec 缺 questions"
    ids = set()
    for q in spec["questions"]:
        for key in ("id", "type", "label"):
            if key not in q:
                return f"问题缺 {key}：{q}"
        if q["id"] in ids:
            return f"问题 id 重复：{q['id']}"
        ids.add(q["id"])
        if q["type"] not in ("radio", "multi", "text"):
            return f"未知题型 {q['type']}（{q['id']}）"
        if q["type"] in ("radio", "multi"):
            if not isinstance(q.get("options"), list) or not q["options"]:
                return f"{q['id']} 缺 options"
            for o in q["options"]:
                if "value" not in o:
                    return f"{q['id']} 的选项缺 value"
    return None


def safe_name(raw: str) -> str:
    """只留 basename，清掉控制字符与 Windows 非法字符，去掉开头的点。"""
    name = urllib.parse.unquote(raw or "")
    name = os.path.basename(name.replace("\\", "/"))
    name = _BAD_CHARS.sub("_", name).strip().lstrip(".")
    return name[:120]


def unique_path(directory: str, name: str) -> str:
    stem, ext = os.path.splitext(name)
    cand = os.path.join(directory, name)
    i = 1
    while os.path.exists(cand):
        cand = os.path.join(directory, f"{stem}-{i}{ext}")
        i += 1
    return cand


class ConfirmServer:
    """一次确认会话：一个 spec，一份答案，可选一个原料目录。"""

    def __init__(self, spec: dict, out: str, port: int = 0, intake: str | None = None):
        self.spec = spec
        self.out = os.path.abspath(out)
        self.intake = os.path.abspath(intake) if intake else None
        if self.intake:
            os.makedirs(self.intake, exist_ok=True)
        self.token = secrets.token_urlsafe(12)
        self.done = threading.Event()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), _handler_for(self))
        self._thread = None

    @property
    def port(self) -> int:
        return self.httpd.server_address[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/?k={self.token}"

    def files(self) -> list:
        if not self.intake or not os.path.isdir(self.intake):
            return []
        out = []
        for n in sorted(os.listdir(self.intake)):
            p = os.path.join(self.intake, n)
            if os.path.isfile(p) and n != MANIFEST:
                out.append({"name": n, "size": os.path.getsize(p)})
        return out

    def write_manifest(self) -> None:
        if not self.intake:
            return
        with open(os.path.join(self.intake, MANIFEST), "w", encoding="utf-8") as f:
            json.dump(self.files(), f, ensure_ascii=False, indent=2)

    def start(self) -> None:
        self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self._thread.start()

    def wait(self, timeout: float) -> bool:
        return self.done.wait(timeout=timeout)

    def shutdown(self) -> None:
        self.httpd.shutdown()


def _handler_for(srv: ConfirmServer):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="text/html; charset=utf-8"):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj, ensure_ascii=False), "application/json")

        def _authed(self, given) -> bool:
            return given == srv.token

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/files":
                if not self._authed(parse_qs(u.query).get("k", [""])[0]):
                    return self._json(403, {"error": "token 不对"})
                return self._json(200, srv.files())
            if u.path != "/":
                return self._send(404, "not found", "text/plain; charset=utf-8")
            if not self._authed(parse_qs(u.query).get("k", [""])[0]):
                return self._send(403, "token 不对", "text/plain; charset=utf-8")
            page = (PAGE
                    .replace("__TITLE__", srv.spec.get("title", "确认"))
                    .replace("__INTRO__", srv.spec.get("intro", ""))
                    .replace("__DROP__", DROP_HTML if srv.intake else "")
                    .replace("__INTAKE__", json.dumps(srv.intake or "", ensure_ascii=False))
                    .replace("__SPEC__", json.dumps(srv.spec, ensure_ascii=False)))
            self._send(200, page)

        def do_POST(self):
            path = urlparse(self.path).path
            if path == "/upload":
                return self._upload()
            if path == "/delete":
                return self._delete()
            if path == "/submit":
                return self._submit()
            return self._send(404, "not found", "text/plain; charset=utf-8")

        def _upload(self):
            if not srv.intake:
                return self._json(404, {"error": "未开启原料上传"})
            name = safe_name(self.headers.get("X-Filename", ""))
            if not name:
                return self._json(400, {"error": "文件名为空"})
            n = int(self.headers.get("Content-Length", 0))
            if n > MAX_BYTES:
                return self._json(413, {"error": f"超过 {MAX_BYTES // (1024 * 1024)} MB"})
            data = self.rfile.read(n)
            dest = unique_path(srv.intake, name)
            with open(dest, "wb") as f:
                f.write(data)
            return self._json(200, {"saved": os.path.basename(dest), "size": len(data)})

        def _delete(self):
            if not srv.intake:
                return self._json(404, {"error": "未开启原料上传"})
            n = int(self.headers.get("Content-Length", 0))
            try:
                payload = json.loads(self.rfile.read(n).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return self._json(400, {"error": "bad json"})
            if not self._authed(payload.get("k")):
                return self._json(403, {"error": "token 不对"})
            name = os.path.basename(payload.get("name", ""))
            target = os.path.join(srv.intake, name)
            if not name or os.path.dirname(os.path.abspath(target)) != srv.intake:
                return self._json(400, {"error": "文件名不合法"})
            if os.path.isfile(target):
                os.remove(target)
            return self._json(200, {"ok": True})

        def _submit(self):
            n = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(n) or b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return self._send(400, "bad json（请求体必须是 UTF-8）",
                                  "text/plain; charset=utf-8")
            if not self._authed(payload.get("k")):
                return self._send(403, "token 不对", "text/plain; charset=utf-8")
            answers = payload.get("answers", {})
            out = {q["id"]: answers.get(q["id"]) for q in srv.spec["questions"]}
            with open(srv.out, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            srv.write_manifest()
            self._send(200, '{"ok":true}', "application/json")
            srv.done.set()

    return Handler


def main() -> int:
    ap = argparse.ArgumentParser(description="网页点选收集输入与原料，结果写 JSON")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--intake", help="原料目录；不给则不显示拖拽区")
    ap.add_argument("--port", type=int, default=0, help="默认 0 = 由系统分配")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()

    with open(a.spec, encoding="utf-8") as f:
        spec = json.load(f)
    err = validate(spec)
    if err:
        print(f"[错误] {err}")
        return 3

    try:
        srv = ConfirmServer(spec, a.out, a.port, a.intake)
    except OSError as e:
        print(f"[错误] 端口 {a.port} 起不来：{e}")
        return 3

    srv.start()
    print(f"[confirm] 打开：{srv.url}")
    print(f"[confirm] 结果写入：{srv.out}")
    if srv.intake:
        print(f"[confirm] 原料目录：{srv.intake}")
    sys.stdout.flush()
    if not a.no_browser:
        try:
            webbrowser.open(srv.url)
        except Exception:
            pass

    ok = srv.wait(a.timeout)
    srv.shutdown()
    if ok:
        print("[confirm] 已提交")
        return 0
    print(f"[confirm] 超时 {a.timeout}s，未提交")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
