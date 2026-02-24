// exportMcqsToExcel.js
// ─────────────────────────────────────────────────────────────────
// First run:  npm install exceljs
// Then call:  exportMcqsToExcel()   ← call this whenever you want
// Or run directly: node exportMcqsToExcel.js
// ─────────────────────────────────────────────────────────────────

import ExcelJS  from "exceljs";
import fs       from "fs";
import path     from "path";
import { fileURLToPath } from "url";

// At the top of exportMcqsToExcel.js
const __filename = fileURLToPath(import.meta.url);
const __dirname  = path.dirname(__filename);

const MCQS_FILE  = path.join(__dirname, "Mcqs.json"); // ← must be same folder

export const exportMcqsToExcel = async () => {
  // ── Read Mcqs.json ───────────────────────────────────────────────────────
  if (!fs.existsSync(MCQS_FILE)) {
    console.warn("⚠️  Mcqs.json not found — nothing to export.");
    return null;
  }

  const data = JSON.parse(fs.readFileSync(MCQS_FILE, "utf8"));
  const mcqs = data.mcqs || [];

  if (mcqs.length === 0) {
    console.warn("⚠️  No MCQs in Mcqs.json — nothing to export.");
    return null;
  }

  // ── Create workbook ──────────────────────────────────────────────────────
  const wb = new ExcelJS.Workbook();
  const ws = wb.addWorksheet("MCQs");

  // ── Column definitions ───────────────────────────────────────────────────
  ws.columns = [
    { header: "#",        key: "no",       width: 5  },
    { header: "Question", key: "question", width: 55 },
    { header: "Option A", key: "optA",     width: 25 },
    { header: "Option B", key: "optB",     width: 25 },
    { header: "Option C", key: "optC",     width: 25 },
    { header: "Option D", key: "optD",     width: 25 },
    { header: "Answer",   key: "answer",   width: 10 },
    { header: "Assessment", key: "assessment", width: 35 },
  ];

  // ── Style header row ─────────────────────────────────────────────────────
  const headerRow = ws.getRow(1);
  headerRow.height = 30;
  headerRow.eachCell((cell) => {
    cell.font      = { name: "Arial", bold: true, color: { argb: "FFFFFFFF" }, size: 12 };
    cell.fill      = { type: "pattern", pattern: "solid", fgColor: { argb: "FF3B4FA8" } };
    cell.alignment = { horizontal: "center", vertical: "middle", wrapText: true };
    cell.border    = {
      top   : { style: "thin" }, bottom: { style: "thin" },
      left  : { style: "thin" }, right : { style: "thin" },
    };
  });

  // ── Add MCQ rows ─────────────────────────────────────────────────────────
  mcqs.forEach((mcq, index) => {
    const row = ws.addRow({
      no      : index + 1,
      question: mcq.question          || "",
      optA    : mcq.options?.A        || "",
      optB    : mcq.options?.B        || "",
      optC    : mcq.options?.C        || "",
      optD    : mcq.options?.D        || "",
      answer  : mcq.answer            || "",
      assessment: mcq.assessment      || "",
    });

    row.height = 40;
    const isOdd = (index + 1) % 2 !== 0;

    row.eachCell((cell, colNumber) => {
      // Alternating row background
      cell.fill = {
        type    : "pattern",
        pattern : "solid",
        fgColor : { argb: isOdd ? "FFF0F4FF" : "FFFFFFFF" },
      };

      cell.border = {
        top   : { style: "thin" }, bottom: { style: "thin" },
        left  : { style: "thin" }, right : { style: "thin" },
      };

      cell.alignment = {
        horizontal: colNumber === 1 || colNumber === 7 ? "center" : "left",
        vertical  : "middle",
        wrapText  : true,
      };

      // Answer column — green bold
      if (colNumber === 7) {
        cell.font = { name: "Arial", bold: true, color: { argb: "FF1A7A3C" }, size: 11 };
      } else {
        cell.font = { name: "Arial", size: 11 };
      }
    });
  });

  // ── Freeze header row ─────────────────────────────────────────────────────
  ws.views = [{ state: "frozen", ySplit: 1 }];

  // ── Save file as MCQS.YYYY-MM-DD.xlsx ────────────────────────────────────
  const today    = new Date().toISOString().slice(0, 10);   // e.g. 2026-02-23
  const filename = `MCQS.${today}.xlsx`;
  const outPath  = path.join(__dirname, filename);

  await wb.xlsx.writeFile(outPath);
  console.log(`✅ Excel exported: ${filename}  (${mcqs.length} MCQs)`);
  return outPath;
};

