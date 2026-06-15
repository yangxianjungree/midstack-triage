# 架构图

| 文件 | 说明 |
|---|---|
| `architecture-overview.png` | 主架构图（作者原稿） |
| `architecture-overview.svg` | 主图 SVG（内嵌 PNG） |
| `supplements/architecture-phase4-detail.*` | ④ 推理验证展开图 |

## 换主图

替换 `architecture-overview.png` 后重新嵌入 SVG：

```bash
cd docs/concepts/diagrams
python3 - <<'PY'
import base64, re, subprocess
from pathlib import Path
png = Path("architecture-overview.png")
data = png.read_bytes()
out = subprocess.check_output(["file", str(png)], text=True)
m = re.search(r"(\d+) x (\d+)", out)
w, h = m.groups() if m else ("1024", "647")
b64 = base64.b64encode(data).decode()
svg = f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}"><image width="{w}" height="{h}" href="data:image/png;base64,{b64}"/></svg>\n'
Path("architecture-overview.svg").write_text(svg, encoding="utf-8")
print("ok", w, h)
PY
```

## 重渲染 phase4 补充图

```bash
cd docs/concepts/diagrams/supplements
python3 - <<'PY'
import base64, json, urllib.request, pathlib
name = "architecture-phase4-detail"
code = pathlib.Path(f"{name}.mmd").read_text(encoding="utf-8")
b64 = base64.urlsafe_b64encode(json.dumps({"code": code, "mermaid": {"theme": "base"}}).encode()).decode().rstrip("=")
for ext, url in [
    ("png", f"https://mermaid.ink/img/{b64}?type=png&width=2200&bgColor=FFFFFF"),
    ("svg", f"https://mermaid.ink/svg/{b64}?bgColor=FFFFFF"),
]:
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
    pathlib.Path(f"{name}.{ext}").write_bytes(urllib.request.urlopen(req, timeout=90).read())
    print("ok", name + "." + ext)
PY
```
