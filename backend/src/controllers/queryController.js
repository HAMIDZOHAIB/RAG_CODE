// queryController.js - FIXED VERSION
import axios from "axios";
import Groq from "groq-sdk";
import WebsiteData from "../../models/websitedata.js";
import ChatSession from "../../models/ChatSession.js";

const TOP_K = 5;
const SIMILARITY_THRESHOLD = 0.35; // Keep consistent
const EMBEDDING_API_URL = process.env.EMBEDDING_API_URL || "http://localhost:5000/embed";
const EMBEDDING_API_TIMEOUT = 5000;
const PYTHON_SCRAPER_URL = process.env.PYTHON_SCRAPER_URL || "http://localhost:8000/scrape";

const scrapingInProgress = new Map();
const activeRequests = new Map();

const groq = new Groq({
  apiKey: process.env.GROQ_API_KEY,
});

// ✅ ULTRA-STRONG follow-up detection including "give me the link/website"
function hasStrongFollowUpIndicators(query) {
  const lowerQuery = query.toLowerCase().trim();
  
  const strongIndicators = [
    // Pronouns at start
    /^(it|this|that|these|those|they|them|its|their)\s/i,
    
    // CRITICAL: "give me" / "show me" patterns
    /^(give|show|send|provide|share)\s+(me|us)\s+(the|a|an|its|their)/i,
    /^(give|show|send|provide|share)\s+(the|a|an)/i,
    
    // "the link" / "the website" / "the url"
    /\b(the|a|an)\s+(link|website|url|site|page|source)\b/i,
    
    // Question words + pronouns
    /^(why|how|when|where|what)\s+(is|are|do|does|can|should)\s+(it|this|that|these|those)/i,
    /^(why|how|when|where)\s+(use|need|have|want|do)\s+(it|this|that)/i,
    
    // Corrective phrases
    /\b(not (the )?(right|correct|official)|wrong|another|different)\b/i,
    /\b(give me (the )?(official|correct|right|actual|real))\b/i,
    
    // Very short procedural
    /^(link|website|url|source|page)\??$/i,
    /^(how|why|what|when|where)\??$/i,
  ];
  
  return strongIndicators.some(pattern => pattern.test(lowerQuery));
}

function isMCQorIndependentQuery(query) {
  const lowerQuery = query.toLowerCase().trim();
  
  const mcqPatterns = [
    /^[a-d]\)/i,
    /^[a-d]\./i,
    /\b(option [a-d]|choice [a-d])\b/i,
    /\b(select|choose) (the )?(correct|right|best)\b/i,
    /which of the following/i,
    /all of the above|none of the above/i,
    /^(true|false)[\s:]/i,
    /^(q\d+|question \d+|\d+[\.\):])/i,
  ];
  
  return mcqPatterns.some(pattern => pattern && pattern.test(lowerQuery));
}

function hasNewTopicIndicators(query) {
  const lowerQuery = query.toLowerCase().trim();
  
  const newTopicPhrases = [
    /^(tell me about|what is|who is|explain|describe)\s(?!it|this|that|the link|the website)/i,
    /^(search for|find|look up)\s(?!it|this|that|the link|the website)/i,
  ];
  
  return newTopicPhrases.some(pattern => pattern.test(lowerQuery));
}

async function shouldUseContext(query, conversationHistory) {
  console.log(`\n🧠 === CONTEXT DECISION for: "${query}" ===`);
  
  if (conversationHistory.length === 0) {
    console.log(`📋 No history`);
    return { useContext: false, reason: "no_history" };
  }
  
  if (isMCQorIndependentQuery(query)) {
    console.log(`📋 MCQ detected`);
    return { useContext: false, reason: "mcq_detected" };
  }
  
  if (hasStrongFollowUpIndicators(query)) {
    console.log(`📋 ✅ STRONG FOLLOW-UP - Using context`);
    return { useContext: true, reason: "strong_followup" };
  }
  
  if (hasNewTopicIndicators(query)) {
    console.log(`📋 New topic detected`);
    return { useContext: false, reason: "new_topic" };
  }
  
  const wordCount = query.trim().split(/\s+/).length;
  if (wordCount <= 5) {
    console.log(`📋 Short query (${wordCount} words) - Using context`);
    return { useContext: true, reason: "short_query" };
  }
  
  console.log(`📋 Default - Independent query`);
  return { useContext: false, reason: "default" };
}

export const handleQuery = async (req, res) => {
  const startTime = Date.now();
  
  try {
    const { session_id, query, skip_scraping, check_similarity_only } = req.body;

    if (!session_id || !query) {
      return res.status(400).json({ error: "session_id and query are required" });
    }

    const scrapingKey = `${session_id}:${query.toLowerCase().trim()}`;
    
    // ✅ PREVENT DUPLICATES
    if (!check_similarity_only && activeRequests.has(scrapingKey)) {
      console.log(`⚠️ DUPLICATE REQUEST BLOCKED: "${query}"`);
      return res.status(429).json({ 
        error: "Request already in progress",
        message: "This query is currently being processed."
      });
    }
    
    if (!check_similarity_only) {
      activeRequests.set(scrapingKey, Date.now());
      console.log(`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
      console.log(`📝 NEW REQUEST: "${query}"`);
      console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
    }

    // Fetch history
    const sessionMessages = await ChatSession.findAll({
      where: { session_id },
      order: [["createdAt", "ASC"]],
      limit: 12
    });

    const conversationHistory = sessionMessages.map(msg => ({
      role: msg.role,
      content: msg.message,
    })).filter(msg => 
      !msg.content.includes('🔍') && 
      !msg.content.includes('⏳') && 
      !msg.content.includes('❌')
    );

    console.log(`📚 History: ${conversationHistory.length} messages`);
    if (conversationHistory.length > 0) {
      const lastTwo = conversationHistory.slice(-2);
      lastTwo.forEach(msg => {
        console.log(`  ${msg.role}: "${msg.content.substring(0, 60)}..."`);
      });
    }

    // Context decision
    const contextDecision = await shouldUseContext(query, conversationHistory);
    const useContext = contextDecision.useContext;
    
    console.log(`✅ CONTEXT: ${useContext ? 'YES' : 'NO'} (${contextDecision.reason})`);

    // Build embedding query
    let queryForEmbedding = query;
    
    if (useContext && conversationHistory.length > 0) {
      const recentContext = conversationHistory
        .slice(-4)
        .map(msg => msg.content)
        .join(" ");
      
      queryForEmbedding = `${recentContext} ${query}`;
      console.log(`🔗 Enhanced: "${queryForEmbedding.substring(0, 100)}..."`);
    }

    // Generate embedding
    let queryEmbedding;
    try {
      const embedResp = await axios.post(
        EMBEDDING_API_URL,
        { text: queryForEmbedding },
        { timeout: EMBEDDING_API_TIMEOUT }
      );
      queryEmbedding = embedResp.data.embedding;
    } catch (embedError) {
      activeRequests.delete(scrapingKey);
      if (embedError.code === 'ECONNREFUSED') {
        return res.status(503).json({ 
          error: "Embedding service unavailable",
          is_sufficient: false,
          similarity_score: 0
        });
      }
      return res.status(500).json({ 
        error: "Failed to generate embedding",
        is_sufficient: false,
        similarity_score: 0
      });
    }

    // Fetch and score
    const allChunks = await WebsiteData.findAll();
    
    if (allChunks.length === 0) {
      activeRequests.delete(scrapingKey);
      return res.status(404).json({ 
        error: "No documents in database",
        is_sufficient: false,
        similarity_score: 0
      });
    }

    const scoredChunks = allChunks.map(row => ({
      row,
      score: cosineSimilarity(queryEmbedding, row.embedding)
    }));

    const topChunks = scoredChunks
      .sort((a, b) => b.score - a.score)
      .slice(0, TOP_K);

    const maxScore = topChunks[0]?.score || 0;
    console.log(`🎯 Similarity: ${(maxScore * 100).toFixed(2)}%`);

    // Similarity check only
    if (check_similarity_only) {
      const response = {
        max_similarity: (maxScore * 100).toFixed(2) + "%",
        similarity_score: maxScore,
        is_sufficient: maxScore >= SIMILARITY_THRESHOLD,
        scraping_in_progress: scrapingInProgress.has(scrapingKey),
        session_id: session_id,
      };
      
      // If scraping is done and we have answer, include it
      if (!scrapingInProgress.has(scrapingKey) && maxScore >= SIMILARITY_THRESHOLD) {
        console.log(`✅ Scraping done, similarity sufficient - answering via poll`);
        // We'll let the next non-check_similarity_only call handle the answer
      }
      
      activeRequests.delete(scrapingKey);
      return res.json(response);
    }

    // Low similarity - scrape
    if (maxScore < SIMILARITY_THRESHOLD && !skip_scraping) {
      
      if (scrapingInProgress.has(scrapingKey)) {
        const startTime = scrapingInProgress.get(scrapingKey);
        const elapsedSeconds = (Date.now() - startTime) / 1000;
        
        activeRequests.delete(scrapingKey);
        
        return res.json({
          answer: `⏳ Still searching the web... (${elapsedSeconds.toFixed(0)}s elapsed)`,
          session_id: session_id,
          scraping_in_progress: true,
          elapsed_seconds: elapsedSeconds.toFixed(0),
          is_sufficient: false,
          similarity_score: maxScore
        });
      }

      console.log(`❌ Low similarity → Starting scraper`);

      scrapingInProgress.set(scrapingKey, Date.now());

      await ChatSession.create({
        session_id,
        role: "user",
        message: query,
      });

      await ChatSession.create({
        session_id,
        role: "assistant",
        message: "🔍 Searching the web for information...",
      });

      triggerScraperWithCallback(query, session_id, scrapingKey);

      activeRequests.delete(scrapingKey);
      
      return res.json({
        answer: "🔍 Searching the web for information...",
        session_id: session_id,
        scraping_started: true,
        max_similarity: (maxScore * 100).toFixed(2) + "%",
        is_sufficient: false,
        similarity_score: maxScore
      });
    }

    // Prepare context
    const relevantChunks = topChunks.map(c => c.row);
    const websiteLinks = [...new Set(relevantChunks.map(c => c.website_link))];
    
    const contextText = relevantChunks
      .map((chunk, idx) => `[Source ${idx + 1}] ${chunk.website_link}\n${chunk.plain_text.substring(0, 800)}`)
      .join("\n\n");

    // Get last assistant message
    const lastAssistantMsg = conversationHistory
      .filter(msg => msg.role === 'assistant')
      .slice(-1)[0];
    
    const conversationContext = conversationHistory
      .slice(-6)
      .map(msg => `${msg.role}: ${msg.content}`)
      .join('\n');

    // Build system prompt
    let systemPrompt;
    
    if (useContext && conversationContext) {
      systemPrompt = `You are a helpful assistant. Answer in 2-3 sentences.

RECENT CONVERSATION:
${conversationContext}

${lastAssistantMsg ? `LAST THING YOU SAID:\n"${lastAssistantMsg.content}"\n` : ''}

CONTEXT FROM DATABASE:
${contextText}

AVAILABLE LINKS:
${websiteLinks.map((link, idx) => `${idx + 1}. ${link}`).join('\n')}

CRITICAL INSTRUCTIONS:
- This is a FOLLOW-UP question about the conversation above
- If user asks for "the link" or "the website", provide the link from YOUR LAST RESPONSE
- Example: You said "NGTSOL is a company...", user asks "give me the link" → find NGTSOL link in sources
- ALWAYS look at BOTH conversation AND database context
- Extract entity names from conversation (NGTSOL, VLC, etc.) and find their links in sources
- Be direct and helpful
- NO phrases like "According to the context"`;
    } else {
      systemPrompt = `You are a helpful assistant. Answer in 2-3 sentences.

CONTEXT FROM DATABASE:
${contextText}

AVAILABLE LINKS:
${websiteLinks.map((link, idx) => `${idx + 1}. ${link}`).join('\n')}

INSTRUCTIONS:
- Answer from the database context
- Be direct and helpful
- NO phrases like "According to the context"`;
    }

    // Build messages
    const messages = [
      { role: "system", content: systemPrompt },
      ...conversationHistory.slice(-6),
      { role: "user", content: query },
    ];

    // Store user query
    if (!skip_scraping) {
      await ChatSession.create({
        session_id,
        role: "user",
        message: query,
      });
    }

    // Call Groq
    console.log(`🤖 Calling LLM...`);
    
    const completion = await groq.chat.completions.create({
      messages: messages,
      model: "llama-3.3-70b-versatile",
      temperature: 0.7,
      max_tokens: 700,
      top_p: 0.9,
    });

    const answer = completion.choices[0]?.message?.content || "No response generated";
    
    console.log(`💬 Answer: "${answer.substring(0, 100)}..."`);
    
    // Check if RAG failed
    const noInfoPhrases = [
      "i don't have",
      "no information available",
      "cannot find",
      "not available",
    ];
    
    const hasNoInfo = noInfoPhrases.some(phrase => 
      answer.toLowerCase().includes(phrase)
    );
    
    if (hasNoInfo && !skip_scraping) {
      
      if (scrapingInProgress.has(scrapingKey)) {
        const startTime = scrapingInProgress.get(scrapingKey);
        const elapsedSeconds = (Date.now() - startTime) / 1000;
        
        activeRequests.delete(scrapingKey);
        
        return res.json({
          answer: `⏳ Still searching the web... (${elapsedSeconds.toFixed(0)}s elapsed)`,
          session_id: session_id,
          scraping_in_progress: true,
          is_sufficient: false,
          similarity_score: maxScore
        });
      }

      console.log("❌ RAG failed → Starting scraper");

      scrapingInProgress.set(scrapingKey, Date.now());

      await ChatSession.create({
        session_id,
        role: "assistant",
        message: "🔍 Searching the web for information...",
      });

      triggerScraperWithCallback(query, session_id, scrapingKey);

      activeRequests.delete(scrapingKey);
      
      return res.json({
        answer: "🔍 Searching the web for information...",
        session_id: session_id,
        scraping_started: true,
        reason: "no_info",
        is_sufficient: false,
        similarity_score: maxScore
      });
    }

    // Store response
    await ChatSession.create({
      session_id,
      role: "assistant",
      message: answer,
    });

    const elapsed = Date.now() - startTime;
    console.log(`✅ Complete in ${elapsed}ms`);
    console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`);

    // ✅ FIXED: Added all flags for frontend
    const response = {
      answer: answer,
      sources: topChunks.map((c, idx) => ({
        id: idx + 1,
        text: c.row.plain_text.substring(0, 150) + "...",
        score: c.score.toFixed(3),
        website_link: c.row.website_link
      })),
      website_links: websiteLinks,
      max_similarity: (maxScore * 100).toFixed(2) + "%",
      context_used: useContext,
      session_id: session_id,
      // ✅ CRITICAL FLAGS FOR FRONTEND
      is_sufficient: true,
      similarity_score: maxScore,
      scraping_in_progress: false,
      scraping_started: false
    };
    
    res.json(response);
    activeRequests.delete(scrapingKey);

  } catch (err) {
    console.error("❌ Error:", err.message);
    const scrapingKey = `${req.body.session_id}:${req.body.query.toLowerCase().trim()}`;
    activeRequests.delete(scrapingKey);
    res.status(500).json({ 
      error: "Internal server error",
      is_sufficient: false,
      similarity_score: 0
    });
  }
};

async function triggerScraperWithCallback(query, session_id, scrapingKey) {
  try {
    console.log(`🚀 Scraper starting...`);
    
    const response = await axios.post(PYTHON_SCRAPER_URL, {
      query: query,
      session_id: session_id
    }, { timeout: 120000 });

    console.log(`✅ Scraper done:`, response.data);
    
    if (response.data.message === 'No new results found' || response.data.new_urls === 0) {
      await ChatSession.create({
        session_id,
        role: "assistant",
        message: "❌ I couldn't find relevant information. Please try rephrasing.",
      });
    } else {
      await ChatSession.create({
        session_id,
        role: "assistant",
        message: "✅ I've searched the web and found new information. Please ask your question again.",
      });
    }
    
    scrapingInProgress.delete(scrapingKey);
    
  } catch (error) {
    console.error(`❌ Scraper failed:`, error.message);
    
    await ChatSession.create({
      session_id,
      role: "assistant",
      message: "❌ Web search encountered an error. Please try again.",
    });
    
    scrapingInProgress.delete(scrapingKey);
  }
}

function cosineSimilarity(a, b) {
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) {
    return 0;
  }
  const dot = a.reduce((sum, val, i) => sum + val * b[i], 0);
  const normA = Math.sqrt(a.reduce((sum, val) => sum + val * val, 0));
  const normB = Math.sqrt(b.reduce((sum, val) => sum + val * val, 0));
  return normA === 0 || normB === 0 ? 0 : dot / (normA * normB);
}

export const getChatHistory = async (req, res) => {
  try {
    const { session_id } = req.query;
    
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