// src/App.jsx - FIXED: polling reads history, progress stages show correctly
import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:3000/api';

// Messages that indicate scraping/processing is still in progress (not final answers)
const PROGRESS_PATTERNS = [
  '🔍', '⏳', '🌐', '📄', '⚡', '🧹', '🔧', '📊', '🧠', '💾',
  'Searching the web', 'searching', 'Still searching', 'Found new information'
];

const isProgressMessage = (content) =>
  PROGRESS_PATTERNS.some(p => content.includes(p));

const isFinalAnswer = (content) =>
  content && content.trim().length > 0 && !isProgressMessage(content);

// Progress stages shown while scraping runs in background
const PROGRESS_STAGES = [
  "🔍 Starting web search... Analyzing your query",
  "🌐 Searching for relevant websites...",
  "📄 Found websites! Preparing to scrape content...",
  "⚡ Scraping content from websites...",
  "🧹 Cleaning and preprocessing scraped text...",
  "🔗 Detecting links, references, and metadata...",
  "🧠 Creating vector embeddings for new content...",
  "💾 Storing embeddings in database...",
  "📊 Updating search index and vector store...",
  "✨ Optimizing embeddings for faster retrieval...",
  "🕵️‍♂️ Performing semantic similarity checks...",
  "✅ Data processing complete! Preparing answer...",
  "🤖 Generating final answer with AI...",
  "🎯 Answer ready! Delivering to user..."
];

function App() {
  const [messages, setMessages]           = useState([]);
  const [input, setInput]                 = useState('');
  const [loading, setLoading]             = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [showSources, setShowSources]     = useState(false);
  const [currentSources, setCurrentSources] = useState([]);
  const [isTyping, setIsTyping]           = useState(false);
  const [isScraping, setIsScraping]       = useState(false);
  const [currentProgress, setCurrentProgress] = useState('');

  const messagesEndRef      = useRef(null);
  const textareaRef         = useRef(null);
  const pollingIntervalRef  = useRef(null);
  const progressIntervalRef = useRef(null);
  const answerReceivedRef   = useRef(false);
  const progressStepRef     = useRef(0);
  const lastHistoryLengthRef = useRef(0);

  // ── Session ───────────────────────────────────────────────────────────────
  const getSessionId = () => {
    let id = localStorage.getItem('chat_session_id');
    if (!id) {
      id = `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      localStorage.setItem('chat_session_id', id);
    }
    return id;
  };
  const [sessionId] = useState(getSessionId);

  // ── Load history on mount ─────────────────────────────────────────────────
  useEffect(() => {
    const loadHistory = async () => {
      try {
        setLoadingHistory(true);
        const res = await axios.get(`${API_BASE_URL}/query/history`, {
          params: { session_id: sessionId }
        });
        if (res.data.history?.length > 0) {
          const loaded = res.data.history
            .filter(m => isFinalAnswer(m.content)) // skip progress msgs on load
            .map((m, i) => ({ role: m.role, content: m.content, id: `${m.createdAt}-${i}` }));
          setMessages(loaded);
          lastHistoryLengthRef.current = loaded.length;
        }
      } catch (e) {
        console.error('Failed to load history:', e);
      } finally {
        setLoadingHistory(false);
      }
    };
    loadHistory();
  }, [sessionId]);

  // ── Auto scroll ───────────────────────────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Textarea auto resize ──────────────────────────────────────────────────
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [input]);

  // ── Cleanup on unmount ────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      clearInterval(pollingIntervalRef.current);
      clearInterval(progressIntervalRef.current);
    };
  }, []);

  // ── Stop all polling ──────────────────────────────────────────────────────
  const stopPolling = () => {
    clearInterval(pollingIntervalRef.current);
    clearInterval(progressIntervalRef.current);
    pollingIntervalRef.current  = null;
    progressIntervalRef.current = null;
  };

  // ── Show final answer ─────────────────────────────────────────────────────
  const displayAnswer = (content, sources = []) => {
    answerReceivedRef.current = true;
    stopPolling();

    // Remove any progress/status messages, add real answer
    setMessages(prev => {
      const filtered = prev.filter(m => !(m.isProgress));
      return [...filtered, {
        role: 'assistant',
        content,
        id: Date.now(),
        isProgress: false
      }];
    });

    setCurrentSources(sources || []);
    setIsTyping(false);
    setLoading(false);
    setIsScraping(false);
    setCurrentProgress('');
  };

  // ── Update the live progress bubble ──────────────────────────────────────
  const setProgressBubble = (text) => {
    setCurrentProgress(text);
    setMessages(prev => {
      const withoutOldProgress = prev.filter(m => !m.isProgress);
      return [...withoutOldProgress, {
        role: 'assistant',
        content: text,
        id: 'progress-bubble',
        isProgress: true
      }];
    });
  };

  // ── KEY FIX: Poll getChatHistory, not check_similarity_only ──────────────
  // When backend's trigger_query_controller runs (after scraping + embedding),
  // it calls queryController with skip_scraping=true and saves the REAL answer
  // to ChatSession DB. We detect it here by watching for new non-progress msgs.
  const startPolling = (query) => {
    answerReceivedRef.current  = false;
    progressStepRef.current    = 0;

    // Show first progress stage immediately
    setProgressBubble(PROGRESS_STAGES[0]);

    // Rotate progress stages every 6s while waiting
    progressIntervalRef.current = setInterval(() => {
      if (answerReceivedRef.current) return;
      progressStepRef.current = Math.min(
        progressStepRef.current + 1,
        PROGRESS_STAGES.length - 1
      );
      setProgressBubble(PROGRESS_STAGES[progressStepRef.current]);
    }, 6000);

    let attempts = 0;
    const maxAttempts = 100; // 80 × 3s = 4 minutes max

    // Poll chat history every 3 seconds
    pollingIntervalRef.current = setInterval(async () => {
      if (answerReceivedRef.current) {
        stopPolling();
        return;
      }

      attempts++;
      if (attempts > maxAttempts) {
        stopPolling();
        setIsScraping(false);
        setLoading(false);
        displayAnswer("❌ Search took too long. Please try rephrasing your question.");
        return;
      }

      try {
        // FIX: Read actual chat history — the backend saves the real answer here
        // after trigger_query_controller completes. No need for check_similarity_only.
        const res = await axios.get(`${API_BASE_URL}/query/history`, {
          params: { session_id: sessionId }
        });

        const history = res.data.history || [];

        // Find messages added AFTER the user sent this query
        // Filter to only assistant messages that are real answers (not progress)
        const newAssistantMessages = history
          .filter(m => m.role === 'assistant')
          .filter(m => isFinalAnswer(m.content));

        // If we have more final answers than before the query was sent,
        // the backend has produced a real answer
        if (newAssistantMessages.length > lastHistoryLengthRef.current) {
          const latestAnswer = newAssistantMessages[newAssistantMessages.length - 1];
          console.log('✅ New answer detected in history:', latestAnswer.content.substring(0, 80));
          lastHistoryLengthRef.current = newAssistantMessages.length;
          displayAnswer(latestAnswer.content);
          return;
        }

        // Show elapsed time in progress bubble
        const elapsed = attempts * 3;
        if (elapsed % 15 === 0) {
          console.log(`⏳ Still waiting for answer... ${elapsed}s elapsed`);
        }

      } catch (e) {
        console.error('Polling error:', e);
      }
    }, 3000);
  };

  // ── Send message ──────────────────────────────────────────────────────────
  const handleSend = async () => {
    if (!input.trim() || loading || isScraping) return;

    const userQuery = input.trim();
    const userMsg   = { role: 'user', content: userQuery, id: Date.now() };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);
    setIsTyping(true);
    answerReceivedRef.current = false;

    // Track how many final assistant answers exist BEFORE this query
    // so polling can detect when a NEW one appears
    try {
      const histRes = await axios.get(`${API_BASE_URL}/query/history`, {
        params: { session_id: sessionId }
      });
      const priorFinalAnswers = (histRes.data.history || [])
        .filter(m => m.role === 'assistant' && isFinalAnswer(m.content));
      lastHistoryLengthRef.current = priorFinalAnswers.length;
    } catch (e) {
      // non-fatal, polling will still work
    }

    try {
      const res = await axios.post(`${API_BASE_URL}/query`, {
        session_id: sessionId,
        query: userQuery,
      });

      console.log('📥 Initial response:', res.data);

      // ── Case 1: Immediate answer (data already in DB, no scraping needed) ──
      if (res.data.answer && !res.data.scraping_started && !res.data.scraping_in_progress) {
        console.log('✅ Immediate answer!');
        setIsTyping(false);
        setTimeout(() => displayAnswer(res.data.answer, res.data.sources || []), 400);
        return;
      }

      // ── Case 2: Scraping started — poll history for real answer ────────────
      if (res.data.scraping_started || res.data.scraping_in_progress) {
        console.log('🌐 Scraping started, begin polling history...');
        setIsTyping(false);
        setIsScraping(true);
        startPolling(userQuery);
        return;
      }

      // ── Case 3: Unexpected format — try to show whatever answer exists ──────
      if (res.data.answer) {
        displayAnswer(res.data.answer, res.data.sources || []);
      } else {
        throw new Error('No answer in response');
      }

    } catch (err) {
      console.error('❌ Send error:', err);
      stopPolling();
      setIsTyping(false);
      setLoading(false);
      setIsScraping(false);
      setMessages(prev => prev.filter(m => !m.isProgress));
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '❌ ' + (err.response?.data?.error || 'Something went wrong. Please try again.'),
        id: Date.now()
      }]);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // ── Clear chat ────────────────────────────────────────────────────────────
  const clearChat = async () => {
    stopPolling();
    answerReceivedRef.current = false;
    setIsScraping(false);
    setLoading(false);
    try {
      await axios.post(`${API_BASE_URL}/query/clear-history`, { session_id: sessionId });
      setMessages([]);
      setCurrentSources([]);
      setShowSources(false);
      setCurrentProgress('');
      lastHistoryLengthRef.current = 0;
      const newId = `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      localStorage.setItem('chat_session_id', newId);
      window.location.reload();
    } catch (e) {
      console.error('Clear failed:', e);
    }
  };

  const exampleQuestions = [
    { icon: "💰", text: "What is Xobin pricing?",      color: "from-emerald-400 to-teal-500" },
    { icon: "⚡", text: "Tell me about the features",  color: "from-blue-400 to-cyan-500"    },
    { icon: "🔧", text: "How does it work?",           color: "from-violet-400 to-purple-500" },
    { icon: "🎯", text: "What are the benefits?",      color: "from-pink-400 to-rose-500"    }
  ];

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div
      className="h-screen w-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 relative overflow-hidden cursor-text"
      onClick={() => textareaRef.current?.focus()}
    >
      {/* Animated background blobs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 left-20 w-96 h-96 bg-gradient-to-br from-blue-200 to-indigo-200 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob"></div>
        <div className="absolute top-40 right-20 w-96 h-96 bg-gradient-to-br from-purple-200 to-pink-200 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob animation-delay-2000"></div>
        <div className="absolute -bottom-8 left-40 w-96 h-96 bg-gradient-to-br from-indigo-200 to-blue-200 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob animation-delay-4000"></div>
      </div>

      <div className="h-full w-full flex flex-col bg-white/80 backdrop-blur-xl relative z-10">

        {/* Header */}
        <div className="flex-shrink-0 bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 px-6 sm:px-8 py-5 sm:py-6 border-b border-indigo-200/30 shadow-lg">
          <div className="flex items-center justify-between max-w-7xl mx-auto">
            <div className="flex items-center gap-4 sm:gap-5">
              <div className="relative">
                <div className="w-14 h-14 sm:w-16 sm:h-16 bg-white rounded-2xl flex items-center justify-center text-3xl sm:text-4xl shadow-xl transform hover:scale-110 transition-transform duration-300 rotate-3 hover:rotate-0">
                  🤖
                </div>
                <div className={`absolute -top-1 -right-1 w-4 h-4 sm:w-5 sm:h-5 rounded-full border-2 border-white shadow-lg ${
                  isScraping ? 'bg-yellow-400 animate-pulse' : 'bg-green-400 animate-pulse'
                }`}></div>
              </div>
              <div>
                <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">RAG Assistant</h1>
                <p className="text-blue-100 text-xs sm:text-sm font-medium flex items-center gap-2 mt-1">
                  <span className={`w-2 h-2 rounded-full ${isScraping ? 'bg-yellow-400' : 'bg-green-400'} animate-pulse`}></span>
                  {isScraping ? 'Searching the web...' : 'Powered by ZOHAIB'}
                </p>
              </div>
            </div>
            <div className="flex gap-2 sm:gap-3">
              {currentSources.length > 0 && (
                <button
                  onClick={(e) => { e.stopPropagation(); setShowSources(!showSources); }}
                  className="group px-4 sm:px-6 py-2 sm:py-3 bg-white/20 hover:bg-white/30 backdrop-blur-md text-white rounded-xl font-semibold flex items-center gap-2 sm:gap-3 text-xs sm:text-sm transition-all duration-300 border border-white/30 hover:border-white/50 shadow-lg"
                >
                  <span className="text-lg sm:text-xl">📚</span>
                  <span className="hidden sm:inline">{showSources ? 'Hide' : 'Show'} Sources</span>
                  <span className="bg-yellow-400 text-gray-800 px-2 sm:px-3 py-0.5 rounded-lg text-xs font-bold">{currentSources.length}</span>
                </button>
              )}
              {messages.length > 0 && (
                <button
                  onClick={(e) => { e.stopPropagation(); clearChat(); }}
                  className="group px-4 sm:px-6 py-2 sm:py-3 bg-white/20 hover:bg-red-400/30 backdrop-blur-md text-white rounded-xl font-semibold flex items-center gap-2 sm:gap-3 text-xs sm:text-sm transition-all duration-300 border border-white/30 shadow-lg"
                >
                  <span className="text-lg sm:text-xl">🗑️</span>
                  <span className="hidden sm:inline">Clear</span>
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Messages */}
        <div
          className="flex-1 overflow-y-auto px-4 sm:px-6 py-4 sm:py-6 bg-gradient-to-b from-gray-50 to-white scrollbar-thin scrollbar-thumb-indigo-300 scrollbar-track-transparent"
          onClick={(e) => { e.stopPropagation(); textareaRef.current?.focus(); }}
        >
          <div className="max-w-5xl mx-auto space-y-4 sm:space-y-6">
            {loadingHistory ? (
              <div className="flex flex-col items-center justify-center h-full space-y-6">
                <div className="relative">
                  <div className="w-16 h-16 sm:w-20 sm:h-20 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
                </div>
                <p className="text-gray-600 text-base sm:text-lg font-medium">Loading your conversation...</p>
              </div>
            ) : messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center space-y-8 sm:space-y-10 py-8 sm:py-12 animate-fade-in">
                <div className="relative">
                  <div className="w-24 h-24 sm:w-32 sm:h-32 bg-gradient-to-br from-blue-500 via-indigo-500 to-purple-600 rounded-3xl flex items-center justify-center text-5xl sm:text-7xl shadow-2xl transform hover:scale-110 transition-all duration-500 rotate-6 hover:rotate-0">
                    💬
                  </div>
                </div>
                <div className="space-y-3 sm:space-y-4 px-4">
                  <h2 className="text-3xl sm:text-5xl font-black text-transparent bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 bg-clip-text">
                    Welcome Back! 👋
                  </h2>
                  <p className="text-gray-600 text-base sm:text-xl font-medium max-w-2xl mx-auto">
                    I'm your intelligent assistant. Ask me anything and I'll search the web if needed.
                  </p>
                </div>
                <div className="mt-6 sm:mt-8 w-full max-w-3xl px-4">
                  <p className="text-gray-500 text-xs sm:text-sm mb-4 font-semibold uppercase tracking-wider flex items-center justify-center gap-2">
                    <span>✨</span> Suggested Questions
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                    {exampleQuestions.map((q, idx) => (
                      <button
                        key={idx}
                        onClick={(e) => { e.stopPropagation(); setInput(q.text); textareaRef.current?.focus(); }}
                        className="group relative px-5 sm:px-6 py-4 sm:py-5 bg-white rounded-2xl hover:shadow-xl transition-all duration-300 font-medium border-2 border-gray-200 hover:border-indigo-300 text-left shadow-md hover:-translate-y-1 overflow-hidden cursor-pointer"
                      >
                        <div className={`absolute inset-0 bg-gradient-to-r ${q.color} opacity-0 group-hover:opacity-10 transition-opacity duration-300`}></div>
                        <div className="relative flex items-center gap-3 sm:gap-4">
                          <span className="text-2xl sm:text-3xl">{q.icon}</span>
                          <span className="text-sm sm:text-base">{q.text}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <>
                {messages.map((msg, index) => (
                  <div
                    key={msg.id}
                    className={`flex gap-3 sm:gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : ''} animate-slide-in`}
                    style={{ animationDelay: `${index * 0.05}s` }}
                  >
                    <div className={`flex-shrink-0 w-10 h-10 sm:w-12 sm:h-12 rounded-2xl flex items-center justify-center text-xl sm:text-2xl shadow-lg ${
                      msg.role === 'user'
                        ? 'bg-gradient-to-br from-blue-500 to-indigo-600 rotate-3'
                        : 'bg-gradient-to-br from-indigo-500 to-purple-600 -rotate-3'
                    } ${msg.isProgress ? 'animate-pulse' : ''}`}>
                      {msg.role === 'user' ? '👤' : (msg.isProgress ? '🌐' : '🤖')}
                    </div>

                    <div className={`group max-w-[75%] px-4 sm:px-6 py-3 sm:py-4 rounded-2xl transition-all duration-300 ${
                      msg.role === 'user'
                        ? 'bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-lg'
                        : msg.isProgress
                          ? 'bg-blue-50 text-blue-800 shadow-md border-2 border-blue-200 animate-pulse'
                          : 'bg-white text-gray-800 shadow-md border-2 border-gray-200'
                    }`}>
                      <p
                        className="text-sm sm:text-base leading-relaxed whitespace-pre-wrap font-medium"
                        dangerouslySetInnerHTML={{ __html: msg.content }}
                      />
                    </div>
                  </div>
                ))}

                {/* Typing indicator — only shown when loading but before any message appears */}
                {(loading || isTyping) && !isScraping && (
                  <div className="flex gap-3 sm:gap-4 animate-slide-in">
                    <div className="flex-shrink-0 w-10 h-10 sm:w-12 sm:h-12 rounded-2xl flex items-center justify-center bg-gradient-to-br from-indigo-500 to-purple-600 text-xl sm:text-2xl shadow-lg -rotate-3 animate-pulse">
                      🤖
                    </div>
                    <div className="bg-white rounded-2xl shadow-md px-6 sm:px-8 py-4 sm:py-5 border-2 border-gray-200">
                      <div className="flex gap-2">
                        <div className="w-2.5 h-2.5 sm:w-3 sm:h-3 bg-indigo-500 rounded-full animate-bounce shadow-lg"></div>
                        <div className="w-2.5 h-2.5 sm:w-3 sm:h-3 bg-blue-500 rounded-full animate-bounce shadow-lg" style={{ animationDelay: '0.2s' }}></div>
                        <div className="w-2.5 h-2.5 sm:w-3 sm:h-3 bg-purple-500 rounded-full animate-bounce shadow-lg" style={{ animationDelay: '0.4s' }}></div>
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>
        </div>

        {/* Sources Panel */}
        {showSources && currentSources.length > 0 && (
          <div className="flex-shrink-0 bg-gradient-to-br from-amber-50 to-orange-50 border-t-2 border-amber-200 max-h-64 sm:max-h-72 overflow-y-auto animate-slide-up">
            <div className="max-w-5xl mx-auto px-4 sm:px-6 py-4 sm:py-5">
              <div className="flex items-center justify-between mb-3 sm:mb-4">
                <h4 className="font-bold text-gray-800 flex items-center gap-2 sm:gap-3 text-base sm:text-lg">
                  <span className="text-xl sm:text-2xl">📚</span>
                  Referenced Sources
                  <span className="bg-gradient-to-r from-amber-400 to-orange-500 text-white px-2 sm:px-3 py-0.5 rounded-lg text-xs font-bold">{currentSources.length}</span>
                </h4>
                <button onClick={(e) => { e.stopPropagation(); setShowSources(false); }} className="text-gray-400 hover:text-gray-700 text-xl transition-all duration-300">✕</button>
              </div>
              <div className="space-y-3">
                {currentSources.map((source, idx) => (
                  <div key={source.id} className="bg-white p-4 sm:p-5 rounded-xl border-2 border-amber-200 hover:border-amber-400 transition-all duration-300 shadow-md hover:shadow-lg">
                    <div className="flex items-center justify-between mb-2 sm:mb-3">
                      <span className="font-bold text-gray-800 flex items-center gap-2 text-sm sm:text-base">
                        <span>📄</span> Source {source.id}
                      </span>
                      <span className="text-xs bg-gradient-to-r from-green-400 to-emerald-500 text-white px-3 py-1 rounded-full font-bold">
                        Score: {source.score}
                      </span>
                    </div>
                    <p className="text-gray-600 text-xs sm:text-sm leading-relaxed mb-2">{source.text}</p>
                    {source.website_link && (
                      <a href={source.website_link} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 text-xs flex items-center gap-1 font-medium">
                        🔗 View Source
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Input Area */}
        <div className="flex-shrink-0 bg-white border-t-2 border-gray-200 px-4 sm:px-6 py-4 sm:py-6 shadow-lg">
          <div className="max-w-5xl mx-auto">

            {/* Live scraping progress bar */}
            {isScraping && (
              <div className="mb-4 p-4 bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-blue-300 rounded-xl flex items-center gap-3">
                <div className="w-6 h-6 border-3 border-blue-500 border-t-transparent rounded-full animate-spin flex-shrink-0"></div>
                <div className="flex-1">
                  <p className="text-blue-800 font-semibold text-sm">
                    {currentProgress || PROGRESS_STAGES[0]}
                  </p>
                  <p className="text-blue-600 text-xs mt-1">
                    This may take 1-2 minutes. I'll show you progress at each step.
                  </p>
                </div>
              </div>
            )}

            <div className="flex gap-3 sm:gap-4 items-end">
              <div className="flex-1 relative group">
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder={isScraping ? "Searching... please wait ⏳" : "Type your message here... ✨"}
                  disabled={loading || loadingHistory || isScraping}
                  rows="1"
                  className="w-full px-4 sm:px-6 py-3 sm:py-4 bg-gray-50 border-2 border-indigo-400 focus:border-indigo-600 rounded-2xl focus:ring-4 focus:ring-indigo-200 focus:outline-none resize-none max-h-32 disabled:bg-gray-100 disabled:cursor-not-allowed text-sm sm:text-base text-gray-800 placeholder-gray-400 transition-all duration-300 shadow-sm font-medium"
                  autoFocus
                />
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); handleSend(); }}
                disabled={loading || !input.trim() || loadingHistory || isScraping}
                className="group px-6 sm:px-8 py-3 sm:py-4 bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 hover:from-blue-700 hover:via-indigo-700 hover:to-purple-700 text-white rounded-2xl disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300 font-bold text-sm sm:text-base shadow-lg hover:shadow-xl flex items-center gap-2 sm:gap-3 transform hover:-translate-y-1"
              >
                {loading || isScraping ? (
                  <>
                    <div className="w-4 h-4 sm:w-5 sm:h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                    <span className="hidden sm:inline">{isScraping ? 'Searching...' : 'Thinking...'}</span>
                  </>
                ) : (
                  <>
                    <span className="hidden sm:inline">Send</span>
                    <span className="text-lg sm:text-xl">🚀</span>
                  </>
                )}
              </button>
            </div>

            <div className="flex items-center justify-center gap-3 sm:gap-4 mt-3 sm:mt-4">
              <p className="text-gray-500 text-xs sm:text-sm font-medium flex items-center gap-2">
                <kbd className="px-2 sm:px-3 py-1 bg-gray-100 rounded-lg border border-gray-300 text-gray-600 font-mono text-xs shadow-sm">Enter</kbd>
                <span className="hidden sm:inline">to send</span>
              </p>
              <span className="text-gray-300 hidden sm:inline">•</span>
              <p className="text-gray-500 text-xs sm:text-sm font-medium items-center gap-2 hidden sm:flex">
                <kbd className="px-2 sm:px-3 py-1 bg-gray-100 rounded-lg border border-gray-300 text-gray-600 font-mono text-xs shadow-sm">Shift + Enter</kbd>
                for new line
              </p>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes blob {
          0%, 100% { transform: translate(0, 0) scale(1); }
          25% { transform: translate(20px, -50px) scale(1.1); }
          50% { transform: translate(-20px, 20px) scale(0.9); }
          75% { transform: translate(50px, 50px) scale(1.05); }
        }
        @keyframes slide-in {
          from { opacity: 0; transform: translateY(20px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes slide-up {
          from { opacity: 0; transform: translateY(100%); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes fade-in {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
        .animate-blob { animation: blob 7s infinite; }
        .animation-delay-2000 { animation-delay: 2s; }
        .animation-delay-4000 { animation-delay: 4s; }
        .animate-slide-in { animation: slide-in 0.5s ease-out forwards; }
        .animate-slide-up { animation: slide-up 0.4s ease-out forwards; }
        .animate-fade-in  { animation: fade-in 0.8s ease-out forwards; }
        .scrollbar-thin::-webkit-scrollbar { width: 8px; }
        .scrollbar-thumb-indigo-300::-webkit-scrollbar-thumb { background-color: rgba(129,140,248,0.5); border-radius: 4px; }
        .scrollbar-thumb-amber-400::-webkit-scrollbar-thumb  { background-color: rgba(251,191,36,0.5);  border-radius: 4px; }
        .scrollbar-track-transparent::-webkit-scrollbar-track { background: transparent; }
      `}</style>
    </div>
  );
}

export default App;