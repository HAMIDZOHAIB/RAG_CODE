// queryController.js — Advanced RAG Controller (Fixed: memory, follow-up context, frontend display)
import axios from "axios";
import Groq from "groq-sdk";
import WebsiteData from "../../models/websitedata.js";
import ChatSession from "../../models/ChatSession.js";
import { saveMcqsToFile } from "../controllers/Mcqhandler.js";
import { exportMcqsToExcel } from "../controllers/exportMcqsToExcel.js";
import fs from "fs";

import path  from "path";
import { fileURLToPath } from "url";

const TOP_K = 5;
const SIMILARITY_THRESHOLD = 0.35;

// Lower threshold for simple factual/follow-up queries
// These often match weakly against webpage chunks but the answer IS there
const SIMILARITY_THRESHOLD_RELAXED = 0.20;
const EMBEDDING_API_URL     = process.env.EMBEDDING_API_URL || "http://localhost:5000/embed";
const EMBEDDING_API_TIMEOUT = 5000;
const PYTHON_SCRAPER_URL    = process.env.PYTHON_SCRAPER_URL || "http://localhost:8000/scrape";

const scrapingInProgress = new Map();
const activeRequests     = new Map();

// ── Cache: store last successful answer + its links per session ──────────────
const sessionAnswerCache = new Map(); // session_id → { answer, links, topics, timestamp }

const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });

// ─────────────────────────────────────────────────────────────────────────────
// 1. INTENT CLASSIFIER
// ─────────────────────────────────────────────────────────────────────────────
function classifyIntent(query, conversationHistory) {
  const q   = query.trim();
  const ql  = q.toLowerCase();
  const hasHistory = conversationHistory.length > 0;

  // ── Link / URL request ────────────────────────────────────────────────────
  const linkPatterns = [
    /\b(give|show|share|send|provide|get|what('?s| is)?)\s+(me\s+)?(the\s+)?(link|url|website|site|address|href|web address)(es|s)?\b/i,
    /\b(link|url|website|site)(s)?\s+(of|for|to)\s+(the(se|m)?\b|those|above|it|them)\b/i,
    /\b(their|its)\s+(link|url|website|site)\b/i,
    /^(link|url|website|site|links|urls|websites|sites)\s*\??$/i,
    /\b(where can i (find|access|visit|go))\b/i,
    /\bweb\s*site\s*(link|url|address)\b/i,
    /\b(official|actual|real)\s+(link|url|website|site)\b/i,
    /\bgive.+(link|url|website|site)\b/i,
    /\b(link|url|website|site).+(of these|of those|of them|mentioned|above|listed)\b/i,
  ];
  if (linkPatterns.some(p => p.test(ql))) return "link_request";

  // ── MCQ / quiz ────────────────────────────────────────────────────────────
  const mcqPatterns = [
    /^[a-d]\)/i, /^[a-d]\./i,
    /\b(option [a-d]|choice [a-d])\b/i,
    /\b(select|choose)\s+(the\s+)?(correct|right|best)\b/i,
    /which of the following/i,
    /all of the above|none of the above/i,
    /^(true|false)[\s:]/i,
    /^(q\d+|question \d+|\d+[\.\):])/i,
  ];
  if (mcqPatterns.some(p => p.test(ql))) return "mcq";

  // ── Explicit scrape intent ────────────────────────────────────────────────
  const scrapePatterns = [
    /\b(scrape|crawl|fetch|grab|extract)\b/i,
    /\b(related\s+website|related\s+site|related\s+web)\b/i,
  ];
  if (scrapePatterns.some(p => p.test(ql))) return "scrape_intent";

  // ── Clarification / elaboration ───────────────────────────────────────────
  const clarifyPatterns = [
    /^(tell me more|explain (more|further|that|this)|elaborate|go on|continue|more details?|more info)\b/i,
    /\b(what do you mean|can you clarify|i don'?t understand|can you elaborate)\b/i,
  ];
  if (hasHistory && clarifyPatterns.some(p => p.test(ql))) return "clarification";

  // ── Pronoun-based follow-up ───────────────────────────────────────────────
  const followUpPatterns = [
    /^(it|this|that|these|those|they|them|its|their)\s/i,
    /\b(it|this|that|these|those|they|them)\s+(is|are|was|were|has|have|do|does)\b/i,
    /^(why|how|when|where|what)\s+(is|are|do|does|can|should)\s+(it|this|that|these|those)\b/i,
    /\b(the same|the above|aforementioned|mentioned|listed)\b/i,
    /\b(not (the )?(right|correct|official)|wrong|another|different)\b/i,
  ];
  if (hasHistory && followUpPatterns.some(p => p.test(ql))) return "follow_up";

  // ── New topic indicators ──────────────────────────────────────────────────
  const newTopicPatterns = [
    /^(tell me about|what is|who is|explain|describe)\s(?!it|this|that|the link|the website)/i,
    /^(search for|find|look up)\s(?!it|this|that|the link|the website)/i,
    /^(list|show me|give me)\s(all\s)?(website|site|company|service|tool|platform)/i,
  ];
  if (newTopicPatterns.some(p => p.test(ql))) return "independent";

  // ── Repeated query detection ───────────────────────────────────────────────
  // FIX: If the exact same query was already asked recently, treat as independent
  // so it gets a CLEAN embedding (no history noise) and scores well against DB.
  // Without this, "capital of sweden" asked twice gets enriched with its own
  // prior answer, lowering cosine similarity below threshold → scraper fires.
  const questionWords = /^(what|who|how|why|when|where|which|tell|give|show|find|search|explain|describe|list)\b/i;
  const wordCount = q.split(/\s+/).length;

  if (hasHistory) {
    const recentUserQueries = conversationHistory
      .filter(m => m.role === 'user')
      .slice(-4)
      .map(m => m.content.toLowerCase().trim());
    if (recentUserQueries.includes(ql)) {
      console.log(`🔁 Repeated query "${q}" → independent (clean embed, no history noise)`);
      return "independent";
    }
  }

  if (wordCount <= 3 && !questionWords.test(q)) {
    if (hasHistory) {
      // Short new query with history = follow_up continuation
      // e.g. "capital of pakistan", "capital of france" → "finland"
      console.log(`🔗 Short query "${q}" with history → follow_up for context enrichment`);
      return "follow_up";
    }
    return "entity_switch";
  }

  // ── Default ────────────────────────────────────────────────────────────────
  if (hasHistory && wordCount <= 6) return "follow_up";
  return "independent";
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. EXTRACT LINKS FROM PRIOR ASSISTANT MESSAGES
// ─────────────────────────────────────────────────────────────────────────────
function extractLinksFromHistory(conversationHistory) {
  const urlRegex = /https?:\/\/[^\s"',\)>]+/gi;
  const links = [];
  for (let i = conversationHistory.length - 1; i >= 0; i--) {
    const msg = conversationHistory[i];
    if (msg.role === 'assistant') {
      const found = msg.content.match(urlRegex);
      if (found) links.push(...found);
    }
  }
  return [...new Set(links)];
}

function extractTopicsFromHistory(conversationHistory) {
  return conversationHistory
    .filter(m => m.role === 'user')
    .slice(-6)
    .map(m => m.content)
    .join(' | ');
}

// ─────────────────────────────────────────────────────────────────────────────
// 3. ENTITY EXTRACTION & MISMATCH DETECTION
// ─────────────────────────────────────────────────────────────────────────────
function extractQueryEntities(query) {
  const normalized = query.trim().toLowerCase();
  const entities   = new Set();

  const quoted = query.match(/["']([^"']{3,})["']/g);
  if (quoted) quoted.forEach(q => entities.add(q.replace(/["']/g, '').toLowerCase()));

  const namedMatch = query.match(
    /(?:about|who is|tell me about|search for|find|regarding|on)\s+([A-Za-z\u0600-\u06FF][\w\s\-\u0600-\u06FF]{2,40})/i
  );
  if (namedMatch) entities.add(namedMatch[1].trim().toLowerCase());

  const genericWords = new Set(['what','who','when','where','how','tell','give','show',
                                 'find','search','about','please','the','and','for','me',
                                 'those','these','that','this','them','their','its','list',
                                 'provide','website','websites','site','sites','link','links']);
  const multiWord = query.match(/\b([A-Za-z\u0600-\u06FF]{2,}(?:\s+[A-Za-z\u0600-\u06FF]{2,}){1,4})\b/g);
  if (multiWord) {
    multiWord.forEach(phrase => {
      const cleaned = phrase.trim().toLowerCase();
      const words   = cleaned.split(' ');
      if (words.length >= 2 && !words.some(w => genericWords.has(w))) {
        entities.add(cleaned);
      }
    });
  }

  if (normalized.split(' ').length >= 2) entities.add(normalized);
  return [...entities];
}

function entityFoundInContext(query, topChunks) {
  // BUG FIX: extractQueryEntities only extracts 2+ word phrases.
  // Single-word queries like "finland" return entities=[] → always returns true.
  // Fix: always also check the raw query word(s) directly against chunk text.
  const entities = extractQueryEntities(query);

  // Add individual meaningful words from the query (length > 3 to skip "of", "the", etc.)
  const rawWords = query.trim().toLowerCase().split(/\s+/).filter(w => w.length > 3);
  const allEntities = [...new Set([...entities, ...rawWords])];

  if (allEntities.length === 0) return true;

  const allChunkText = topChunks
    .map(c => (c.row.plain_text || '').toLowerCase())
    .join(' ');

  const matched = allEntities.filter(e => allChunkText.includes(e));
  const found   = matched.length > 0;

  if (!found) {
    console.log(`🚨 Entity mismatch! Entities: [${allEntities.join(', ')}]`);
    console.log(`   Sources: ${topChunks.map(c => c.row.website_link).join(', ')}`);
  } else {
    console.log(`✅ Entity match: [${matched.join(', ')}]`);
  }
  return found;
}

// ─────────────────────────────────────────────────────────────────────────────
// 4. EMBEDDING QUERY BUILDER
// FIX: Short follow-up queries now get enriched with conversation history
// so "finland" after capitals discussion embeds as a proper contextual query
// ─────────────────────────────────────────────────────────────────────────────
function buildEmbeddingQuery(query, intent, conversationHistory) {
  const questionWords = /^(what|who|how|why|when|where|which|tell|give|show|find|search|explain|describe|list)\b/i;
  const wordCount = query.trim().split(/\s+/).length;
  const isShortQuery = wordCount <= 3 && !questionWords.test(query.trim());

  // For link requests: embed the TOPIC from history, not "give me the link"
  if (intent === 'link_request' && conversationHistory.length > 0) {
    const recentUserMsgs = conversationHistory
      .filter(m => m.role === 'user')
      .slice(-3)
      .map(m => m.content);
    const lastTopic = recentUserMsgs.reverse().find(m =>
      !/(link|url|website|site)/i.test(m)
    );
    if (lastTopic) {
      console.log(`🔗 Link request → embedding last topic: "${lastTopic}"`);
      return lastTopic;
    }
  }

  // FIX: Short queries (like "finland") with history ALWAYS get enriched
  // Previously had `&& !isShortEntity` which blocked enrichment — now removed
  if (intent === 'follow_up' || intent === 'clarification' || isShortQuery) {
    if (conversationHistory.length > 0) {
      // FIX: Do NOT enrich if the current query already appeared in recent history.
      // Enriching "capital of sweden" with its own prior answer creates noise that
      // lowers cosine similarity below threshold → triggers unnecessary scraping.
      const recentUserQueries = conversationHistory
        .filter(m => m.role === 'user')
        .slice(-4)
        .map(m => m.content.toLowerCase().trim());
      const isRepeatedQuery = recentUserQueries.includes(query.toLowerCase().trim());

      if (isRepeatedQuery) {
        console.log(`🔁 Repeated query in follow_up → clean embed (no enrichment)`);
        return query;
      }

      // Build context-aware enriched query for genuine follow-ups
      // e.g. "capital of pakistan", "capital of france" → "finland" = "capital of finland"
      const recentHistory = conversationHistory.slice(-6);
      const userMessages  = recentHistory
        .filter(m => m.role === 'user')
        .map(m => m.content);
      const assistantMessages = recentHistory
        .filter(m => m.role === 'assistant')
        .slice(-2)
        .map(m => m.content.substring(0, 200));

      const patternContext = [...userMessages, ...assistantMessages].join(' ');
      const enriched = `${patternContext} ${query}`;

      console.log(`🔗 Enriched embedding query: "${enriched.substring(0, 100)}..."`);
      return enriched;
    }
  }

  console.log(`🔍 Clean embedding for intent: ${intent}`);
  return query;
}

// ─────────────────────────────────────────────────────────────────────────────
// 5. BUILD DEEP CONTEXT
// ─────────────────────────────────────────────────────────────────────────────
function buildDeepContext(conversationHistory) {
  const recent        = conversationHistory.slice(-15);
  const lastAssistant = [...recent].reverse().find(m => m.role === 'assistant');
  const fullConversation = recent
    .map(m => `${m.role === 'user' ? '👤 User' : '🤖 Assistant'}: ${m.content}`)
    .join('\n');
  return { lastAssistant, fullConversation };
}

// ─────────────────────────────────────────────────────────────────────────────
// 6. SYSTEM PROMPT BUILDER
// ─────────────────────────────────────────────────────────────────────────────
function buildSystemPrompt({ intent, query, contextText, websiteLinks, conversationHistory, skip_scraping, sessionCache }) {
  const { lastAssistant, fullConversation } = buildDeepContext(conversationHistory);
  const linkList = websiteLinks.map((l, i) => `${i+1}. ${l}`).join('\n');

  // ── POST-SCRAPE: trust fresh data ──────────────────────────────────────────
  if (skip_scraping) {
    return `You are a helpful assistant. Fresh data was just scraped for this query.

DATABASE CONTEXT (just scraped):
${contextText}

AVAILABLE LINKS:
${linkList}

RULES:
1. Answer directly from the DATABASE CONTEXT
2. If the user asked for links/websites, list them as clickable URLs
3. Answer in 2-4 sentences
4. Do NOT say "I need to search" — searching was just done
5. Never use "According to the context" phrases`;
  }

  // ── LINK REQUEST ───────────────────────────────────────────────────────────
  if (intent === 'link_request') {
    // FIX: Only use sessionCache links if the cached topic is still relevant.
    // historyLinks (extracted from actual assistant message text) are always safe
    // because they come from the real content of prior answers.
    const historyLinks = extractLinksFromHistory(conversationHistory);
    const cachedTopic  = (sessionCache?.lastTopic || '').toLowerCase();
    const recentTopics = conversationHistory
      .filter(m => m.role === 'user').slice(-3)
      .map(m => m.content.toLowerCase()).join(' ');
    const cacheRelevant = cachedTopic && recentTopics.includes(cachedTopic.split(' ')[0]);
    const cachedLinks  = cacheRelevant ? (sessionCache?.links || []) : [];
    const allLinks     = [...new Set([...cachedLinks, ...historyLinks, ...websiteLinks])];

    if (allLinks.length > 0) {
      return `You are a helpful assistant.

The user is asking for website links related to the previous topic.

LINKS FOUND:
${allLinks.map((l, i) => `${i+1}. ${l}`).join('\n')}

PREVIOUS ASSISTANT ANSWER:
${lastAssistant ? lastAssistant.content : "None"}

DATABASE CONTEXT (additional):
${contextText}

RULES:
1. List ALL relevant links above in a numbered format
2. Briefly describe what each website is about (1 short sentence each)
3. Do NOT say "I need to search" — the links are already available
4. Do NOT say links are unavailable if they are listed above`;
    }

    return `You are a helpful assistant.

DATABASE CONTEXT:
${contextText}

AVAILABLE LINKS:
${linkList}

RULES:
1. The user wants website links. Extract and list all URLs from DATABASE CONTEXT
2. Present them in a numbered list with a brief description of each
3. If no links are in the context, say: "I need to search for more information on this topic"`;
  }

  // ── CLARIFICATION ──────────────────────────────────────────────────────────
  if (intent === 'clarification') {
    return `You are a helpful assistant.

CONVERSATION HISTORY:
${fullConversation}

YOUR LAST ANSWER:
${lastAssistant ? lastAssistant.content : "None"}

DATABASE CONTEXT:
${contextText}

AVAILABLE LINKS:
${linkList}

RULES:
1. Elaborate on your last answer using DATABASE CONTEXT
2. Add more details the user is asking for
3. Do NOT repeat your last answer verbatim — extend it
4. Answer in 3-5 sentences`;
  }

  // ── FOLLOW-UP ──────────────────────────────────────────────────────────────
  if (intent === 'follow_up') {
    return `You are a strict RAG assistant with conversation memory.

FULL CONVERSATION HISTORY:
${fullConversation}

YOUR LAST ANSWER:
${lastAssistant ? lastAssistant.content : "None"}

DATABASE CONTEXT:
${contextText}

AVAILABLE LINKS:
${linkList}

CURRENT USER QUERY: "${query}"

RULES:
1. Use CONVERSATION HISTORY to understand what the user is referring to.
   - Example: if prior msgs asked about capitals of countries and user now says "finland",
     understand they are asking about the capital of Finland.
2. Answer ONLY from DATABASE CONTEXT
3. If the queried entity is NOT in DATABASE CONTEXT → say EXACTLY: "I need to search for more information on this topic"
4. Use conversation history ONLY to resolve what the user means — not to invent facts
5. If user asks for links, list them from AVAILABLE LINKS section
6. Answer in 2-4 sentences`;


  }

  // ── ENTITY SWITCH ──────────────────────────────────────────────────────────
  if (intent === 'entity_switch') {
    return `You are a helpful assistant. Answer ONLY from the DATABASE CONTEXT below.

DATABASE CONTEXT (retrieved for: "${query}"):
${contextText}

AVAILABLE LINKS:
${linkList}

RULES:
1. Answer ONLY about "${query}" from DATABASE CONTEXT
2. Do NOT assume the user is asking about the previous topic
3. If "${query}" is NOT in DATABASE CONTEXT → say EXACTLY: "I need to search for more information on this topic"
4. Answer in 2-3 sentences`;
  }

  // ── INDEPENDENT / DEFAULT ──────────────────────────────────────────────────
  return `You are a strict RAG assistant. Answer ONLY from the DATABASE CONTEXT.

DATABASE CONTEXT:
${contextText}

AVAILABLE LINKS:
${linkList}

RULES:
1. Answer ONLY from DATABASE CONTEXT — never use training knowledge
2. If the user asks for websites/links, list them from AVAILABLE LINKS
3. If the queried entity is NOT in DATABASE CONTEXT → say EXACTLY: "I need to search for more information on this topic"
4. Answer in 2-4 sentences. No "According to the context" phrases`;
}

// ─────────────────────────────────────────────────────────────────────────────
// 7. SAFE DB SAVE HELPER
// FIX: Centralized save function prevents duplicate saves and makes flow clear
// ─────────────────────────────────────────────────────────────────────────────
async function saveMessage(session_id, role, message) {
  try {
    await ChatSession.create({ session_id, role, message });
  } catch (e) {
    console.error(`⚠️ DB save error (${role}):`, e.message);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// 8. MAIN HANDLER
// FIX: User message saved only ONCE per request, answer always returned to frontend
// ─────────────────────────────────────────────────────────────────────────────
// ─── ADD THIS IMPORT at the top of your controller ───────────────────────────
// const { saveMcqsToFile } = require("./mcqHandler");
// ─────────────────────────────────────────────────────────────────────────────

// ← ONLY NEW IMPORT ADDED

export const handleQuery = async (req, res) => {
  const startTime = Date.now();

  let userMessageSaved = false;

  const saveUserMessage = async (session_id, query) => {
    if (!userMessageSaved) {
      await saveMessage(session_id, "user", query);
      userMessageSaved = true;
    }
  };

  try {
    const { session_id, query, skip_scraping, check_similarity_only } = req.body;

    if (!session_id || !query) {
      return res.status(400).json({ error: "session_id and query are required",
                                    is_sufficient: false, similarity_score: 0 });
    }

    const scrapingKey = `${session_id}:${query.toLowerCase().trim()}`;

    if (!check_similarity_only && activeRequests.has(scrapingKey)) {
      console.log(`⚠️ Duplicate blocked: "${query}"`);
      return res.status(429).json({ error: "Request already in progress",
                                    is_sufficient: false, similarity_score: 0 });
    }

    if (!check_similarity_only) {
      activeRequests.set(scrapingKey, Date.now());
      console.log(`\n${'━'.repeat(50)}`);
      console.log(`📝 REQUEST: "${query}" | skip_scraping=${skip_scraping}`);
      console.log(`${'━'.repeat(50)}`);
    }

    // ── Fetch history ──────────────────────────────────────────────────────
    let sessionMessages = [];
    try {
      sessionMessages = await ChatSession.findAll({
        where: { session_id },
        order: [["createdAt", "ASC"]],
        limit: 20
      });
    } catch (e) {
      console.error("❌ DB error fetching history:", e);
      activeRequests.delete(scrapingKey);
      return res.status(500).json({ error: "Database error", is_sufficient: false, similarity_score: 0 });
    }

    const conversationHistory = sessionMessages
      .map(m => ({ role: m.role, content: m.message }))
      .filter(m => !m.content.includes('🔍') && !m.content.includes('⏳') &&
                   !m.content.includes('❌') && !m.content.includes('✅ Found new'));

    console.log(`📚 History: ${conversationHistory.length} messages`);

    // ── Classify intent ────────────────────────────────────────────────────
    const intent = classifyIntent(query, conversationHistory);
    console.log(`🎯 Intent: ${intent}`);

    // ── Session cache ──────────────────────────────────────────────────────
    const sessionCache = sessionAnswerCache.get(session_id) || null;

    // ── LINK REQUEST: if we have cached links, answer immediately ──────────
    if (intent === 'link_request' && !skip_scraping) {
      const historyLinks = extractLinksFromHistory(conversationHistory);

      const lastUserTopic = conversationHistory
        .filter(m => m.role === 'user')
        .slice(-3)
        .map(m => m.content)
        .join(' ')
        .toLowerCase();

      const cachedTopic = (sessionCache?.lastTopic || '').toLowerCase();

      const recentMsgCount = conversationHistory.length;
      const cacheIsRecent  = sessionCache &&
        (recentMsgCount <= 4 || lastUserTopic.includes(cachedTopic.split(' ')[0]));

      const cachedLinks = cacheIsRecent ? (sessionCache?.links || []) : [];
      const allLinks    = [...new Set([...cachedLinks, ...historyLinks])];

      if (allLinks.length > 0) {
        console.log(`🔗 Link request answered from cache/history (${allLinks.length} links)`);

        const { lastAssistant } = buildDeepContext(conversationHistory);

        const llmMessages = [
          {
            role: "system",
            content: `You are a helpful assistant. The user wants website links from the previous conversation.

PREVIOUSLY FOUND LINKS:
${allLinks.map((l, i) => `${i+1}. ${l}`).join('\n')}

PREVIOUS ANSWER:
${lastAssistant ? lastAssistant.content : "None"}

TASK: List each link in a numbered format and add a short 1-sentence description of what each site does (based on the previous answer context or the URL itself).
Do NOT say links are unavailable. Do NOT say "I need to search".`
          },
          { role: "user", content: query }
        ];

        let linkAnswer;
        try {
          const completion = await groq.chat.completions.create({
            messages: llmMessages, model: "llama-3.3-70b-versatile",
            temperature: 0.3, max_tokens: 500, top_p: 0.9
          });
          linkAnswer = completion.choices[0]?.message?.content;
        } catch (e) {
          console.error("⚠️ LLM error for link request:", e.message);
        }

        if (!linkAnswer) {
          linkAnswer = `Here are the links from our previous conversation:\n\n` +
            allLinks.map((l, i) => `${i+1}. ${l}`).join('\n');
        }

        await saveUserMessage(session_id, query);
        await saveMessage(session_id, "assistant", linkAnswer);

        activeRequests.delete(scrapingKey);
        return res.json({
          answer: linkAnswer,
          website_links: allLinks,
          context_used: true,
          session_id,
          is_sufficient: true,
          similarity_score: 1.0,
          scraping_in_progress: false,
          scraping_started: false
        });
      }
      console.log(`⚠️ Link request but no cache — falling through to search`);
    }

    // ── Build embedding query ──────────────────────────────────────────────
    const queryForEmbedding = buildEmbeddingQuery(query, intent, conversationHistory);

    // ── Generate embedding ─────────────────────────────────────────────────
    let queryEmbedding;
    try {
      const embedResp = await axios.post(EMBEDDING_API_URL,
        { text: queryForEmbedding }, { timeout: EMBEDDING_API_TIMEOUT });
      if (!embedResp.data?.embedding) throw new Error("Invalid embedding response");
      queryEmbedding = embedResp.data.embedding;
      console.log(`🧠 Embedding: ${queryEmbedding.length} dims`);
    } catch (e) {
      activeRequests.delete(scrapingKey);
      if (e.code === 'ECONNREFUSED')
        return res.status(503).json({ error: "Embedding service down", is_sufficient: false, similarity_score: 0 });
      return res.status(500).json({ error: "Embedding failed: " + e.message, is_sufficient: false, similarity_score: 0 });
    }

    // ── Fetch + score DB chunks ────────────────────────────────────────────
    let allChunks;
    try { allChunks = await WebsiteData.findAll(); }
    catch (e) {
      activeRequests.delete(scrapingKey);
      return res.status(500).json({ error: "DB error", is_sufficient: false, similarity_score: 0 });
    }

    if (allChunks.length === 0) {
      if (scrapingInProgress.has(scrapingKey)) {
        const elapsed = ((Date.now() - scrapingInProgress.get(scrapingKey)) / 1000).toFixed(0);
        activeRequests.delete(scrapingKey);
        return res.json({ answer: `⏳ Still searching... (${elapsed}s)`, session_id,
                          scraping_in_progress: true, is_sufficient: false, similarity_score: 0 });
      }

      console.log(`📭 DB is empty — triggering scraper for: "${query}"`);
      scrapingInProgress.set(scrapingKey, Date.now());

      await saveUserMessage(session_id, query);
      await saveMessage(session_id, "assistant", "🔍 Searching the web...");

      triggerScraperWithCallback(query, session_id, scrapingKey);
      activeRequests.delete(scrapingKey);

      return res.json({
        answer: "🔍 Searching the web for information...",
        session_id,
        scraping_started: true,
        is_sufficient: false,
        similarity_score: 0
      });
    }

    const parseEmbedding = (val) => {
      if (Array.isArray(val)) return val;
      if (typeof val === 'string') {
        try {
          return JSON.parse(val);
        } catch {
          return null;
        }
      }
      return null;
    };

    const scoredChunks = allChunks
      .map(r => {
        const embedding = parseEmbedding(r.embedding);
        return embedding ? { row: r, score: cosineSimilarity(queryEmbedding, embedding) } : null;
      })
      .filter(i => i !== null && !isNaN(i.score));

    if (scoredChunks.length === 0) {
      activeRequests.delete(scrapingKey);
      return res.status(500).json({ error: "No valid embeddings", is_sufficient: false, similarity_score: 0 });
    }

    const topChunks = scoredChunks.sort((a, b) => b.score - a.score).slice(0, TOP_K);
    const maxScore  = topChunks[0]?.score || 0;
    console.log(`📊 Similarity: ${(maxScore * 100).toFixed(2)}%`);

    if (check_similarity_only) {
      activeRequests.delete(scrapingKey);
      return res.json({
        max_similarity: (maxScore * 100).toFixed(2) + "%",
        similarity_score: maxScore,
        is_sufficient: maxScore >= SIMILARITY_THRESHOLD_RELAXED,
        scraping_in_progress: scrapingInProgress.has(scrapingKey),
        session_id
      });
    }

    // ── Scrape decision ────────────────────────────────────────────────────
    const userWantsScrape = intent === 'scrape_intent';

    const effectiveThreshold = (intent === 'follow_up' || intent === 'clarification')
      ? SIMILARITY_THRESHOLD_RELAXED
      : SIMILARITY_THRESHOLD;

    console.log(`📐 Threshold: ${effectiveThreshold} (intent=${intent}), score=${maxScore.toFixed(3)}`);

    const skipScrapingAtThreshold = ['link_request', 'follow_up', 'clarification'].includes(intent);

    const needsScrape = !skipScrapingAtThreshold && (
      maxScore < effectiveThreshold ||
      userWantsScrape
    );

    if (needsScrape && !skip_scraping) {
      if (scrapingInProgress.has(scrapingKey)) {
        const elapsed = ((Date.now() - scrapingInProgress.get(scrapingKey)) / 1000).toFixed(0);
        activeRequests.delete(scrapingKey);
        return res.json({ answer: `⏳ Still searching... (${elapsed}s)`, session_id,
                          scraping_in_progress: true, is_sufficient: false, similarity_score: maxScore });
      }

      console.log(`🔍 Pre-LLM scrape triggered (score=${(maxScore*100).toFixed(1)}%, intent=${intent})`);
      scrapingInProgress.set(scrapingKey, Date.now());

      await saveUserMessage(session_id, query);
      await saveMessage(session_id, "assistant", "🔍 Searching the web...");

      triggerScraperWithCallback(query, session_id, scrapingKey);
      activeRequests.delete(scrapingKey);

      return res.json({
        answer: "🔍 Searching the web for information...",
        session_id,
        scraping_started: true,
        is_sufficient: false,
        similarity_score: maxScore
      });
    }

    // ── Build LLM context ──────────────────────────────────────────────────
    const relevantChunks = topChunks.map(c => c.row);
    const websiteLinks   = [...new Set(relevantChunks.map(c => c.website_link))];
    const contextText    = relevantChunks
      .map((c, i) => `[Source ${i+1}] ${c.website_link}\n${c.plain_text.substring(0, 800)}`)
      .join("\n\n");

    // ── Build system prompt ────────────────────────────────────────────────
    const systemPrompt = buildSystemPrompt({
      intent, query, contextText, websiteLinks,
      conversationHistory, skip_scraping, sessionCache
    });

    // ── Build LLM messages ─────────────────────────────────────────────────
    const messages = [
      { role: "system", content: systemPrompt },
      ...conversationHistory.slice(-10),
      { role: "user",   content: query },
    ];

    if (!skip_scraping) {
      await saveUserMessage(session_id, query);
    }

    // ── Call LLM ───────────────────────────────────────────────────────────
    let answer;
    try {
      const completion = await groq.chat.completions.create({
        messages,
        model: "llama-3.3-70b-versatile",
        temperature: 0.4,
        max_tokens: 400,
        top_p: 0.9
      });
      answer = completion.choices[0]?.message?.content;
      console.log(`💬 Raw LLM answer: "${answer?.substring(0, 120)}..."`);
    } catch (e) {
      activeRequests.delete(scrapingKey);
      return res.status(500).json({ error: "LLM error: " + e.message,
                                    is_sufficient: false, similarity_score: maxScore });
    }

    if (!answer || answer.trim() === '') {
      answer = "I wasn't able to generate a response. Please try rephrasing your question.";
      console.warn("⚠️ LLM returned empty answer, using fallback");
    }

    // ── MCQ DETECTION & SAVE ───────────────────────────────────────────────
    // Detects if the LLM answer looks like MCQs and silently appends to Mcqs.json.
    // Does NOT change `answer` — it displays on screen exactly as before.
    // Does NOT affect any other logic below.
  // ── MCQ DETECTION & SAVE ───────────────────────────────────────────────────
// ── MCQ DETECTION & SAVE ───────────────────────────────────────────────────
// FIXES:
//   1. Parser now extracts the Assessment block per question
//   2. Second LLM call rewrites assessment as a plain paragraph
//   3. saveMcqsToFile() now receives { question, options, answer, assessment }
// ──────────────────────────────────────────────────────────────────────────
try {
  const isMcqAnswer =
    /Q\d+[\.\):]|Question\s*\d+[\.\):]|\d+[\.\)]\s+.{10,}/i.test(answer) &&
    /\b[A-D][\.\)]\s+/i.test(answer);

  console.log("🧩 isMcqAnswer:", isMcqAnswer);

  if (isMcqAnswer) {

    // ── STEP 1: Split into per-question blocks ─────────────────────────────
    const blocks = answer
      .split(/(?=\*{0,2}(?:Q\d+[\.\):\s]|Question\s*\d+[\.\):\s]|\d+[\.\)]\s))/im)
      .map(b => b.trim())
      .filter(Boolean);

    // ── STEP 2: Parse each block ───────────────────────────────────────────
    const parsed = blocks.map(block => {
      const lines = block.split("\n").map(l => l.trim()).filter(Boolean);

      // ── Question text (first line, strip numbering + markdown) ────────────
      const question = lines[0]
        .replace(/^\*{1,2}/, "")
        .replace(/\*{1,2}$/, "")
        .replace(/^(Q\d+[\.\):\s]+|Question\s*\d+[\.\):\s]+|\d+[\.\)]\s+)/i, "")
        .trim();

      const options = { A: null, B: null, C: null, D: null };
      let correct     = null;
      let rawAssessment = "";         // ← NEW: collect raw assessment text
      let inAssessment  = false;      // ← NEW: flag when we're inside Assessment block

      lines.slice(1).forEach(line => {
        // ── Detect Assessment heading ──────────────────────────────────────
        if (/^\*{0,2}Assessment\*{0,2}\s*:?/i.test(line)) {
          inAssessment = true;
          // capture anything after "Assessment:" on the same line
          const inline = line.replace(/^\*{0,2}Assessment\*{0,2}\s*:?\s*/i, "").trim();
          if (inline) rawAssessment += " " + inline;
          return;
        }

        // ── While inside Assessment block, collect lines ───────────────────
        if (inAssessment) {
          rawAssessment += " " + line;
          return;
        }

        // ── Option lines  e.g.  A) text  or  (A) text  or  A. text ─────────
        const opt = line.match(/^[\(\[]?([A-Da-d])[\)\]\.\s]+(.+)/);
        if (opt) {
          options[opt[1].toUpperCase()] = opt[2]
            .replace(/\*{1,2}/g, "")
            .trim();
          return;
        }

        // ── Answer line  e.g.  Answer: C ──────────────────────────────────
        const ans = line.match(/^(answer|ans|correct answer)\s*[:\-]\s*([A-Da-d])/i);
        if (ans) {
          correct = ans[2].toUpperCase();
        }
      });

      return {
        question,
        options,
        answer      : correct,
        rawAssessment: rawAssessment.trim(),   // raw — will be rewritten below
      };
    }).filter(m => m.question && Object.values(m.options).some(Boolean));

    console.log(`🧩 Parsed MCQs: ${parsed.length}`, JSON.stringify(parsed[0] || {}));

    // ── STEP 3: Rewrite each rawAssessment as a plain paragraph ───────────
    // One LLM call rewrites ALL assessments in one shot (cheaper & faster)
    if (parsed.length > 0) {
      let finalParsed = parsed;

      const hasAnyAssessment = parsed.some(m => m.rawAssessment);

      if (hasAnyAssessment) {
        try {
          // Build a numbered list of raw assessments for the LLM to rewrite
          const rawList = parsed
            .map((m, i) =>
              `[${i + 1}] Question: "${m.question.substring(0, 80)}"\n` +
              `    Raw assessment: ${m.rawAssessment || "(none)"}`
            )
            .join("\n\n");

          const rewriteMessages = [
            {
              role: "system",
              content: `You are an assessment writer. You will receive a numbered list of MCQ questions and their raw assessments.
For EACH item, rewrite the assessment as a single, plain, flowing paragraph.

STRICT RULES:
- Output ONLY the rewritten assessments, one per line, prefixed with the same number: [1] text  [2] text etc.
- NO bullet points, NO option labels (A/B/C/D), NO asterisks, NO dashes, NO line breaks inside an assessment
- Each assessment must be ONE continuous paragraph of 2-4 sentences
- Describe what each answer choice reveals about the person's personality/behavior in one unified paragraph
- Do NOT include the question text in your output`
            },
            {
              role: "user",
              content: rawList
            }
          ];

          const rewriteCompletion = await groq.chat.completions.create({
            messages   : rewriteMessages,
            model      : "llama-3.3-70b-versatile",
            temperature: 0.3,
            max_tokens : 800,
            top_p      : 0.9,
          });

          const rewriteRaw = rewriteCompletion.choices[0]?.message?.content || "";
          console.log(`✍️  Rewritten assessments raw: "${rewriteRaw.substring(0, 200)}"`);

          // ── Parse rewrite response: extract [N] paragraph ────────────────
          // Match patterns like [1] some text [2] more text
          const rewriteMap = {};
          const rewriteMatches = [...rewriteRaw.matchAll(/\[(\d+)\]\s*([\s\S]*?)(?=\[\d+\]|$)/g)];
          rewriteMatches.forEach(m => {
            const idx  = parseInt(m[1], 10) - 1;   // 0-based
            const text = m[2]
              .replace(/\n+/g, " ")                 // flatten newlines
              .replace(/\*{1,2}/g, "")              // strip markdown bold
              .replace(/\s{2,}/g, " ")              // collapse spaces
              .trim();
            if (text) rewriteMap[idx] = text;
          });

          // ── Merge rewritten assessments back into parsed objects ──────────
          finalParsed = parsed.map((m, i) => ({
            question  : m.question,
            options   : m.options,
            answer    : m.answer,
            assessment: rewriteMap[i] || m.rawAssessment || null,   // fallback to raw
          }));

          console.log(`✅ Assessment rewrite done. Sample: "${(finalParsed[0]?.assessment || "").substring(0, 100)}"`);

        } catch (rewriteErr) {
          // Rewrite failed — fall back to raw assessment text
          console.warn("⚠️ Assessment rewrite LLM failed, using raw:", rewriteErr.message);
          finalParsed = parsed.map(m => ({
            question  : m.question,
            options   : m.options,
            answer    : m.answer,
            assessment: m.rawAssessment || null,
          }));
        }
      } else {
        // No assessment in LLM output at all — save without it
        finalParsed = parsed.map(m => ({
          question  : m.question,
          options   : m.options,
          answer    : m.answer,
          assessment: null,
        }));
      }

      // ── STEP 4: Save to Mcqs.json ─────────────────────────────────────────
      saveMcqsToFile(finalParsed, session_id, query);
      console.log(`💾 Saved ${finalParsed.length} MCQ(s) with assessments`);
    }
  }
} catch (mcqErr) {
  console.error("⚠️ MCQ save failed:", mcqErr.message);
  import("./path/to/your/stacktrace").catch(() => console.error(mcqErr));
}
// ── END MCQ DETECTION ──────────────────────────────────────────────────────


    // ── Check if LLM says it needs to search ──────────────────────────────
    const noInfoPhrases = [
      "i don't have", "i do not have",
      "no information available", "cannot find", "not available",
      "i need to search for more information",
      "not mentioned", "not provided", "does not mention",
      "does not contain", "no information about",
      "not found in", "not in the provided", "not in the context",
      "context does not", "provided content does not",
    ];

    const hasNoInfo = noInfoPhrases.some(p => answer.toLowerCase().includes(p));

    const entityMatch = entityFoundInContext(query, topChunks);
    if ((hasNoInfo || (!entityMatch && !skip_scraping)) && intent !== 'link_request') {
      if (scrapingInProgress.has(scrapingKey)) {
        const elapsed = ((Date.now() - scrapingInProgress.get(scrapingKey)) / 1000).toFixed(0);
        activeRequests.delete(scrapingKey);
        return res.json({ answer: `⏳ Still searching... (${elapsed}s)`, session_id,
                          scraping_in_progress: true, is_sufficient: false, similarity_score: maxScore });
      }

      console.log("🔍 LLM has no info → triggering scraper");
      scrapingInProgress.set(scrapingKey, Date.now());

      await saveMessage(session_id, "assistant", "🔍 Searching the web...");

      triggerScraperWithCallback(query, session_id, scrapingKey);
      activeRequests.delete(scrapingKey);

      return res.json({
        answer: "🔍 Searching the web for information...",
        session_id,
        scraping_started: true,
        is_sufficient: false,
        similarity_score: maxScore
      });
    }

    // ── Extract links from answer + DB for caching ─────────────────────────
    const urlRegex    = /https?:\/\/[^\s"',\)>]+/gi;
    const answerLinks = answer.match(urlRegex) || [];
    const allLinks    = [...new Set([...answerLinks, ...websiteLinks])];

    // ── Save to session cache ──────────────────────────────────────────────
    const linksToCache = (intent === 'independent' || intent === 'entity_switch')
      ? allLinks
      : [...new Set([...(sessionCache?.links || []), ...allLinks])];

    sessionAnswerCache.set(session_id, {
      lastTopic : query,
      links     : linksToCache,
      answer    : answer,
      timestamp : Date.now(),
    });

    // ── Save assistant answer ──────────────────────────────────────────────
    await saveMessage(session_id, "assistant", answer);

    const elapsed = Date.now() - startTime;
    console.log(`✅ Done in ${elapsed}ms | intent=${intent}`);
    console.log(`${'━'.repeat(50)}\n`);

    res.json({
      answer,
      sources: topChunks.map((c, i) => ({
        id: i+1,
        text: c.row.plain_text.substring(0, 150) + "...",
        score: c.score.toFixed(3),
        website_link: c.row.website_link
      })),
      website_links       : allLinks,
      max_similarity      : (maxScore * 100).toFixed(2) + "%",
      context_used        : true,
      intent_detected     : intent,
      session_id,
      is_sufficient       : true,
      similarity_score    : maxScore,
      scraping_in_progress: false,
      scraping_started    : false
    });

    activeRequests.delete(scrapingKey);

  } catch (err) {
    console.error("❌ UNHANDLED ERROR:", err);
    const key = `${req.body?.session_id}:${req.body?.query?.toLowerCase().trim()}`;
    activeRequests.delete(key);
    res.status(500).json({
      answer: "An error occurred. Please try again.",
      error: "Internal server error: " + err.message,
      is_sufficient: false,
      similarity_score: 0
    });
  }
};

//use for excel sheet export
export const exportMcqs = async (req, res) => {
  try {
    const __filename = fileURLToPath(import.meta.url);
    const __dirname  = path.dirname(__filename);
    const MCQS_FILE  = path.join(__dirname, "Mcqs.json"); // ← define it here

    if (!fs.existsSync(MCQS_FILE)) {
      console.log("❌ Mcqs.json not found at:", MCQS_FILE);
      return res.status(404).json({ error: "No MCQs found. Ask for MCQs first." });
    }

    const data = JSON.parse(fs.readFileSync(MCQS_FILE, "utf8"));
    if (!data.mcqs || data.mcqs.length === 0) {
      return res.status(404).json({ error: "No MCQs found. Ask for MCQs first." });
    }

    const filePath = await exportMcqsToExcel();
    if (!filePath) return res.status(404).json({ error: "Export failed." });

    const today    = new Date().toISOString().slice(0, 10);
    const filename = `MCQS.${today}.xlsx`;

    res.setHeader("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
    res.setHeader("Content-Disposition", `attachment; filename="${filename}"`);

    const fileStream = fs.createReadStream(filePath);
    fileStream.pipe(res);
    fileStream.on("end", () => fs.unlink(filePath, () => {}));

  } catch (err) {
    console.error("❌ Export error:", err);
    res.status(500).json({ error: err.message });
  }
};
// ─────────────────────────────────────────────────────────────────────────────
// SCRAPER TRIGGER
// ─────────────────────────────────────────────────────────────────────────────
async function triggerScraperWithCallback(query, session_id, scrapingKey) {
  try {
    console.log(`🚀 Triggering scraper for: "${query}"`);
    const response = await axios.post(PYTHON_SCRAPER_URL,
      { query, session_id },
      { timeout: 180000, validateStatus: s => s < 600 }
    );
    console.log(`✅ Scraper response (${response.status}):`, response.data);

    const msg = (response.data?.new_urls === 0 || response.data?.message === 'No new results found')
      ? "❌ Couldn't find relevant information. Try rephrasing."
      : "✅ Found new information. Please ask your question again.";

    await saveMessage(session_id, "assistant", msg);

  } catch (error) {
    console.error(`❌ Scraper error:`, error.message);
    await saveMessage(session_id, "assistant", "❌ Web search encountered an error. Please try again.");
  } finally {
    scrapingInProgress.delete(scrapingKey);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// COSINE SIMILARITY
// ─────────────────────────────────────────────────────────────────────────────
function cosineSimilarity(a, b) {
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return 0;
  const dot   = a.reduce((s, v, i) => s + v * b[i], 0);
  const normA = Math.sqrt(a.reduce((s, v) => s + v * v, 0));
  const normB = Math.sqrt(b.reduce((s, v) => s + v * v, 0));
  if (normA === 0 || normB === 0) return 0;
  return dot / (normA * normB);
}

// ─────────────────────────────────────────────────────────────────────────────
// CHAT HISTORY & CLEAR
// ─────────────────────────────────────────────────────────────────────────────
export const getChatHistory = async (req, res) => {
  try {
    const { session_id } = req.query;
    if (!session_id) return res.status(400).json({ error: "session_id required" });
    const messages = await ChatSession.findAll({
      where: { session_id }, order: [["createdAt","ASC"]]
    });
    res.json({
      history: messages.map(m => ({
        role: m.role,
        content: m.message,
        createdAt: m.createdAt
      })),
      session_id
    });
  } catch (e) {
    res.status(500).json({ error: "Failed to fetch history" });
  }
};

export const clearHistory = async (req, res) => {
  try {
    const { session_id } = req.body;
    await ChatSession.destroy({ where: { session_id } });
    sessionAnswerCache.delete(session_id);
    res.json({ message: "History cleared" });
  } catch (e) {
    res.status(500).json({ error: "Failed to clear history" });
  }
};