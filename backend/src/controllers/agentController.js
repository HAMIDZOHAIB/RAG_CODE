import axios from "axios";

export const agentController = async (req, res) => {
  try {
    const { query } = req.body;
    if (!query) {
      return res.status(400).json({ error: "query is required" });
    }

    console.log("🤖 AgentController received query:", query);

    // Call FastAPI
    const response = await axios.post("http://localhost:8000/scrape", { query }, { timeout: 60000 });

    console.log("✅ FastAPI response received:", response.data);
    res.json(response.data);

  } catch (err) {
    console.error("agentController error:", err.message);
    res.status(500).json({ error: "Agent internal error", details: err.response?.data || err.message });
  }
};
