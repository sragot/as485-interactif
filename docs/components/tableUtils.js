// tableUtils.js — colonnes redimensionnables + bouton téléchargement CSV

export function tableWithTools(tableElement, data, filename = "données.csv") {
  addResizableColumns(tableElement);

  const container = document.createElement("div");

  if (data && data.length > 0) {
    container.appendChild(makeCsvButton(data, filename));
  }
  container.appendChild(tableElement);

  return container;
}

function makeCsvButton(data, filename) {
  const cols = Object.keys(data[0]);
  const header = cols.map(c => `"${c.replace(/"/g, '""')}"`).join(",");
  const body = data
    .map(row => cols.map(c => `"${String(row[c] ?? "").replace(/"/g, '""')}"`).join(","))
    .join("\r\n");
  const csv = "﻿" + header + "\r\n" + body;

  const btn = document.createElement("button");
  btn.textContent = "⬇ Télécharger CSV";
  Object.assign(btn.style, {
    display: "inline-block",
    margin: "4px 0 6px 0",
    padding: "4px 12px",
    fontSize: "13px",
    cursor: "pointer",
    border: "1px solid #bbb",
    borderRadius: "4px",
    background: "var(--theme-background-alt, #f5f5f5)",
    color: "var(--theme-foreground, #333)",
  });

  btn.addEventListener("click", () => {
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.style.display = "none";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  });

  return btn;
}

function addResizableColumns(tableEl) {
  const table =
    tableEl instanceof HTMLTableElement ? tableEl : tableEl.querySelector("table");
  if (!table) return;

  table.style.tableLayout = "fixed";

  for (const th of table.querySelectorAll("thead th")) {
    th.style.position = "relative";
    th.style.overflow = "hidden";
    th.style.whiteSpace = "nowrap";

    const handle = document.createElement("div");
    Object.assign(handle.style, {
      position: "absolute",
      right: "0",
      top: "0",
      width: "5px",
      height: "100%",
      cursor: "col-resize",
      userSelect: "none",
    });

    handle.addEventListener("mousedown", (e) => {
      e.preventDefault();
      const x0 = e.pageX;
      const w0 = th.getBoundingClientRect().width;
      const onMove = (e) => {
        th.style.width = Math.max(40, w0 + e.pageX - x0) + "px";
      };
      const onUp = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });

    th.appendChild(handle);
  }
}
