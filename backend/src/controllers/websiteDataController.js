import WebsiteData from "../../models/websitedata.js"; // go up 2 levels from src/controllers


/**
 * Controller to insert a chunk of website data
 */
export const createWebsiteData = async (req, res) => {
  try {
    const { website_id, website_link, plain_text, embedding } = req.body;

    // Basic validation
    if (!website_id || !website_link || !plain_text || !embedding) {
      return res.status(400).json({ error: "Missing required fields" });
    }

    // Insert into DB
    const row = await WebsiteData.create({
      website_id,
      website_link,
      plain_text,
      embedding,
    });

    return res.status(201).json({ message: "Chunk inserted successfully", row });
  } catch (err) {
    console.error("Error in createWebsiteData:", err);
    return res.status(500).json({ error: "Internal server error" });
  }
};
