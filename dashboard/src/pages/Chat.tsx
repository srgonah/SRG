import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '@/api/client';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import type { Session, ChatMessage, SourceCitation } from '@/api/types';

interface DisplayMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  citations?: SourceCitation[];
  isStreaming?: boolean;
}

export function ChatPage() {
  useDocumentTitle('Chat');

  const { sessionId } = useParams<{ sessionId?: string }>();
  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(sessionId || null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [useRag, setUseRag] = useState(true);
  const [useStream, setUseStream] = useState(true);

  // Load sessions
  useEffect(() => {
    async function loadSessions() {
      try {
        const res = await api.sessions.list();
        setSessions(res.sessions || []);
      } catch (err) {
        console.error('Failed to load sessions:', err);
      }
    }
    loadSessions();
  }, []);

  // Load messages when session changes
  useEffect(() => {
    async function loadMessages() {
      if (!currentSessionId) {
        setMessages([]);
        return;
      }

      try {
        const res = await api.sessions.getMessages(currentSessionId);
        setMessages(
          (res.messages || []).map((m: ChatMessage) => ({
            id: m.id,
            role: m.role,
            content: m.content,
          }))
        );
      } catch (err) {
        console.error('Failed to load messages:', err);
      }
    }
    loadMessages();
  }, [currentSessionId]);

  // Update URL when session changes
  useEffect(() => {
    if (currentSessionId && currentSessionId !== sessionId) {
      navigate(`/chat/${currentSessionId}`, { replace: true });
    }
  }, [currentSessionId, sessionId, navigate]);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleNewChat = useCallback(() => {
    setCurrentSessionId(null);
    setMessages([]);
    navigate('/chat');
    inputRef.current?.focus();
  }, [navigate]);

  const handleSelectSession = useCallback((id: string) => {
    setCurrentSessionId(id);
  }, []);

  const handleDeleteSession = useCallback(async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.sessions.delete(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (currentSessionId === id) {
        handleNewChat();
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  }, [currentSessionId, handleNewChat]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput('');
    setLoading(true);

    // Add user message
    const userMsg: DisplayMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
    };
    setMessages((prev) => [...prev, userMsg]);

    // Add placeholder for assistant
    const assistantId = `assistant-${Date.now()}`;
    const assistantMsg: DisplayMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      isStreaming: useStream,
    };
    setMessages((prev) => [...prev, assistantMsg]);

    try {
      if (useStream) {
        // Streaming response
        let content = '';
        for await (const chunk of api.chat.stream({
          message: text,
          session_id: currentSessionId,
          use_rag: useRag,
          stream: true,
        })) {
          content += chunk;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content } : m
            )
          );
        }
        // Mark as done streaming
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, isStreaming: false } : m
          )
        );
      } else {
        // Normal response
        const res = await api.chat.send({
          message: text,
          session_id: currentSessionId,
          use_rag: useRag,
          include_sources: true,
        });

        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  id: res.message.id,
                  content: res.message.content,
                  citations: res.citations,
                  isStreaming: false,
                }
              : m
          )
        );

        // Update session ID if new
        if (res.is_new_session || !currentSessionId) {
          setCurrentSessionId(res.session_id);
        }
      }

      // Refresh sessions list
      const sessionsRes = await api.sessions.list();
      setSessions(sessionsRes.sessions || []);

      // Get the session ID from the first message if we don't have one
      if (!currentSessionId) {
        const newSessions = sessionsRes.sessions || [];
        if (newSessions.length > 0) {
          setCurrentSessionId(newSessions[0].id);
        }
      }
    } catch (err) {
      console.error('Chat error:', err);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: `Error: ${err instanceof Error ? err.message : 'Failed to get response'}`,
                isStreaming: false,
              }
            : m
        )
      );
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] -m-8">
      {/* Session Sidebar */}
      <aside className="w-72 bg-dark-900 border-r border-dark-700 flex flex-col" aria-label="Chat sessions">
        <div className="p-4 border-b border-dark-700">
          <h2 className="sr-only">Sessions</h2>
          <button onClick={handleNewChat} className="btn btn-primary w-full">
            + New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          {sessions.length === 0 ? (
            <p className="text-gray-400 text-sm text-center py-4">No conversations yet</p>
          ) : (
            <ul className="space-y-1">
              {sessions.map((session) => (
                <li key={session.id} className="flex items-center group">
                  <button
                    onClick={() => handleSelectSession(session.id)}
                    className={`flex-1 text-left px-3 py-2 rounded-lg transition-colors ${
                      session.id === currentSessionId
                        ? 'bg-primary-600/20 text-primary-400'
                        : 'text-gray-400 hover:bg-dark-800 hover:text-gray-300'
                    }`}
                    aria-current={session.id === currentSessionId ? 'true' : undefined}
                  >
                    <p className="text-sm font-medium truncate">{session.title || 'Untitled'}</p>
                    <p className="text-xs text-gray-400">{session.message_count} messages</p>
                  </button>
                  <button
                    onClick={(e) => handleDeleteSession(session.id, e)}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400 transition-opacity flex-shrink-0"
                    aria-label={`Delete session: ${session.title || 'Untitled'}`}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col bg-dark-950">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 bg-gradient-to-br from-primary-500 to-purple-600 rounded-2xl mb-6" aria-hidden="true"></div>
              <h2 className="text-xl font-semibold text-white mb-2">Start a conversation</h2>
              <p className="text-gray-400 max-w-md">
                Ask questions about your invoices and documents. RAG-powered search retrieves relevant context.
              </p>
            </div>
          ) : (
            <div
              className="max-w-3xl mx-auto space-y-6"
              role="log"
              aria-label="Chat messages"
              aria-live="polite"
            >
              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className="border-t border-dark-700 p-4 bg-dark-900">
          <div className="max-w-3xl mx-auto">
            <div className="flex gap-3">
              <div className="flex-1 relative">
                <label htmlFor="chat-input" className="sr-only">Chat message</label>
                <textarea
                  id="chat-input"
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Type your message..."
                  rows={1}
                  className="input resize-none pr-12"
                  aria-label="Type your message"
                  style={{ minHeight: '48px', maxHeight: '200px' }}
                />
              </div>
              <button
                onClick={handleSend}
                disabled={loading || !input.trim()}
                className="btn btn-primary px-6 disabled:opacity-50"
                aria-label={loading ? 'Sending message...' : 'Send message'}
              >
                {loading ? (
                  <span role="status">
                    <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    <span className="sr-only">Sending...</span>
                  </span>
                ) : (
                  'Send'
                )}
              </button>
            </div>

            <div className="flex items-center gap-4 mt-3">
              <label className="flex items-center gap-2 cursor-pointer text-sm">
                <input
                  type="checkbox"
                  checked={useRag}
                  onChange={(e) => setUseRag(e.target.checked)}
                  className="w-4 h-4 accent-primary-500"
                />
                <span className="text-gray-400">Use RAG</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer text-sm">
                <input
                  type="checkbox"
                  checked={useStream}
                  onChange={(e) => setUseStream(e.target.checked)}
                  className="w-4 h-4 accent-primary-500"
                />
                <span className="text-gray-400">Stream response</span>
              </label>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: DisplayMessage }) {
  const isUser = message.role === 'user';

  return (
    <div
      className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
      role="article"
      aria-label={`${isUser ? 'You' : 'Assistant'}`}
    >
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 ${
          isUser
            ? 'bg-primary-600 text-white rounded-br-md'
            : 'bg-dark-800 text-gray-200 rounded-bl-md'
        }`}
      >
        <div className="whitespace-pre-wrap break-words">
          {message.content || (message.isStreaming && (
            <span className="inline-flex gap-1" role="status" aria-label="Assistant is typing">
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} aria-hidden="true"></span>
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} aria-hidden="true"></span>
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} aria-hidden="true"></span>
            </span>
          ))}
        </div>

        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <div className="mt-3 pt-3 border-t border-dark-700">
            <p className="text-xs text-gray-400 mb-2">Sources:</p>
            <div className="flex flex-wrap gap-2">
              {message.citations.map((c, i) => (
                <span
                  key={i}
                  className="text-xs bg-dark-700 text-gray-400 px-2 py-1 rounded"
                  title={c.snippet || undefined}
                >
                  {c.file_name || c.document_id}
                  {c.page_number && ` (p.${c.page_number})`}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Streaming indicator */}
        {message.isStreaming && message.content && (
          <span className="inline-block w-2 h-4 bg-gray-400 ml-1 animate-pulse" aria-hidden="true"></span>
        )}
      </div>
    </div>
  );
}
