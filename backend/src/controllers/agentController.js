import { exec } from "child_process";

export const agentController = async (req, res) => {
  try {
    const { query } = req.body;

    if (!query) {
      return res.status(400).json({ error: "query is required" });
    }

    console.log("🤖 Agent received query:", query);

    // Call your python scraper
    exec(`python main.py "${query}"`, (error, stdout, stderr) => {
      if (error) {
        console.error("Python error:", error);
        return res.status(500).json({ error: "Agent failed to scrape" });
      }

      console.log("Scraper output:", stdout);
      return res.json({ message: "Agent scraping completed" });
    });

  } catch (err) {
    console.error("agentController error:", err);
    res.status(500).json({ error: "Agent internal error" });
  }
};
