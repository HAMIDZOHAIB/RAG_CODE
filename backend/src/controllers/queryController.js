// queryController.js - FIXED VERSION with better error handling
import axios from "axios";
import Groq from "groq-sdk";
import WebsiteData from "../../models/websitedata.js";
import ChatSession from "../../models/ChatSession.js";

const TOP_K = 5;
const SIMILARITY_THRESHOLD = 0.35;
const EMBEDDING_API_URL = process.env.EMBEDDING_API_URL || "http://localhost:5000/embed";
const EMBEDDING_API_TIMEOUT = 5000;
const PYTHON_SCRAPER_URL = process.env.PYTHON_SCRAPER_URL || "http://localhost:8000/scrape";

const scrapingInProgress = new Map();
const activeRequests = new Map();

// ✅ Add request timeout to prevent hanging
const REQUEST_TIMEOUT = 30000; // 30 seconds

const groq = new Groq({
  apiKey: process.env.GROQ_API_KEY,
});

// ✅ ULTRA-STRONG follow-up detection
function hasStrongFollowUpIndicators(query) {
  const lowerQuery = query.toLowerCase().trim();
  
  const strongIndicators = [
    /^(it|this|that|these|those|they|them|its|their)\s/i,
    /^(give|show|send|provide|share)\s+(me|us)\s+(the|a|an|its|their)/i,
    /^(give|show|send|provide|share)\s+(the|a|an)/i,
    /\b(the|a|an)\s+(link|website|url|site|page|source)\b/i,
    /^(why|how|when|where|what)\s+(is|are|do|does|can|should)\s+(it|this|that|these|those)/i,
    /^(why|how|when|where)\s+(use|need|have|want|do)\s+(it|this|that)/i,
    /\b(not (the )?(right|correct|official)|wrong|another|different)\b/i,
    /\b(give me (the )?(official|correct|right|actual|real))\b/i,
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
  
  return newTopicPhrases.some(phrase => phrase.test(lowerQuery));
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

    // ✅ Validate inputs
    if (!session_id || !query) {
      console.error("❌ Missing required fields:", { session_id, query });
      return res.status(400).json({ 
        error: "session_id and query are required",
        is_sufficient: false,
        similarity_score: 0
      });
    }

    const scrapingKey = `${session_id}:${query.toLowerCase().trim()}`;
    
    // ✅ PREVENT DUPLICATES
    if (!check_similarity_only && activeRequests.has(scrapingKey)) {
      console.log(`⚠️ DUPLICATE REQUEST BLOCKED: "${query}"`);
      return res.status(429).json({ 
        error: "Request already in progress",
        message: "This query is currently being processed.",
        is_sufficient: false,
        similarity_score: 0
      });
    }
    
    if (!check_similarity_only) {
      activeRequests.set(scrapingKey, Date.now());
      console.log(`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
      console.log(`📝 NEW REQUEST: "${query}"`);
      console.log(`   skip_scraping: ${skip_scraping}`);
      console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
    }

    // ✅ Fetch history with error handling
    let sessionMessages = [];
    try {
      sessionMessages = await ChatSession.findAll({
        where: { session_id },
        order: [["createdAt", "ASC"]],
        limit: 12
      });
    } catch (dbError) {
      console.error("❌ Database error fetching history:", dbError);
      activeRequests.delete(scrapingKey);
      return res.status(500).json({ 
        error: "Database error",
        is_sufficient: false,
        similarity_score: 0
      });
    }

    const conversationHistory = sessionMessages.map(msg => ({
      role: msg.role,
      content: msg.message,
    })).filter(msg => 
      !msg.content.includes('🔍') && 
      !msg.content.includes('⏳') && 
      !msg.content.includes('❌')
    );

    console.log(`📚 History: ${conversationHistory.length} messages`);

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
      console.log(`🔗 Enhanced query (${queryForEmbedding.length} chars)`);
    }

    // ✅ Generate embedding with better error handling
    let queryEmbedding;
    try {
      console.log(`🧠 Generating embedding...`);
      const embedResp = await axios.post(
        EMBEDDING_API_URL,
        { text: queryForEmbedding },
        { timeout: EMBEDDING_API_TIMEOUT }
      );
      
      if (!embedResp.data || !embedResp.data.embedding) {
        throw new Error("Invalid embedding response");
      }
      
      queryEmbedding = embedResp.data.embedding;
      console.log(`   ✅ Embedding generated (${queryEmbedding.length} dims)`);
      
    } catch (embedError) {
      console.error("❌ Embedding error:", embedError.message);
      activeRequests.delete(scrapingKey);
      
      if (embedError.code === 'ECONNREFUSED') {
        return res.status(503).json({ 
          error: "Embedding service unavailable. Please check if the embedding server is running.",
          is_sufficient: false,
          similarity_score: 0
        });
      }
      
      return res.status(500).json({ 
        error: "Failed to generate embedding: " + embedError.message,
        is_sufficient: false,
        similarity_score: 0
      });
    }

    // ✅ Fetch chunks with error handling
    let allChunks;
    try {
      console.log(`📊 Fetching database chunks...`);
      allChunks = await WebsiteData.findAll();
      console.log(`   Found ${allChunks.length} chunks`);
    } catch (dbError) {
      console.error("❌ Database error fetching chunks:", dbError);
      activeRequests.delete(scrapingKey);
      return res.status(500).json({ 
        error: "Database error",
        is_sufficient: false,
        similarity_score: 0
      });
    }
    
    if (allChunks.length === 0) {
      console.log("⚠️  No chunks in database");
      activeRequests.delete(scrapingKey);
      return res.status(404).json({ 
        error: "No documents in database",
        is_sufficient: false,
        similarity_score: 0
      });
    }

    // ✅ Score chunks with validation
    const scoredChunks = allChunks
      .filter(row => row.embedding && Array.isArray(row.embedding))
      .map(row => ({
        row,
        score: cosineSimilarity(queryEmbedding, row.embedding)
      }))
      .filter(item => !isNaN(item.score)); // Remove invalid scores

    if (scoredChunks.length === 0) {
      console.log("⚠️  No valid embeddings found");
      activeRequests.delete(scrapingKey);
      return res.status(500).json({ 
        error: "No valid embeddings in database",
        is_sufficient: false,
        similarity_score: 0
      });
    }

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
      
      activeRequests.delete(scrapingKey);
      return res.json(response);
    }

    // ✅ Low similarity - scrape
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

      console.log(`❌ Low similarity (${(maxScore * 100).toFixed(2)}%) → Starting scraper`);

      scrapingInProgress.set(scrapingKey, Date.now());

      // ✅ Save messages with error handling
      try {
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
      } catch (dbError) {
        console.error("⚠️  Could not save messages:", dbError);
      }

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

    // ✅ Prepare context
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
- Extract entity names from conversation and find their links in sources
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

    // ✅ Store user query with error handling
    if (!skip_scraping) {
      try {
        await ChatSession.create({
          session_id,
          role: "user",
          message: query,
        });
      } catch (dbError) {
        console.error("⚠️  Could not save user message:", dbError);
      }
    }

    // ✅ Call Groq with error handling
    console.log(`🤖 Calling LLM...`);
    
    let answer;
    try {
      const completion = await groq.chat.completions.create({
        messages: messages,
        model: "llama-3.3-70b-versatile",
        temperature: 0.7,
        max_tokens: 700,
        top_p: 0.9,
      });

      answer = completion.choices[0]?.message?.content || "No response generated";
      console.log(`💬 Answer: "${answer.substring(0, 100)}..."`);
      
    } catch (llmError) {
      console.error("❌ LLM error:", llmError);
      activeRequests.delete(scrapingKey);
      
      return res.status(500).json({ 
        error: "LLM service error: " + llmError.message,
        is_sufficient: false,
        similarity_score: maxScore
      });
    }
    
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

      try {
        await ChatSession.create({
          session_id,
          role: "assistant",
          message: "🔍 Searching the web for information...",
        });
      } catch (dbError) {
        console.error("⚠️  Could not save message:", dbError);
      }

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

    // ✅ Store response with error handling
    try {
      await ChatSession.create({
        session_id,
        role: "assistant",
        message: answer,
      });
    } catch (dbError) {
      console.error("⚠️  Could not save assistant message:", dbError);
    }

    const elapsed = Date.now() - startTime;
    console.log(`✅ Complete in ${elapsed}ms`);
    console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`);

    // ✅ Send response
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
      is_sufficient: true,
      similarity_score: maxScore,
      scraping_in_progress: false,
      scraping_started: false
    };
    
    res.json(response);
    activeRequests.delete(scrapingKey);

  } catch (err) {
    console.error("❌ UNHANDLED ERROR in handleQuery:");
    console.error(err);
    
    const scrapingKey = `${req.body?.session_id}:${req.body?.query?.toLowerCase().trim()}`;
    activeRequests.delete(scrapingKey);
    
    res.status(500).json({ 
      error: "Internal server error: " + err.message,
      is_sufficient: false,
      similarity_score: 0
    });
  }
};

async function triggerScraperWithCallback(query, session_id, scrapingKey) {
  try {
    console.log(`🚀 Triggering scraper at ${PYTHON_SCRAPER_URL}...`);
    
    const response = await axios.post(PYTHON_SCRAPER_URL, {
      query: query,
      session_id: session_id
    }, { 
      timeout: 120000,
      validateStatus: (status) => status < 600 // Don't throw on 4xx/5xx
    });

    console.log(`✅ Scraper response (${response.status}):`, response.data);
    
    if (response.status !== 200) {
      console.error(`⚠️  Scraper returned non-200 status: ${response.status}`);
    }
    
    if (response.data.message === 'No new results found' || response.data.new_urls === 0) {
      try {
        await ChatSession.create({
          session_id,
          role: "assistant",
          message: "❌ I couldn't find relevant information. Please try rephrasing.",
        });
      } catch (dbError) {
        console.error("⚠️  Could not save message:", dbError);
      }
    } else {
      try {
        await ChatSession.create({
          session_id,
          role: "assistant",
          message: "✅ I've searched the web and found new information. Please ask your question again.",
        });
      } catch (dbError) {
        console.error("⚠️  Could not save message:", dbError);
      }
    }
    
    scrapingInProgress.delete(scrapingKey);
    
  } catch (error) {
    console.error(`❌ Scraper error:`, error.message);
    if (error.response) {
      console.error(`   Status: ${error.response.status}`);
      console.error(`   Data:`, error.response.data);
    }
    
    try {
      await ChatSession.create({
        session_id,
        role: "assistant",
        message: "❌ Web search encountered an error. Please try again.",
      });
    } catch (dbError) {
      console.error("⚠️  Could not save error message:", dbError);
    }
    
    scrapingInProgress.delete(scrapingKey);
  }
}

function cosineSimilarity(a, b) {
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) {
    console.error("⚠️  Invalid vectors for similarity:", { 
      aType: typeof a, 
      bType: typeof b,
      aLen: a?.length,
      bLen: b?.length
    });
    return 0;
  }
  
  const dot = a.reduce((sum, val, i) => sum + val * b[i], 0);
  const normA = Math.sqrt(a.reduce((sum, val) => sum + val * val, 0));
  const normB = Math.sqrt(b.reduce((sum, val) => sum + val * val, 0));
  
  if (normA === 0 || normB === 0) {
    console.error("⚠️  Zero norm vector");
    return 0;
  }
  
  return dot / (normA * normB);
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
    console.error("Error clearing history:", err);
    res.status(500).json({ error: "Failed to clear history" });
  }
};