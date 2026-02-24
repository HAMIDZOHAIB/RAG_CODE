import ExcelJS  from "exceljs";
import fs        from "fs";
import path      from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname  = path.dirname(__filename);

const SJT_FILE = path.join(__dirname, "Sjt.json");

export const exportSjtToExcel = async () => {
  if (!fs.existsSync(SJT_FILE)) {
    console.warn("⚠️ Sjt.json not found — nothing to export.");
    return null;
  }

  const raw = fs.readFileSync(SJT_FILE, "utf8").trim();
  if (!raw) {
    console.warn("⚠️ Sjt.json is empty.");
    return null;
  }

  const data     = JSON.parse(raw);
  const sjtItems = data.sjt || [];

  if (sjtItems.length === 0) {
    console.warn("⚠️ No SJT items found.");
    return null;
  }

  const wb = new ExcelJS.Workbook();
  const ws = wb.addWorksheet("SJT");

  // ── Column definitions ───────────────────────────────────────────────────
  ws.columns = [
    { header: "#",            key: "no",      width: 5  },
    { header: "Scenario",     key: "scenario", width: 50 },
    { header: "Option A",     key: "optA",     width: 25 },
    { header: "Option B",     key: "optB",     width: 25 },
    { header: "Option C",     key: "optC",     width: 25 },
    { header: "Option D",     key: "optD",     width: 25 },
    { header: "Assessment A", key: "assA",     width: 35 },
    { header: "Assessment B", key: "assB",     width: 35 },
    { header: "Assessment C", key: "assC",     width: 35 },
    { header: "Assessment D", key: "assD",     width: 35 },
  ];

  // ── Style header row ─────────────────────────────────────────────────────
  const headerRow = ws.getRow(1);
  headerRow.height = 30;
  headerRow.eachCell((cell) => {
    cell.font      = { name: "Arial", bold: true, color: { argb: "FFFFFFFF" }, size: 12 };
    cell.fill      = { type: "pattern", pattern: "solid", fgColor: { argb: "FF6B21A8" } }; // purple for SJT
    cell.alignment = { horizontal: "center", vertical: "middle", wrapText: true };
    cell.border    = {
      top   : { style: "thin" }, bottom: { style: "thin" },
      left  : { style: "thin" }, right  : { style: "thin" },
    };
  });

  // ── Assessment column header — different color ────────────────────────────
  ["G", "H", "I", "J"].forEach(col => {
    const cell = ws.getCell(`${col}1`);
    cell.fill  = { type: "pattern", pattern: "solid", fgColor: { argb: "FF1A7A3C" } }; // green for assessment
  });

  // ── Add SJT rows ─────────────────────────────────────────────────────────
  sjtItems.forEach((item, index) => {
    const row    = ws.addRow({
      no      : index + 1,
      scenario: item.scenario          || "",
      optA    : item.options?.A        || "",
      optB    : item.options?.B        || "",
      optC    : item.options?.C        || "",
      optD    : item.options?.D        || "",
      assA    : item.assessment?.A     || "",
      assB    : item.assessment?.B     || "",
      assC    : item.assessment?.C     || "",
      assD    : item.assessment?.D     || "",
    });

    row.height   = 60;
    const isOdd  = (index + 1) % 2 !== 0;

    row.eachCell((cell, colNumber) => {
      cell.fill = {
        type    : "pattern",
        pattern : "solid",
        fgColor : { argb: isOdd ? "FFF5F0FF" : "FFFFFFFF" }, // light purple tint for odd rows
      };

      cell.border = {
        top   : { style: "thin" }, bottom: { style: "thin" },
        left  : { style: "thin" }, right  : { style: "thin" },
      };

      cell.alignment = {
        horizontal: colNumber === 1 ? "center" : "left",
        vertical  : "middle",
        wrapText  : true,
      };

      // Assessment columns (7-10) — green italic font
      if (colNumber >= 7) {
        cell.font = { name: "Arial", italic: true, color: { argb: "FF1A7A3C" }, size: 10 };
      } else {
        cell.font = { name: "Arial", size: 11 };
      }
    });
  });

  // ── Freeze header row ─────────────────────────────────────────────────────
  ws.views = [{ state: "frozen", ySplit: 1 }];

  // ── Save file ─────────────────────────────────────────────────────────────
  const today    = new Date().toISOString().slice(0, 10);
  const filename = `SJT.${today}.xlsx`;
  const outPath  = path.join(__dirname, filename);

  await wb.xlsx.writeFile(outPath);
  console.log(`✅ SJT Excel exported: ${filename} (${sjtItems.length} items)`);
  return outPath;
};