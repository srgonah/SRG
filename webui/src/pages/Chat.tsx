import { useCallback, useEffect, useRef, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Divider from "@mui/material/Divider";
import Grid from "@mui/material/Grid2";
import IconButton from "@mui/material/IconButton";
import LinearProgress from "@mui/material/LinearProgress";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemSecondaryAction from "@mui/material/ListItemSecondaryAction";
import ListItemText from "@mui/material/ListItemText";
import Paper from "@mui/material/Paper";
import Skeleton from "@mui/material/Skeleton";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import AddIcon from "@mui/icons-material/Add";
import ChatIcon from "@mui/icons-material/Chat";
import DeleteIcon from "@mui/icons-material/Delete";
import SendIcon from "@mui/icons-material/Send";
import { chat, sessions } from "../api/client";
import type { ChatMessage, ChatSession } from "../types/api";

export default function Chat() {
  // Session state
  const [sessionList, setSessionList] = useState<ChatSession[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [sessionsError, setSessionsError] = useState<string | null>(null);

  // Messages state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);

  // Input state
  const [inputValue, setInputValue] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Fetch sessions
  const fetchSessions = useCallback(async () => {
    try {
      setSessionsLoading(true);
      setSessionsError(null);
      const response = await sessions.list(50, 0);
      setSessionList(response.sessions);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load sessions";
      setSessionsError(message);
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  // Fetch messages for selected session
  const fetchMessages = useCallback(async (sessionId: string) => {
    try {
      setMessagesLoading(true);
      const msgs = await sessions.messages(sessionId, 100);
      setMessages(msgs);
    } catch (err) {
      console.error("Failed to load messages:", err);
      setMessages([]);
    } finally {
      setMessagesLoading(false);
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  // Fetch messages when session changes
  useEffect(() => {
    if (selectedSessionId) {
      fetchMessages(selectedSessionId);
    } else {
      setMessages([]);
    }
  }, [selectedSessionId, fetchMessages]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Create new session
  const handleNewChat = async () => {
    try {
      const newSession = await sessions.create({ title: "New Conversation" });
      setSessionList((prev) => [newSession, ...prev]);
      setSelectedSessionId(newSession.id);
      setMessages([]);
      inputRef.current?.focus();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to create session";
      setSendError(message);
    }
  };

  // Delete session
  const handleDeleteSession = async (sessionId: string, event: React.MouseEvent) => {
    event.stopPropagation();
    try {
      await sessions.remove(sessionId);
      setSessionList((prev) => prev.filter((s) => s.id !== sessionId));
      if (selectedSessionId === sessionId) {
        setSelectedSessionId(null);
        setMessages([]);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to delete session";
      setSendError(message);
    }
  };

  // Send message
  const handleSend = async () => {
    if (!inputValue.trim() || sending) return;

    const messageContent = inputValue.trim();
    setInputValue("");
    setSending(true);
    setSendError(null);

    // Optimistically add user message
    const tempUserMessage: ChatMessage = {
      id: `temp-${Date.now()}`,
      role: "user",
      content: messageContent,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMessage]);

    try {
      const response = await chat.send({
        message: messageContent,
        session_id: selectedSessionId ?? undefined,
        use_rag: true,
        include_sources: true,
      });

      // If this was a new session, select it
      if (response.is_new_session || !selectedSessionId) {
        setSelectedSessionId(response.session_id);
        // Refresh session list to include the new session
        fetchSessions();
      }

      // Update messages with the actual response
      setMessages((prev) => {
        // Remove temp message and add both user and assistant messages
        const withoutTemp = prev.filter((m) => m.id !== tempUserMessage.id);
        return [
          ...withoutTemp,
          {
            id: `user-${Date.now()}`,
            role: "user",
            content: messageContent,
            created_at: new Date().toISOString(),
          },
          response.message,
        ];
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to send message";
      setSendError(message);
      // Remove optimistic message on error
      setMessages((prev) => prev.filter((m) => m.id !== tempUserMessage.id));
    } finally {
      setSending(false);
    }
  };

  // Handle key press in input
  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  // Format timestamp
  const formatTime = (dateString: string): string => {
    return new Date(dateString).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // Format session date
  const formatSessionDate = (dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return "Today";
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays} days ago`;
    return date.toLocaleDateString();
  };

  // Render message bubble
  const renderMessage = (message: ChatMessage) => {
    const isUser = message.role === "user";
    return (
      <Box
        key={message.id}
        sx={{
          display: "flex",
          justifyContent: isUser ? "flex-end" : "flex-start",
          mb: 2,
        }}
      >
        <Paper
          elevation={0}
          sx={{
            maxWidth: "70%",
            p: 2,
            borderRadius: 2,
            ...(isUser
              ? {
                  bgcolor: "primary.main",
                  color: "primary.contrastText",
                }
              : {
                  bgcolor: "grey.100",
                  color: "text.primary",
                }),
          }}
        >
          <Typography
            variant="body2"
            sx={{
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
            }}
          >
            {message.content}
          </Typography>
          <Typography
            variant="caption"
            sx={{
              display: "block",
              mt: 1,
              opacity: 0.7,
              textAlign: isUser ? "right" : "left",
            }}
          >
            {formatTime(message.created_at)}
          </Typography>
        </Paper>
      </Box>
    );
  };

  // Render typing indicator
  const renderTypingIndicator = () => (
    <Box sx={{ display: "flex", justifyContent: "flex-start", mb: 2 }}>
      <Paper
        elevation={0}
        sx={{
          p: 2,
          borderRadius: 2,
          bgcolor: "grey.100",
        }}
      >
        <Box sx={{ display: "flex", gap: 0.5, alignItems: "center" }}>
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              bgcolor: "grey.400",
              animation: "pulse 1.4s infinite ease-in-out",
              animationDelay: "0s",
              "@keyframes pulse": {
                "0%, 80%, 100%": { opacity: 0.4 },
                "40%": { opacity: 1 },
              },
            }}
          />
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              bgcolor: "grey.400",
              animation: "pulse 1.4s infinite ease-in-out",
              animationDelay: "0.2s",
            }}
          />
          <Box
            sx={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              bgcolor: "grey.400",
              animation: "pulse 1.4s infinite ease-in-out",
              animationDelay: "0.4s",
            }}
          />
        </Box>
      </Paper>
    </Box>
  );

  // Render session list loading skeleton
  const renderSessionsSkeleton = () => (
    <List>
      {[1, 2, 3, 4, 5].map((i) => (
        <ListItemButton key={i} disabled>
          <ListItemText
            primary={<Skeleton variant="text" width={150} />}
            secondary={<Skeleton variant="text" width={80} />}
          />
        </ListItemButton>
      ))}
    </List>
  );

  return (
    <Box sx={{ height: "calc(100vh - 180px)", display: "flex", flexDirection: "column" }}>
      <Typography variant="h5" sx={{ mb: 2 }}>
        Chat
      </Typography>

      <Grid container spacing={2} sx={{ flexGrow: 1, minHeight: 0 }}>
        {/* Sidebar - Sessions list */}
        <Grid size={{ xs: 12, md: 3 }}>
          <Paper sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
            {/* New chat button */}
            <Box sx={{ p: 2 }}>
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                fullWidth
                onClick={handleNewChat}
              >
                New Chat
              </Button>
            </Box>

            <Divider />

            {/* Sessions list */}
            <Box sx={{ flexGrow: 1, overflow: "auto" }}>
              {sessionsError && (
                <Alert severity="error" sx={{ m: 2 }}>
                  {sessionsError}
                </Alert>
              )}

              {sessionsLoading ? (
                renderSessionsSkeleton()
              ) : sessionList.length === 0 ? (
                <Box sx={{ p: 3, textAlign: "center" }}>
                  <ChatIcon sx={{ fontSize: 32, color: "text.secondary", mb: 1 }} />
                  <Typography variant="body2" color="text.secondary">
                    No conversations yet
                  </Typography>
                </Box>
              ) : (
                <List>
                  {sessionList.map((session) => (
                    <ListItemButton
                      key={session.id}
                      selected={selectedSessionId === session.id}
                      onClick={() => setSelectedSessionId(session.id)}
                      sx={{
                        "&.Mui-selected": {
                          bgcolor: "action.selected",
                        },
                      }}
                    >
                      <ListItemText
                        primary={
                          <Typography
                            variant="body2"
                            noWrap
                            sx={{ fontWeight: selectedSessionId === session.id ? 600 : 400 }}
                          >
                            {session.title || "Untitled"}
                          </Typography>
                        }
                        secondary={
                          <Typography variant="caption" color="text.secondary">
                            {formatSessionDate(session.updated_at)}
                          </Typography>
                        }
                      />
                      <ListItemSecondaryAction>
                        <IconButton
                          edge="end"
                          size="small"
                          onClick={(e) => handleDeleteSession(session.id, e)}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </ListItemSecondaryAction>
                    </ListItemButton>
                  ))}
                </List>
              )}
            </Box>
          </Paper>
        </Grid>

        {/* Main chat area */}
        <Grid size={{ xs: 12, md: 9 }}>
          <Paper sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
            {selectedSessionId ? (
              <>
                {/* Messages area */}
                <Box
                  sx={{
                    flexGrow: 1,
                    overflow: "auto",
                    p: 2,
                    display: "flex",
                    flexDirection: "column",
                  }}
                >
                  {messagesLoading ? (
                    <Box sx={{ p: 2 }}>
                      {[1, 2, 3].map((i) => (
                        <Box key={i} sx={{ mb: 2 }}>
                          <Skeleton
                            variant="rectangular"
                            width={i % 2 === 0 ? "60%" : "40%"}
                            height={60}
                            sx={{
                              borderRadius: 2,
                              ml: i % 2 === 0 ? "auto" : 0,
                            }}
                          />
                        </Box>
                      ))}
                    </Box>
                  ) : messages.length === 0 ? (
                    <Box
                      sx={{
                        flexGrow: 1,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      <Box sx={{ textAlign: "center" }}>
                        <ChatIcon sx={{ fontSize: 48, color: "text.secondary", mb: 2 }} />
                        <Typography variant="h6" color="text.secondary" gutterBottom>
                          Start a conversation
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Type a message below to begin chatting
                        </Typography>
                      </Box>
                    </Box>
                  ) : (
                    <>
                      {messages.map(renderMessage)}
                      {sending && renderTypingIndicator()}
                      <div ref={messagesEndRef} />
                    </>
                  )}
                </Box>

                {/* Streaming indicator */}
                {sending && <LinearProgress sx={{ mx: 2 }} />}

                {/* Error message */}
                {sendError && (
                  <Alert severity="error" sx={{ mx: 2, mb: 1 }} onClose={() => setSendError(null)}>
                    {sendError}
                  </Alert>
                )}

                {/* Input area */}
                <Box sx={{ p: 2, borderTop: 1, borderColor: "divider" }}>
                  <Box sx={{ display: "flex", gap: 1 }}>
                    <TextField
                      inputRef={inputRef}
                      fullWidth
                      multiline
                      maxRows={4}
                      placeholder="Type a message... (Enter to send, Shift+Enter for new line)"
                      value={inputValue}
                      onChange={(e) => setInputValue(e.target.value)}
                      onKeyDown={handleKeyDown}
                      disabled={sending}
                      size="small"
                    />
                    <IconButton
                      color="primary"
                      onClick={handleSend}
                      disabled={!inputValue.trim() || sending}
                      sx={{
                        bgcolor: "primary.main",
                        color: "primary.contrastText",
                        "&:hover": {
                          bgcolor: "primary.dark",
                        },
                        "&.Mui-disabled": {
                          bgcolor: "action.disabledBackground",
                        },
                      }}
                    >
                      <SendIcon />
                    </IconButton>
                  </Box>
                </Box>
              </>
            ) : (
              /* Empty state - no session selected */
              <Box
                sx={{
                  flexGrow: 1,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Box sx={{ textAlign: "center", p: 4 }}>
                  <ChatIcon sx={{ fontSize: 64, color: "text.secondary", mb: 2 }} />
                  <Typography variant="h6" color="text.secondary" gutterBottom>
                    Select a conversation or start a new one
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                    Your chat history will appear on the left
                  </Typography>
                  <Button variant="contained" startIcon={<AddIcon />} onClick={handleNewChat}>
                    New Chat
                  </Button>
                </Box>
              </Box>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}
