import WebsiteData from "../../models/websitedata.js";
import sequelize from "../../config/db.js";


export const createWebsiteData = async (req, res) => {
  try {
    const { website_id, website_link, plain_text, embedding } = req.body;

    // ── Validation ─────────────────────────────────────────────────────────
    if (!website_id || !website_link || !plain_text || !embedding) {
      return res.status(400).json({ error: "Missing required fields" });
    }

    if (!Array.isArray(embedding)) {
      return res.status(400).json({ error: "embedding must be an array" });
    }

    if (embedding.length !== 1024) {
      return res.status(400).json({
        error: `embedding must have 1024 dimensions, got ${embedding.length}`
      });
    }

    // ── Convert JS array → pgvector string format ──────────────────────────
    // pgvector expects: '[0.123, 0.456, ...]' as a string with ::vector cast
    const embeddingStr = `[${embedding.join(",")}]`;

    // ── Raw INSERT with ::vector cast ──────────────────────────────────────
    // Using raw query because Sequelize ORM cannot auto-serialize vector type.
    const [results] = await sequelize.query(
      `INSERT INTO "WebsiteData" (website_id, website_link, plain_text, embedding, "createdAt", "updatedAt")
       VALUES (:website_id, :website_link, :plain_text, :embedding::vector, NOW(), NOW())
       RETURNING id, website_id, website_link`,
      {
        replacements: {
          website_id,
          website_link,
          plain_text,
          embedding: embeddingStr,
        },
      }
    );

    return res.status(201).json({
      message: "Chunk inserted successfully",
      row: results[0]
    });

  } catch (err) {
    console.error("❌ Error in createWebsiteData:", err.message);
    return res.status(500).json({ error: "Internal server error" });
  }
};

/**
 * Controller to fetch all website data chunks.
 * Used by queryController to score chunks via cosine similarity.
 */
export const getAllWebsiteData = async (req, res) => {
  try {
    const rows = await WebsiteData.findAll();
    return res.status(200).json(rows);
  } catch (err) {
    console.error("❌ Error in getAllWebsiteData:", err.message);
    return res.status(500).json({ error: "Internal server error" });
  }
};