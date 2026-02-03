// src/App.jsx - FULLSCREEN LIGHT MODE VERSION
import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:3000/api';

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [showSources, setShowSources] = useState(false);
  const [currentSources, setCurrentSources] = useState([]);
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  // Get or create persistent session ID
  const getSessionId = () => {
    let sessionId = localStorage.getItem('chat_session_id');
    if (!sessionId) {
      sessionId = `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      localStorage.setItem('chat_session_id', sessionId);
    }
    return sessionId;
  };

  const [sessionId] = useState(getSessionId);

  // Load chat history on component mount
  useEffect(() => {
    const loadChatHistory = async () => {
      try {
        setLoadingHistory(true);
        const response = await axios.get(`${API_BASE_URL}/query/history`, {
          params: { session_id: sessionId }
        });
        
        if (response.data.history && response.data.history.length > 0) {
          const loadedMessages = response.data.history.map((msg, index) => ({
            role: msg.role,
            content: msg.content,
            id: `${msg.createdAt}-${index}`
          }));
          setMessages(loadedMessages);
        }
      } catch (err) {
        console.error('Failed to load chat history:', err);
        setMessages([]);
      } finally {
        setLoadingHistory(false);
      }
    };

    loadChatHistory();
  }, [sessionId]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [input]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage = { role: 'user', content: input, id: Date.now() };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);
    setIsTyping(true);

    try {
      const response = await axios.post(`${API_BASE_URL}/query`, {
        session_id: sessionId,
        query: input,
      });

      // Simulate typing delay for better UX
      setTimeout(() => {
        const assistantMessage = {
          role: 'assistant',
          content: response.data.answer,
          id: Date.now() + 1,
        };
        setMessages(prev => [...prev, assistantMessage]);
        setCurrentSources(response.data.sources || []);
        setIsTyping(false);
      }, 800);
    } catch (err) {
      setIsTyping(false);
      const errorMessage = {
        role: 'assistant',
        content: '❌ ' + (err.response?.data?.error || 'Something went wrong!'),
        id: Date.now() + 1,
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const clearChat = async () => {
    try {
      await axios.post(`${API_BASE_URL}/query/clear-history`, {
        session_id: sessionId,
      });
      setMessages([]);
      setCurrentSources([]);
      setShowSources(false);
      
      const newSessionId = `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      localStorage.setItem('chat_session_id', newSessionId);
      window.location.reload();
    } catch (err) {
      console.error('Failed to clear:', err);
    }
  };

  const exampleQuestions = [
    { icon: "💰", text: "What is Xobin pricing?", color: "from-emerald-400 to-teal-500" },
    { icon: "⚡", text: "Tell me about the features", color: "from-blue-400 to-cyan-500" },
    { icon: "🔧", text: "How does it work?", color: "from-violet-400 to-purple-500" },
    { icon: "🎯", text: "What are the benefits?", color: "from-pink-400 to-rose-500" }
  ];

  return (
    <div className="h-screen w-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 relative overflow-hidden">
      
      {/* Animated Background Elements - Light Theme */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 left-20 w-96 h-96 bg-gradient-to-br from-blue-200 to-indigo-200 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob"></div>
        <div className="absolute top-40 right-20 w-96 h-96 bg-gradient-to-br from-purple-200 to-pink-200 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob animation-delay-2000"></div>
        <div className="absolute -bottom-8 left-40 w-96 h-96 bg-gradient-to-br from-indigo-200 to-blue-200 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob animation-delay-4000"></div>
      </div>

      {/* Main Chat Container - FULLSCREEN */}
      <div className="h-full w-full flex flex-col bg-white/80 backdrop-blur-xl relative z-10">
        
        {/* Header - Light Theme */}
        <div className="flex-shrink-0 bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 px-6 sm:px-8 py-5 sm:py-6 border-b border-indigo-200/30 shadow-lg">
          <div className="flex items-center justify-between max-w-7xl mx-auto">
            <div className="flex items-center gap-4 sm:gap-5">
              {/* Animated Logo */}
              <div className="relative">
                <div className="w-14 h-14 sm:w-16 sm:h-16 bg-white rounded-2xl flex items-center justify-center text-3xl sm:text-4xl shadow-xl transform hover:scale-110 transition-transform duration-300 rotate-3 hover:rotate-0">
                  🤖
                </div>
                <div className="absolute -top-1 -right-1 w-4 h-4 sm:w-5 sm:h-5 bg-green-400 rounded-full border-2 border-white animate-pulse shadow-lg"></div>
              </div>
              
              <div>
                <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
                  RAG Assistant
                </h1>
                <p className="text-blue-100 text-xs sm:text-sm font-medium flex items-center gap-2 mt-1">
                  <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
                  Powered by ZOHAIB
                </p>
              </div>
            </div>
            
            {/* Header Actions */}
            <div className="flex gap-2 sm:gap-3">
              {currentSources.length > 0 && (
                <button
                  onClick={() => setShowSources(!showSources)}
                  className="group px-4 sm:px-6 py-2 sm:py-3 bg-white/20 hover:bg-white/30 backdrop-blur-md text-white rounded-xl font-semibold flex items-center gap-2 sm:gap-3 text-xs sm:text-sm transition-all duration-300 border border-white/30 hover:border-white/50 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
                >
                  <span className="text-lg sm:text-xl group-hover:scale-110 transition-transform">📚</span>
                  <span className="hidden sm:inline">{showSources ? 'Hide' : 'Show'} Sources</span>
                  <span className="bg-yellow-400 text-gray-800 px-2 sm:px-3 py-0.5 sm:py-1 rounded-lg text-xs font-bold shadow-md">
                    {currentSources.length}
                  </span>
                </button>
              )}
              {messages.length > 0 && (
                <button
                  onClick={clearChat}
                  className="group px-4 sm:px-6 py-2 sm:py-3 bg-white/20 hover:bg-red-400/30 backdrop-blur-md text-white rounded-xl font-semibold flex items-center gap-2 sm:gap-3 text-xs sm:text-sm transition-all duration-300 border border-white/30 hover:border-red-300/50 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
                >
                  <span className="text-lg sm:text-xl group-hover:rotate-12 transition-transform">🗑️</span>
                  <span className="hidden sm:inline">Clear</span>
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Messages Area - Light Theme */}
        <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-4 sm:py-6 bg-gradient-to-b from-gray-50 to-white scrollbar-thin scrollbar-thumb-indigo-300 scrollbar-track-transparent">
          <div className="max-w-5xl mx-auto space-y-4 sm:space-y-6">
            {loadingHistory ? (
              <div className="flex flex-col items-center justify-center h-full space-y-6">
                <div className="relative">
                  <div className="w-16 h-16 sm:w-20 sm:h-20 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
                  <div className="absolute inset-0 w-16 h-16 sm:w-20 sm:h-20 border-4 border-blue-200 border-b-blue-600 rounded-full animate-spin" style={{animationDirection: 'reverse', animationDuration: '1s'}}></div>
                </div>
                <p className="text-gray-600 text-base sm:text-lg font-medium">Loading your conversation...</p>
              </div>
            ) : messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center space-y-8 sm:space-y-10 py-8 sm:py-12 animate-fade-in">
                {/* Hero Section */}
                <div className="relative">
                  <div className="absolute inset-0 bg-gradient-to-r from-indigo-400 to-purple-400 rounded-full blur-3xl opacity-20 animate-pulse"></div>
                  <div className="relative w-24 h-24 sm:w-32 sm:h-32 bg-gradient-to-br from-blue-500 via-indigo-500 to-purple-600 rounded-3xl flex items-center justify-center text-5xl sm:text-7xl shadow-2xl transform hover:scale-110 transition-all duration-500 rotate-6 hover:rotate-0">
                    💬
                  </div>
                </div>
                
                <div className="space-y-3 sm:space-y-4 px-4">
                  <h2 className="text-3xl sm:text-5xl font-black text-transparent bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 bg-clip-text">
                    Welcome Back! 👋
                  </h2>
                  <p className="text-gray-600 text-base sm:text-xl font-medium max-w-2xl mx-auto">
                    I'm your intelligent assistant. Ask me anything about your documents and I'll provide accurate, context-aware answers.
                  </p>
                </div>
                
                {/* Example Questions Grid */}
                <div className="mt-6 sm:mt-8 w-full max-w-3xl px-4">
                  <p className="text-gray-500 text-xs sm:text-sm mb-4 sm:mb-6 font-semibold uppercase tracking-wider flex items-center justify-center gap-2">
                    <span className="text-base sm:text-lg">✨</span>
                    Suggested Questions
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                    {exampleQuestions.map((question, idx) => (
                      <button 
                        key={idx}
                        onClick={() => setInput(question.text)}
                        className="group relative px-5 sm:px-6 py-4 sm:py-5 bg-white text-gray-700 rounded-2xl hover:shadow-xl transition-all duration-300 font-medium border-2 border-gray-200 hover:border-indigo-300 text-left shadow-md hover:-translate-y-1 overflow-hidden"
                      >
                        <div className={`absolute inset-0 bg-gradient-to-r ${question.color} opacity-0 group-hover:opacity-10 transition-opacity duration-300`}></div>
                        <div className="relative flex items-center gap-3 sm:gap-4">
                          <span className="text-2xl sm:text-3xl transform group-hover:scale-125 transition-transform duration-300">{question.icon}</span>
                          <span className="text-sm sm:text-base">{question.text}</span>
                        </div>
                        <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                          <span className="text-indigo-500 font-bold">→</span>
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
                    style={{animationDelay: `${index * 0.1}s`}}
                  >
                    {/* Avatar */}
                    <div className={`flex-shrink-0 w-10 h-10 sm:w-12 sm:h-12 rounded-2xl flex items-center justify-center text-xl sm:text-2xl shadow-lg transform hover:scale-110 transition-all duration-300 ${
                      msg.role === 'user' 
                        ? 'bg-gradient-to-br from-blue-500 to-indigo-600 rotate-3' 
                        : 'bg-gradient-to-br from-indigo-500 to-purple-600 -rotate-3'
                    }`}>
                      {msg.role === 'user' ? '👤' : '🤖'}
                    </div>
                    
                    {/* Message Bubble */}
                    <div className={`group max-w-[75%] px-4 sm:px-6 py-3 sm:py-4 rounded-2xl transition-all duration-300 ${
                      msg.role === 'user'
                        ? 'bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-lg hover:shadow-xl'
                        : 'bg-white text-gray-800 shadow-md hover:shadow-lg border-2 border-gray-200'
                    }`}>
                      <p className="text-sm sm:text-base leading-relaxed whitespace-pre-wrap font-medium">{msg.content}</p>
                      
                      {/* Timestamp on hover */}
                      <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-300 mt-2">
                        <span className={`text-xs ${msg.role === 'user' ? 'text-blue-100' : 'text-gray-400'}`}>
                          {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
                
                {/* Typing Indicator */}
                {(loading || isTyping) && (
                  <div className="flex gap-3 sm:gap-4 animate-slide-in">
                    <div className="flex-shrink-0 w-10 h-10 sm:w-12 sm:h-12 rounded-2xl flex items-center justify-center bg-gradient-to-br from-indigo-500 to-purple-600 text-xl sm:text-2xl shadow-lg -rotate-3">
                      🤖
                    </div>
                    <div className="bg-white rounded-2xl shadow-md px-6 sm:px-8 py-4 sm:py-5 border-2 border-gray-200">
                      <div className="flex gap-2">
                        <div className="w-2.5 h-2.5 sm:w-3 sm:h-3 bg-indigo-500 rounded-full animate-bounce shadow-lg"></div>
                        <div className="w-2.5 h-2.5 sm:w-3 sm:h-3 bg-blue-500 rounded-full animate-bounce shadow-lg" style={{animationDelay: '0.2s'}}></div>
                        <div className="w-2.5 h-2.5 sm:w-3 sm:h-3 bg-purple-500 rounded-full animate-bounce shadow-lg" style={{animationDelay: '0.4s'}}></div>
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>
        </div>

        {/* Sources Panel - Light Theme */}
        {showSources && currentSources.length > 0 && (
          <div className="flex-shrink-0 bg-gradient-to-br from-amber-50 to-orange-50 border-t-2 border-amber-200 max-h-64 sm:max-h-72 overflow-y-auto animate-slide-up scrollbar-thin scrollbar-thumb-amber-400 scrollbar-track-transparent">
            <div className="max-w-5xl mx-auto px-4 sm:px-6 py-4 sm:py-5">
              <div className="flex items-center justify-between mb-3 sm:mb-4">
                <h4 className="font-bold text-gray-800 flex items-center gap-2 sm:gap-3 text-base sm:text-lg">
                  <span className="text-xl sm:text-2xl">📚</span>
                  Referenced Sources 
                  <span className="bg-gradient-to-r from-amber-400 to-orange-500 text-white px-2 sm:px-3 py-0.5 sm:py-1 rounded-lg text-xs sm:text-sm font-bold shadow-md">
                    {currentSources.length}
                  </span>
                </h4>
                <button
                  onClick={() => setShowSources(false)}
                  className="text-gray-400 hover:text-gray-700 text-xl sm:text-2xl transition-all duration-300 hover:rotate-90 transform"
                >
                  ✕
                </button>
              </div>
              <div className="space-y-3">
                {currentSources.map((source, idx) => (
                  <div 
                    key={source.id}
                    className="bg-white p-4 sm:p-5 rounded-xl border-2 border-amber-200 hover:border-amber-400 transition-all duration-300 shadow-md hover:shadow-lg transform hover:-translate-y-1 animate-slide-in"
                    style={{animationDelay: `${idx * 0.1}s`}}
                  >
                    <div className="flex items-center justify-between mb-2 sm:mb-3">
                      <span className="font-bold text-gray-800 flex items-center gap-2 text-sm sm:text-base">
                        <span className="text-base sm:text-lg">📄</span>
                        Source {source.id}
                      </span>
                      <span className="text-xs bg-gradient-to-r from-green-400 to-emerald-500 text-white px-3 sm:px-4 py-1 sm:py-1.5 rounded-full font-bold shadow-md">
                        Score: {source.score}
                      </span>
                    </div>
                    <p className="text-gray-600 text-xs sm:text-sm leading-relaxed">{source.text}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Input Area - Light Theme */}
        <div className="flex-shrink-0 bg-white border-t-2 border-gray-200 px-4 sm:px-6 py-4 sm:py-6 shadow-lg">
          <div className="max-w-5xl mx-auto">
            <div className="flex gap-3 sm:gap-4 items-end">
              {/* Input Container */}
              <div className="flex-1 relative group">
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Type your message here... ✨"
                  disabled={loading || loadingHistory}
                  rows="1"
                  className="w-full px-4 sm:px-6 py-3 sm:py-4 bg-gray-50 border-2 border-gray-300 group-hover:border-indigo-400 focus:border-indigo-500 rounded-2xl focus:ring-4 focus:ring-indigo-200 focus:outline-none resize-none max-h-32 disabled:bg-gray-100 disabled:cursor-not-allowed text-sm sm:text-base text-gray-800 placeholder-gray-400 transition-all duration-300 shadow-sm font-medium"
                />
                <div className="absolute bottom-2 sm:bottom-3 right-2 sm:right-3 text-gray-400 text-xs font-medium">
                  {input.length > 0 && `${input.length} chars`}
                </div>
              </div>
              
              {/* Send Button */}
              <button
                onClick={handleSend}
                disabled={loading || !input.trim() || loadingHistory}
                className="group px-6 sm:px-8 py-3 sm:py-4 bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 hover:from-blue-700 hover:via-indigo-700 hover:to-purple-700 text-white rounded-2xl disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300 font-bold text-sm sm:text-base shadow-lg hover:shadow-xl flex items-center gap-2 sm:gap-3 transform hover:-translate-y-1 hover:scale-105"
              >
                {loading ? (
                  <>
                    <div className="w-4 h-4 sm:w-5 sm:h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                    <span className="hidden sm:inline">Thinking...</span>
                  </>
                ) : (
                  <>
                    <span className="hidden sm:inline">Send</span>
                    <span className="text-lg sm:text-xl group-hover:translate-x-1 transition-transform duration-300">🚀</span>
                  </>
                )}
              </button>
            </div>
            
            {/* Keyboard Shortcuts */}
            <div className="flex items-center justify-center gap-3 sm:gap-4 mt-3 sm:mt-4">
              <p className="text-gray-500 text-xs sm:text-sm font-medium flex items-center gap-2">
                <kbd className="px-2 sm:px-3 py-1 sm:py-1.5 bg-gray-100 rounded-lg border border-gray-300 text-gray-600 font-mono text-xs shadow-sm">Enter</kbd> 
                <span className="hidden sm:inline">to send</span>
              </p>
              <span className="text-gray-300 hidden sm:inline">•</span>
              <p className="text-gray-500 text-xs sm:text-sm font-medium items-center gap-2 hidden sm:flex">
                <kbd className="px-2 sm:px-3 py-1 sm:py-1.5 bg-gray-100 rounded-lg border border-gray-300 text-gray-600 font-mono text-xs shadow-sm">Shift + Enter</kbd> 
                for new line
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Add custom CSS for animations */}
      <style>{`
        @keyframes blob {
          0%, 100% { transform: translate(0, 0) scale(1); }
          25% { transform: translate(20px, -50px) scale(1.1); }
          50% { transform: translate(-20px, 20px) scale(0.9); }
          75% { transform: translate(50px, 50px) scale(1.05); }
        }
        
        @keyframes slide-in {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        
        @keyframes slide-up {
          from {
            opacity: 0;
            transform: translateY(100%);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        
        @keyframes fade-in {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        
        .animate-blob {
          animation: blob 7s infinite;
        }
        
        .animation-delay-2000 {
          animation-delay: 2s;
        }
        
        .animation-delay-4000 {
          animation-delay: 4s;
        }
        
        .animate-slide-in {
          animation: slide-in 0.5s ease-out forwards;
        }
        
        .animate-slide-up {
          animation: slide-up 0.4s ease-out forwards;
        }
        
        .animate-fade-in {
          animation: fade-in 0.8s ease-out forwards;
        }
        
        /* Custom Scrollbar */
        .scrollbar-thin::-webkit-scrollbar {
          width: 8px;
        }
        
        .scrollbar-thumb-indigo-300::-webkit-scrollbar-thumb {
          background-color: rgba(129, 140, 248, 0.5);
          border-radius: 4px;
        }
        
        .scrollbar-thumb-indigo-300::-webkit-scrollbar-thumb:hover {
          background-color: rgba(129, 140, 248, 0.7);
        }
        
        .scrollbar-thumb-amber-400::-webkit-scrollbar-thumb {
          background-color: rgba(251, 191, 36, 0.5);
          border-radius: 4px;
        }
        
        .scrollbar-thumb-amber-400::-webkit-scrollbar-thumb:hover {
          background-color: rgba(251, 191, 36, 0.7);
        }
        
        .scrollbar-track-transparent::-webkit-scrollbar-track {
          background: transparent;
        }
      `}</style>
    </div>
  );
}

export default App;