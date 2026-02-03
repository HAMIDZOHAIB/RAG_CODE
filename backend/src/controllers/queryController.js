// queryController.js - OPTIMIZED VERSION
import axios from "axios";
import Groq from "groq-sdk";
import WebsiteData from "../../models/websitedata.js";
import ChatSession from "../../models/ChatSession.js";

const TOP_K = 5;
const EMBEDDING_API_URL = process.env.EMBEDDING_API_URL || "http://localhost:5000/embed";
const EMBEDDING_API_TIMEOUT = 5000;

const groq = new Groq({
  apiKey: process.env.GROQ_API_KEY,
});

export const handleQuery = async (req, res) => {
  try {
    const { session_id, query } = req.body;

    if (!session_id || !query) {
      return res.status(400).json({ error: "session_id and query are required" });
    }

    // 1️⃣ Generate embedding
    let queryEmbedding;
    try {
      const embedResp = await axios.post(
        EMBEDDING_API_URL,
        { text: query },
        { timeout: EMBEDDING_API_TIMEOUT }
      );
      queryEmbedding = embedResp.data.embedding;
    } catch (embedError) {
      if (embedError.code === 'ECONNREFUSED') {
        return res.status(503).json({ 
          error: "Embedding service unavailable. Ensure Python server is running." 
        });
      }
      return res.status(500).json({ error: "Failed to generate embedding" });
    }

    // 2️⃣ Fetch and score chunks
    const allChunks = await WebsiteData.findAll();
    
    if (allChunks.length === 0) {
      return res.status(404).json({ error: "No documents in database" });
    }

    const scoredChunks = allChunks.map(row => ({
      row,
      score: cosineSimilarity(queryEmbedding, row.embedding)
    }));

    const topChunks = scoredChunks
      .sort((a, b) => b.score - a.score)
      .slice(0, TOP_K)
      .map(c => c.row);

    // 3️⃣ Fetch conversation history
    const sessionMessages = await ChatSession.findAll({
      where: { session_id },
      order: [["createdAt", "ASC"]],
      limit: 10 // Only last 10 messages for context
    });

    const conversationHistory = sessionMessages.map(msg => ({
      role: msg.role,
      content: msg.message,
    }));
    console.log(`📜 Loaded ${conversationHistory.length} messages for session ${session_id}`);
console.log("Conversation history:", conversationHistory.slice(-6));

    // 4️⃣ Prepare context - SHORTENED
    const contextText = topChunks
      .map((chunk, idx) => `[${idx + 1}] ${chunk.plain_text.substring(0, 500)}`) // Limit chunk size
      .join("\n\n");

    // 5️⃣ OPTIMIZED SYSTEM PROMPT - FORCES SHORT ANSWERS
    const systemPrompt = `Answer in 2-3 sentences maximum. Be direct and concise.

Context:
${contextText}

Rules:
- Answer ONLY from context above
- NO phrases like "According to the context" or "Based on the information"
- If answer not in context, say "I don't have that information"
- Keep it short and factual`;

    // 6️⃣ Build messages
    const messages = [
      { role: "system", content: systemPrompt },
      ...conversationHistory.slice(-6), // Only last 3 exchanges
      { role: "user", content: query },
    ];

    // 7️⃣ Store user query
    await ChatSession.create({
      session_id,
      role: "user",
      message: query,
    });

    // 8️⃣ Call Groq with STRICT settings for short answers
    const completion = await groq.chat.completions.create({
      messages: messages,
      model: "llama-3.3-70b-versatile",
      temperature: 0.3,        // Very focused
      max_tokens: 200,         // SHORT answers only
      top_p: 0.85,
      frequency_penalty: 0.6,
      presence_penalty: 0.4,
      stop: ["\n\n", "According to", "Based on"], // Stop verbose phrases
    });

    const answer = completion.choices[0]?.message?.content || "No response generated";
    

    // 9️⃣ Store assistant response
    await ChatSession.create({
      session_id,
      role: "assistant",
      message: answer,
    });

    // 🔟 Return clean response
    res.json({
      answer: answer,
      sources: topChunks.map((c, idx) => ({
        id: idx + 1,
        text: c.plain_text.substring(0, 150) + "...",
        score: scoredChunks.find(sc => sc.row.id === c.id)?.score.toFixed(3),
      })),
      session_id: session_id,
    });

  } catch (err) {
    console.error("Error in handleQuery:", err);
    res.status(500).json({ error: "Internal server error" });
  }
};

function cosineSimilarity(a, b) {
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) {
    throw new Error("Invalid vectors");
  }
  const dot = a.reduce((sum, val, i) => sum + val * b[i], 0);
  const normA = Math.sqrt(a.reduce((sum, val) => sum + val * val, 0));
  const normB = Math.sqrt(b.reduce((sum, val) => sum + val * val, 0));
  return normA === 0 || normB === 0 ? 0 : dot / (normA * normB);
}

// NEW: Get chat history endpoint
export const getChatHistory = async (req, res) => {
  try {
    const { session_id } = req.query;  // Changed to query params
    
    if (!session_id) {
      return res.status(400).json({ error: "session_id is required" });
    }
    
    const messages = await ChatSession.findAll({
      where: { session_id },
      order: [["createdAt", "ASC"]],
    });
    
    const formattedHistory = messages.map(msg => ({
      role: msg.role,
      content: msg.message,
      createdAt: msg.createdAt
    }));
    
    res.json({ 
      history: formattedHistory,
      session_id: session_id 
    });
  } catch (err) {
    console.error("Error fetching chat history:", err);
    res.status(500).json({ error: "Failed to fetch history" });
  }
};
// NEW: Clear chat history endpoint
export const clearHistory = async (req, res) => {
  try {
    const { session_id } = req.body;
    
    await ChatSession.destroy({
      where: { session_id }
    });
    
    res.json({ message: "History cleared" });
  } catch (err) {
    res.status(500).json({ error: "Failed to clear history" });
  }
};