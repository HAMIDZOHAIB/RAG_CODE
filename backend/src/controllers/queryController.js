// queryController.js - COMPLETE UPDATED VERSION - NO DUAL RESPONSES
import axios from "axios";
import Groq from "groq-sdk";
import WebsiteData from "../../models/websitedata.js";
import ChatSession from "../../models/ChatSession.js";

const TOP_K = 5;
const SIMILARITY_THRESHOLD = 0.15; // Lowered to trigger scraper more often
const EMBEDDING_API_URL = process.env.EMBEDDING_API_URL || "http://localhost:5000/embed";
const EMBEDDING_API_TIMEOUT = 5000;
const PYTHON_SCRAPER_URL = process.env.PYTHON_SCRAPER_URL || "http://localhost:8000/scrape";

const scrapingInProgress = new Map();

const groq = new Groq({
  apiKey: process.env.GROQ_API_KEY,
});

// ✅ PRIORITY 1: Detect STRONG follow-up indicators (MUST use context)
function hasStrongFollowUpIndicators(query, conversationHistory) {
  const lowerQuery = query.toLowerCase().trim();
  
  const strongIndicators = [
    // Pronouns at start (VERY STRONG)
    /^(it|this|that|these|those|they|them|its|their)\s/i,
    /^(why|how|when|where|what)\s+(do|does|is|are|did|can|should|would)\s+(we|i|you|they|it|this|that)/i,
    // Ultra short questions that MUST be follow-ups
    /^(why|how|when|where)\s*\?*$/i,
    /^(why|how|when|where)\s+(use|need|have|want|do)\s+(this|that|it|these|those)/i,
    // Corrective phrases
    /\b(not (the )?(right|correct|official)|wrong|another|different)\b/i,
    /\b(give me (the )?(official|correct|right|actual|real))\b/i,
    /\b(that('s| is) not|that('s| is) wrong|that('s| is) incorrect)\b/i,
    // Clarification requests
    /\b(i mean|i meant|i want|i need)\b/i,
    /\b(what about|how about)\s(it|this|that)/i,
    // Direct references
    /\b(the (same|one|link|website|answer|information))\b/i,
    // Questions asking about something just mentioned
    /^(why|how|when|where|what)\s+(is|are|do|does|can|should)\s+(this|that|it|these|those)/i,
    // NEW: Action phrases that are likely follow-ups
    /^(how|what)\s+(to|do|can)\s+(create|make|build|set up|register|sign up|login|use)\b/i,
    /^(can|could|would)\s+(you|i)\s+(create|make|do)/i,
    // NEW: Very short procedural questions
    /^how (to|do|can)/i,
    /^(steps|process|procedure|way|method)/i,
  ];
  
  // Also check if this is a short question after a topic was discussed
  const wordCount = lowerQuery.split(/\s+/).length;
  const isShortProcedural = wordCount <= 7 && 
    (lowerQuery.includes('how') || 
     lowerQuery.includes('create') || 
     lowerQuery.includes('make') || 
     lowerQuery.includes('do') ||
     lowerQuery.includes('account') ||
     lowerQuery.includes('register'));
  
  return strongIndicators.some(pattern => pattern.test(lowerQuery)) || isShortProcedural;
}

// ✅ PRIORITY 2: Detect MCQs (NEVER use context)
function isMCQorIndependentQuery(query) {
  const lowerQuery = query.toLowerCase().trim();
  
  const mcqPatterns = [
    /^[a-d]\)/i,
    /^[a-d]\./i,
    /\b(option [a-d]|choice [a-d])\b/i,
    /\b(select|choose) (the )?(correct|right|best)\b/i,
    /which of the following/i,
    /what is the (answer|result|output)/i,
    /all of the above|none of the above/i,
    /^(true|false)[\s:]/i,
    /\bcorrect (answer|option|statement)\b/i,
    /^(q\d+|question \d+|\d+[\.\):])/i,
  ];
  
  return mcqPatterns.some(pattern => pattern && pattern.test(lowerQuery));
}

// ✅ Detect NEW TOPIC indicators (phrases that signal topic change)
function hasNewTopicIndicators(query) {
  const lowerQuery = query.toLowerCase().trim();
  
  const newTopicPhrases = [
    /^(tell me about|what is|who is|explain|describe)\s(?!it|this|that)/i,
    /^(search for|find|look up|show me)\s(?!it|this|that)/i,
    /^(i want to (know|learn|ask) about)\s/i,
  ];
  
  return newTopicPhrases.some(pattern => pattern.test(lowerQuery));
}

// ✅ Extract main topics from conversation for better embedding search
function extractTopicsFromConversation(conversationHistory) {
  if (!conversationHistory.length) return "";
  
  const lastFewMessages = conversationHistory.slice(-4);
  let topics = new Set();
  
  // Look for specific entities in recent conversation
  lastFewMessages.forEach(msg => {
    const content = msg.content.toLowerCase();
    
    // Extract potential software/app names
    const softwarePatterns = [
      /\b(binance|crypto|bitcoin|ethereum)\b/i,
      /\b(vlc|media player|videolan)\b/i,
      /\b(chrome|browser)\b/i,
      /\b(firefox|mozilla)\b/i,
      /\b(word|excel|powerpoint|office)\b/i,
      /\b(photoshop|adobe)\b/i,
      /\b(windows|macos|linux|android|ios)\b/i,
      /\b(software|app|application|tool|program|platform)\b/i
    ];
    
    softwarePatterns.forEach(pattern => {
      const match = content.match(pattern);
      if (match) {
        topics.add(match[0].toLowerCase());
      }
    });
    
    // Extract URLs and domains
    const urlMatch = content.match(/(https?:\/\/[^\s]+|www\.[^\s]+|\b[a-z0-9-]+\.(com|org|net|edu|gov)\b)/gi);
    if (urlMatch) {
      urlMatch.forEach(url => {
        // Extract domain name
        const domainMatch = url.match(/\/\/([^\/]+)/) || url.match(/(www\.[^\/\s\.]+)/);
        if (domainMatch && domainMatch[1]) {
          const domain = domainMatch[1].replace('www.', '').split('.')[0];
          topics.add(domain);
        }
      });
    }
  });
  
  return Array.from(topics).join(' ');
}

// ✅ Enhance query for embedding based on conversation context
function enhanceQueryForEmbedding(query, conversationHistory, useContext) {
  if (!useContext || conversationHistory.length === 0) {
    return query;
  }
  
  // Extract topics from recent conversation
  const topics = extractTopicsFromConversation(conversationHistory);
  
  if (!topics) {
    return query;
  }
  
  const lowerQuery = query.toLowerCase();
  let enhancedQuery = query;
  
  // For "how to create account" type queries, add specific platform name
  if (lowerQuery.includes('how') && 
      (lowerQuery.includes('create') || lowerQuery.includes('account') || 
       lowerQuery.includes('register') || lowerQuery.includes('sign up'))) {
    
    // Check what platform was discussed
    const lastExchangeText = conversationHistory
      .slice(-2)
      .map(msg => msg.content)
      .join(' ')
      .toLowerCase();
    
    let platform = '';
    if (lastExchangeText.includes('binance')) platform = 'binance cryptocurrency exchange';
    else if (lastExchangeText.includes('vlc')) platform = 'vlc media player';
    else if (lastExchangeText.includes('chrome')) platform = 'google chrome browser';
    else if (lastExchangeText.includes('photoshop')) platform = 'adobe photoshop';
    
    if (platform) {
      enhancedQuery = `${platform} create account register sign up step by step guide ${query}`;
    } else {
      enhancedQuery = `${topics} create account register sign up step by step guide ${query}`;
    }
    
  } else if (lowerQuery.includes('why') || lowerQuery.includes('benefit') || lowerQuery.includes('advantage')) {
    enhancedQuery = `${topics} benefits advantages features pros why use ${query}`;
  } else if (lowerQuery.includes('how') || lowerQuery.includes('install') || lowerQuery.includes('download')) {
    enhancedQuery = `${topics} installation setup download guide tutorial ${query}`;
  } else if (lowerQuery.includes('what') || lowerQuery.includes('is')) {
    enhancedQuery = `${topics} information details about explanation ${query}`;
  } else {
    enhancedQuery = `${topics} ${query}`;
  }
  
  console.log(`🔗 Enhanced embedding query: "${enhancedQuery}"`);
  return enhancedQuery;
}

// ✅ SMART CONTEXT DECISION with clear priority rules
async function shouldUseContext(query, conversationHistory) {
  console.log(`\n🧠 === CONTEXT DECISION PROCESS ===`);
  
  // RULE 0: No history = no context
  if (conversationHistory.length === 0) {
    console.log(`📋 Rule 0: No conversation history`);
    return { useContext: false, reason: "no_history" };
  }
  
  // RULE 1: MCQs NEVER use context (highest priority for MCQs)
  if (isMCQorIndependentQuery(query)) {
    console.log(`📋 Rule 1: MCQ detected - NEVER use context`);
    return { useContext: false, reason: "mcq_detected" };
  }
  
  // RULE 2: STRONG follow-up indicators ALWAYS use context
  if (hasStrongFollowUpIndicators(query, conversationHistory)) {
    console.log(`📋 Rule 2: Strong follow-up indicator - ALWAYS use context`);
    return { useContext: true, reason: "strong_followup" };
  }
  
  // RULE 2a: Check if last message was about a specific entity
  const lastUserMsg = conversationHistory
    .filter(msg => msg.role === 'user')
    .slice(-1)[0];
  const lastAssistantMsg = conversationHistory
    .filter(msg => msg.role === 'assistant')
    .slice(-1)[0];
  
  // If last exchange mentioned a specific platform/tool, and current query is procedural
  if (lastUserMsg && lastAssistantMsg) {
    const lastExchange = lastUserMsg.content + ' ' + lastAssistantMsg.content;
    const lastExchangeLower = lastExchange.toLowerCase();
    
    const hasSpecificEntity = /\b(binance|cryptocurrency|bitcoin|ethereum|vlc|chrome|photoshop|word|excel)\b/i.test(lastExchange);
    const isProceduralQuery = /\b(how|create|make|set up|register|sign up|login|install|download|account)\b/i.test(query.toLowerCase());
    
    if (hasSpecificEntity && isProceduralQuery) {
      console.log(`📋 Rule 2a: Procedural question about specific entity from last exchange`);
      return { useContext: true, reason: "procedural_followup" };
    }
  }
  
  // RULE 3: New topic indicators suggest starting fresh
  if (hasNewTopicIndicators(query)) {
    console.log(`📋 Rule 3: New topic indicator detected`);
    return { useContext: false, reason: "new_topic_phrase" };
  }
  
  // RULE 4: Check if question is very short (likely reference to previous)
  const wordCount = query.trim().split(/\s+/).length;
  if (wordCount <= 5 && conversationHistory.length > 0) {
    console.log(`📋 Rule 4: Very short query (${wordCount} words) - likely follow-up`);
    return { useContext: true, reason: "short_query" };
  }
  
  // RULE 5: Default to NO context for safety
  console.log(`📋 Rule 5: Default - treat as independent query`);
  return { useContext: false, reason: "default_independent" };
}

// ✅ Helper function to trigger scraper with proper response
async function triggerScraperAndRespond(query, session_id, scrapingKey, res, reason, maxScore = 0) {
  // Mark scraping as in progress
  scrapingInProgress.set(scrapingKey, Date.now());
  
  console.log(`🚀 Starting scraper for: "${query}" (Reason: ${reason})`);

  // Store initial messages
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

  // Send immediate response
  res.json({
    answer: "🔍 Searching the web for information... This may take 20-40 seconds.",
    session_id: session_id,
    scraping_started: true,
    reason: reason,
    max_similarity: maxScore > 0 ? (maxScore * 100).toFixed(2) + "%" : "N/A",
    scraping_key: scrapingKey
  });

  // Trigger scraper in background
  triggerScraperWithCallback(query, session_id, scrapingKey);
}

export const handleQuery = async (req, res) => {
  try {
    const { session_id, query, skip_scraping, check_similarity_only } = req.body;

    if (!session_id || !query) {
      return res.status(400).json({ error: "session_id and query are required" });
    }

    const scrapingKey = `${session_id}:${query.toLowerCase().trim()}`;

    // ✅ Fetch conversation history early
    const sessionMessages = await ChatSession.findAll({
      where: { session_id },
      order: [["createdAt", "ASC"]],
      limit: 10
    });

    const conversationHistory = sessionMessages.map(msg => ({
      role: msg.role,
      content: msg.message,
    }));

    console.log(`\n🔍 NEW QUERY: "${query}"`);
    console.log(`📚 Conversation history length: ${conversationHistory.length}`);

    // ✅ Intelligent context decision
    const contextDecision = await shouldUseContext(query, conversationHistory);
    const useContext = contextDecision.useContext;
    
    console.log(`✅ DECISION: ${useContext ? 'USE CONTEXT' : 'STANDALONE QUERY'} (${contextDecision.reason})`);
    console.log(`🧠 === END CONTEXT DECISION ===\n`);

    // ✅ Build query for embedding with enhancement
    let queryForEmbedding = enhanceQueryForEmbedding(query, conversationHistory, useContext);
    
    console.log(`🎯 Final query for embedding: "${queryForEmbedding}"`);

    // 1️⃣ Generate embedding
    let queryEmbedding;
    try {
      const embedResp = await axios.post(
        EMBEDDING_API_URL,
        { text: queryForEmbedding },
        { timeout: EMBEDDING_API_TIMEOUT }
      );
      queryEmbedding = embedResp.data.embedding;
      console.log(`✅ Embedding generated successfully (${queryEmbedding.length} dimensions)`);
    } catch (embedError) {
      console.error(`❌ Embedding error:`, embedError.message);
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
      console.log(`⚠️ Database is empty - forcing scraper`);
      
      if (!skip_scraping) {
        // Database is empty, definitely need to scrape
        return triggerScraperAndRespond(query, session_id, scrapingKey, res, "empty_database");
      }
      
      return res.status(404).json({ error: "No documents in database" });
    }

    console.log(`📊 Database has ${allChunks.length} chunks to search`);
    
    const scoredChunks = allChunks.map(row => ({
      row,
      score: cosineSimilarity(queryEmbedding, row.embedding)
    }));

    const topChunks = scoredChunks
      .sort((a, b) => b.score - a.score)
      .slice(0, TOP_K);

    const maxScore = topChunks[0]?.score || 0;
    console.log(`🎯 Max similarity score: ${(maxScore * 100).toFixed(2)}%`);
    console.log(`📊 Similarity threshold: ${(SIMILARITY_THRESHOLD * 100).toFixed(2)}%`);
    
    // Log top 3 scores for debugging
    console.log(`📈 Top ${Math.min(3, topChunks.length)} scores:`);
    topChunks.slice(0, 3).forEach((chunk, i) => {
      console.log(`  ${i+1}. ${(chunk.score * 100).toFixed(2)}% - ${chunk.row.website_link}`);
    });

    // ✅ If just checking similarity, return early
    if (check_similarity_only) {
      return res.json({
        max_similarity: (maxScore * 100).toFixed(2) + "%",
        similarity_score: maxScore,
        is_sufficient: maxScore >= SIMILARITY_THRESHOLD,
        scraping_in_progress: scrapingInProgress.has(scrapingKey),
        session_id: session_id,
      });
    }

    // ✅ CRITICAL FIX: Check if similarity is low → SCRAPE FIRST, NO IMMEDIATE ANSWER
    if (maxScore < SIMILARITY_THRESHOLD && !skip_scraping) {
      console.log(`❌ Score ${(maxScore * 100).toFixed(2)}% below threshold ${(SIMILARITY_THRESHOLD * 100).toFixed(2)}% → STARTING SCRAPER`);
      
      // Check if scraper is already running
      if (scrapingInProgress.has(scrapingKey)) {
        const startTime = scrapingInProgress.get(scrapingKey);
        const elapsedSeconds = (Date.now() - startTime) / 1000;
        
        console.log(`⏳ Scraping already in progress (${elapsedSeconds.toFixed(0)}s elapsed)`);
        
        return res.json({
          answer: `⏳ Still searching the web... (${elapsedSeconds.toFixed(0)}s elapsed)`,
          session_id: session_id,
          scraping_in_progress: true,
          elapsed_seconds: elapsedSeconds.toFixed(0)
        });
      }

      // ⚠️ STOP HERE AND SCRAPE, DON'T CONTINUE TO RAG
      console.log(`🚫 Stopping RAG flow, scraping will provide answer later`);
      return triggerScraperAndRespond(query, session_id, scrapingKey, res, "low_similarity", maxScore);
    }

    // ✅ Only continue with RAG if similarity is good
    console.log(`✅ Score ${(maxScore * 100).toFixed(2)}% above threshold, continuing with RAG...`);

    // 3️⃣ Prepare context from retrieved chunks
    const relevantChunks = topChunks.map(c => c.row);
    const websiteLinks = [...new Set(relevantChunks.map(c => c.website_link))];
    
    const contextText = relevantChunks
      .map((chunk, idx) => `[Source ${idx + 1}] (${chunk.website_link})\n${chunk.plain_text.substring(0, 1000)}`)
      .join("\n\n");
    
    console.log(`📄 Retrieved ${relevantChunks.length} chunks from database`);

    // ✅ 4️⃣ Build system prompt
    const conversationContext = conversationHistory
      .slice(-8)
      .filter(msg => !msg.content.includes('🔍') && !msg.content.includes('⏳') && !msg.content.includes('❌'))
      .map(msg => `${msg.role}: ${msg.content}`)
      .join('\n');
    
    const lastAssistantMsg = conversationHistory
      .filter(msg => msg.role === 'assistant')
      .filter(msg => !msg.content.includes('🔍') && !msg.content.includes('⏳') && !msg.content.includes('❌'))
      .slice(-1)[0];

    const conversationTopics = extractTopicsFromConversation(conversationHistory);
    
    let systemPrompt;
    
    if (useContext && conversationContext) {
      systemPrompt = `You are a helpful assistant. Answer in 2-3 sentences maximum, be specific and helpful.

RECENT CONVERSATION:
${conversationContext}

${lastAssistantMsg ? `\nLAST THING YOU TOLD THE USER:\n"${lastAssistantMsg.content}"\n` : ''}
${conversationTopics ? `\nCURRENT TOPIC OF DISCUSSION:\n${conversationTopics}\n` : ''}

CONTEXT FROM DATABASE:
${contextText}

AVAILABLE LINKS:
${websiteLinks.map((link, idx) => `${idx + 1}. ${link}`).join('\n')}

CRITICAL INSTRUCTIONS - READ CAREFULLY:
1. Answer ONLY from the database context provided
2. If the context doesn't have enough information, say: "I don't have enough information about that in my database."
3. Do NOT make up information
4. Be conversational and helpful
5. NO phrases like "According to the context"`;
    } else {
      systemPrompt = `You are a helpful assistant. Answer in 2-3 sentences maximum.

${conversationContext ? `RECENT CONVERSATION (for reference):\n${conversationContext}\n\n` : ''}CONTEXT FROM DATABASE:
${contextText}

AVAILABLE LINKS:
${websiteLinks.map((link, idx) => `${idx + 1}. ${link}`).join('\n')}

INSTRUCTIONS:
- Answer ONLY from the database context above
- If context doesn't have relevant info, say: "I don't have enough information about that in my database."
- Do NOT make up information
- Be conversational and helpful
- NO phrases like "According to the context"`;
    }

    // 5️⃣ Build messages
    const messages = [
      { role: "system", content: systemPrompt },
      ...conversationHistory.slice(-8),
      { role: "user", content: query },
    ];

    // 6️⃣ Store user query
    if (!skip_scraping) {
      await ChatSession.create({
        session_id,
        role: "user",
        message: query,
      });
    }

    // 7️⃣ Call Groq
    console.log(`🤖 Calling LLM with RAG context...`);
    
    const completion = await groq.chat.completions.create({
      messages: messages,
      model: "llama-3.3-70b-versatile",
      temperature: 0.7,
      max_tokens: 700,
      top_p: 0.9,
      frequency_penalty: 0.3,
      presence_penalty: 0.3,
      stop: ["According to", "Based on", "The context says", "In the context"],
    });

    const answer = completion.choices[0]?.message?.content || "No response generated";
    
    console.log(`💬 LLM Response: "${answer.substring(0, 150)}..."`);
    
    // 8️⃣ Check if RAG failed - MORE STRICT NOW
    const noInfoPhrases = [
      "i don't have enough information",
      "i don't have that information",
      "no information available",
      "cannot find information",
      "not available in the context",
      "don't have access to",
      "doesn't contain",
      "doesn't have",
      "i cannot provide",
      "i'm unable to",
      "i don't know",
      "i'm not sure",
      "my database doesn't have",
      "i don't have details"
    ];
    
    const hasNoInfo = noInfoPhrases.some(phrase => 
      answer.toLowerCase().includes(phrase)
    );
    
    // Check if answer is too short/generic
    const answerWordCount = answer.split(/\s+/).length;
    const isGenericAnswer = answerWordCount < 20;
    
    // ⚠️ CRITICAL: If RAG says no info, TRIGGER SCRAPER
    if ((hasNoInfo || isGenericAnswer) && !skip_scraping) {
      console.log(`⚠️ RAG says no info or generic answer → triggering scraper`);
      
      // Check if scraper is already running
      if (scrapingInProgress.has(scrapingKey)) {
        const startTime = scrapingInProgress.get(scrapingKey);
        const elapsedSeconds = (Date.now() - startTime) / 1000;
        
        return res.json({
          answer: `⏳ Still searching the web... (${elapsedSeconds.toFixed(0)}s elapsed)`,
          session_id: session_id,
          scraping_in_progress: true,
          elapsed_seconds: elapsedSeconds.toFixed(0)
        });
      }
      
      // Trigger scraper and stop here
      return triggerScraperAndRespond(query, session_id, scrapingKey, res, "rag_no_info");
    }

    // 9️⃣ Store assistant response
    await ChatSession.create({
      session_id,
      role: "assistant",
      message: answer,
    });

    // 🔟 Return RAG response
    res.json({
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
      context_reason: contextDecision.reason,
      enhanced_query: queryForEmbedding,
      session_id: session_id,
      source: "rag"
    });

  } catch (err) {
    console.error("Error in handleQuery:", err);
    res.status(500).json({ error: "Internal server error" });
  }
};

async function triggerScraperWithCallback(query, session_id, scrapingKey) {
  try {
    console.log(`📡 Calling scraper API: ${PYTHON_SCRAPER_URL}`);
    
    const response = await axios.post(PYTHON_SCRAPER_URL, {
      query: query,
      session_id: session_id
    }, { 
      timeout: 120000,
      headers: {
        'Content-Type': 'application/json'
      }
    });

    console.log(`✅ Scraper completed:`, {
      status: response.status,
      data: response.data
    });
    
    let finalMessage = "";
    
    if (response.data.message === 'No new results found' || response.data.new_urls === 0) {
      console.log(`⚠️ Scraper found NO new data`);
      finalMessage = "❌ I couldn't find relevant information on the web for your query. Please try rephrasing your question.";
    } else {
      console.log(`✅ Scraper found ${response.data.new_urls} new URLs`);
      finalMessage = "✅ I've searched the web and found new information. Please ask your question again for the updated answer.";
    }
    
    // Update the chat session with the final message
    await ChatSession.create({
      session_id,
      role: "assistant",
      message: finalMessage,
    });
    
  } catch (error) {
    console.error(`❌ Scraper failed:`, {
      message: error.message,
      code: error.code,
      response: error.response?.data
    });
    
    await ChatSession.create({
      session_id,
      role: "assistant",
      message: "❌ Web search encountered an error. Please try again.",
    });
    
  } finally {
    // Always remove from in-progress map
    scrapingInProgress.delete(scrapingKey);
    console.log(`🗑️ Removed ${scrapingKey} from scrapingInProgress`);
  }
}

function cosineSimilarity(a, b) {
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) {
    console.error(`❌ Invalid vectors: a=${a?.length}, b=${b?.length}`);
    return 0;
  }
  const dot = a.reduce((sum, val, i) => sum + val * b[i], 0);
  const normA = Math.sqrt(a.reduce((sum, val) => sum + val * val, 0));
  const normB = Math.sqrt(b.reduce((sum, val) => sum + val * val, 0));
  
  if (normA === 0 || normB === 0) {
    return 0;
  }
  
  const similarity = dot / (normA * normB);
  
  // Handle floating point issues
  if (similarity < 0) return 0;
  if (similarity > 1) return 1;
  
  return similarity;
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

// ✅ Debug endpoint to check scraper status
export const getScraperStatus = async (req, res) => {
  try {
    const { session_id, query } = req.query;
    
    if (!session_id || !query) {
      return res.status(400).json({ error: "session_id and query are required" });
    }
    
    const scrapingKey = `${session_id}:${query.toLowerCase().trim()}`;
    const isInProgress = scrapingInProgress.has(scrapingKey);
    
    let elapsed = 0;
    if (isInProgress) {
      const startTime = scrapingInProgress.get(scrapingKey);
      elapsed = (Date.now() - startTime) / 1000;
    }
    
    res.json({
      scraping_in_progress: isInProgress,
      elapsed_seconds: elapsed.toFixed(0),
      scraping_key: scrapingKey,
      total_active_scrapes: scrapingInProgress.size
    });
  } catch (err) {
    console.error("Error in getScraperStatus:", err);
    res.status(500).json({ error: "Failed to get scraper status" });
  }
};