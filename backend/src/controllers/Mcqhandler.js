import fs   from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname  = path.dirname(__filename);

const MCQS_FILE = path.join(__dirname, "Mcqs.json");

export const saveMcqsToFile = (mcqs, sessionId, originalQuery) => {
  let existing = { total: 0, mcqs: [] };

  if (fs.existsSync(MCQS_FILE)) {
    try {
      existing = JSON.parse(fs.readFileSync(MCQS_FILE, "utf8"));
    } catch (e) {
      console.error("⚠️ Could not parse Mcqs.json — starting fresh:", e.message);
    }
  }

  const nextId = (existing.total || 0) + 1;

  const enriched = mcqs.map((mcq, idx) => ({
    id        : nextId + idx,
    session_id: sessionId,
    query     : originalQuery,
    question  : mcq.question        || "",
    options   : {
      A: mcq.options?.A || null,
      B: mcq.options?.B || null,
      C: mcq.options?.C || null,
      D: mcq.options?.D || null,
    },
    answer    : mcq.answer          || null,
    assessment: mcq.assessment      || null,
    saved_at  : new Date().toISOString(),
  }));

  existing.mcqs  = [...(existing.mcqs || []), ...enriched];
  existing.total = existing.mcqs.length;

  fs.writeFileSync(MCQS_FILE, JSON.stringify(existing, null, 2), "utf8");
  console.log(`📝 Saved ${enriched.length} MCQ(s) → Mcqs.json (total: ${existing.total})`);
};