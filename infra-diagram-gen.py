#!/usr/bin/env python3
"""infra-diagram-gen v1.0 - Generate architecture diagrams from IaC files. Zero dependencies."""
import sys, os, re

def parse_compose(path):
    lines = open(path, encoding="utf-8").read().split("\n")
    services = {}
    volumes = []
    deps = {}
    in_svc = False
    in_vol = False
    current_svc = None
    in_depends = False
    for raw in lines:
        stripped = raw.strip()
        if stripped == "services:":
            in_svc = True; in_vol = False; current_svc = None; continue
        if stripped == "volumes:":
            in_vol = True; in_svc = False; current_svc = None; continue
        if stripped and not raw[0].isspace() and ":" in stripped:
            in_svc = False; in_vol = False; current_svc = None; in_depends = False; continue
        if in_svc:
            if raw.startswith("  ") and not raw.startswith("   ") and stripped.endswith(":"):
                current_svc = stripped[:-1]
                services[current_svc] = current_svc
                in_depends = False
            elif current_svc and stripped.startswith("image:"):
                img = stripped.replace("image:", "").strip().strip("'\"")
                services[current_svc] = img.split("/")[-1].split(":")[0]
            elif current_svc and "depends_on" in stripped:
                in_depends = True
                deps[current_svc] = []
            elif current_svc and in_depends and stripped.startswith("- "):
                dep = stripped.lstrip("- ").strip()
                if dep != current_svc:
                    deps[current_svc].append(dep)
            elif stripped and not stripped.startswith("- "):
                in_depends = False
        if in_vol:
            if raw.startswith("  ") and not raw.startswith("   ") and stripped.endswith(":"):
                volumes.append(stripped[:-1])
    nodes = []
    for svc in services:
        nodes.append((svc, services[svc], "service"))
    for vol in volumes:
        nodes.append((vol, "📦 " + vol, "volume"))
    edges = []
    for svc, dep_list in deps.items():
        for d in dep_list:
            if d in services:
                edges.append((svc, d))
    return nodes, edges

def parse_tf(path):
    content = open(path, encoding="utf-8").read()
    resources = re.findall(r'resource\s+"([^"]+)"\s+"([^"]+)"', content)
    nodes = []
    for rtype, rname in resources:
        shape = "volume" if any(k in rtype for k in ["s3", "rds", "db", "storage"]) else "service"
        nodes.append((rtype + "." + rname, rtype + "\n" + rname, shape))
    edges = []
    for rtype, rname in resources:
        pattern = re.compile('resource\\s+"' + re.escape(rtype) + '"\\s+"' + re.escape(rname) + '"\\s*\\{(.*?)(?=\\nresource|\\Z)', re.S)
        block = pattern.search(content)
        if block:
            refs = re.findall(r'(?:aws|google|azurerm)\.(\w+)\.(\w+)', block.group(1))
            for rt, rn in refs:
                ref_id = rt + "." + rn
                self_id = rtype + "." + rname
                if ref_id != self_id and any(n[0] == ref_id for n in nodes):
                    edges.append((self_id, ref_id))
    return nodes, edges

def gen_mermaid(nodes, edges):
    out = ["graph TB", ""]
    ids = set()
    for nid, label, shape in nodes:
        sid = re.sub(r'[^a-zA-Z0-9_]', '_', nid)
        ids.add(nid)
        if shape == "volume":
            out.append('    ' + sid + '[("' + label + '")]')
        else:
            out.append('    ' + sid + '["' + label + '"]')
    out.append("")
    for a, b in edges:
        if a in ids and b in ids:
            sa = re.sub(r'[^a-zA-Z0-9_]', '_', a)
            sb = re.sub(r'[^a-zA-Z0-9_]', '_', b)
            out.append('    ' + sa + ' --> ' + sb)
    return "\n".join(out)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 infra-diagram-gen.py <docker-compose.yml | main.tf>")
        sys.exit(1)
    path = sys.argv[1]
    if not os.path.exists(path):
        sys.exit("File not found: " + path)
    if path.endswith(".tf"):
        nodes, edges = parse_tf(path)
    else:
        nodes, edges = parse_compose(path)
    if not nodes:
        sys.exit("No resources found in file")
    diagram = gen_mermaid(nodes, edges)
    out_file = os.path.splitext(path)[0] + "-diagram.md"
    md = "# Architecture Diagram\n\n> Generated from `" + path + "` by [infra-diagram-gen](https://github.com/tomlen045/infra-diagram-gen)\n\n```mermaid\n" + diagram + "\n```\n\nRender at [mermaid.live](https://mermaid.live) or paste in any Markdown file.\n"
    open(out_file, "w", encoding="utf-8").write(md)
    print("✅ Generated: " + out_file)
    print("")
    print(diagram)

if __name__ == "__main__":
    main()
