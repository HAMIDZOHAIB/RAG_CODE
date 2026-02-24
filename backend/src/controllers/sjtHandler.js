import fs   from "fs";
import path  from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname  = path.dirname(__filename);

const SJT_FILE = path.join(__dirname, "Sjt.json");

/**
 * Saves SJT questions to Sjt.json.
 * Called ONLY when LLM response contains SJT content.
 *
 * Each SJT item structure:
 * {
 *   scenario   : "You are working on a team project...",
 *   options    : { A: "...", B: "...", C: "...", D: "..." },
 *   assessment : { A: "...", B: "...", C: "...", D: "..." }
 * }
 */
export const saveSjtToFile = (sjtItems, sessionId, originalQuery) => {
  let existing = { total: 0, sjt: [] };

  try {
    if (fs.existsSync(SJT_FILE)) {
      const raw = fs.readFileSync(SJT_FILE, "utf8").trim();
      if (raw) existing = JSON.parse(raw);
    }
  } catch (e) {
    console.warn("⚠️ Sjt.json unreadable, starting fresh:", e.message);
    existing = { total: 0, sjt: [] };
  }

  const nextId   = (existing.total || 0) + 1;

  const enriched = sjtItems.map((item, idx) => ({
    id         : nextId + idx,
    session_id : sessionId,
    query      : originalQuery,
    scenario   : item.scenario              || "",
    options    : {
      A: item.options?.A || null,
      B: item.options?.B || null,
      C: item.options?.C || null,
      D: item.options?.D || null,
    },
    assessment : {
      A: item.assessment?.A || null,
      B: item.assessment?.B || null,
      C: item.assessment?.C || null,
      D: item.assessment?.D || null,
    },
    saved_at   : new Date().toISOString(),
  }));

  existing.sjt   = [...(existing.sjt || []), ...enriched];
  existing.total = existing.sjt.length;

  fs.writeFileSync(SJT_FILE, JSON.stringify(existing, null, 2), "utf8");
  console.log(`📝 Saved ${enriched.length} SJT item(s) → Sjt.json (total: ${existing.total})`);
};