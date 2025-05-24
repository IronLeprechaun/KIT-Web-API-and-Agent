import React, { useEffect, useState, useRef, type FormEvent } from 'react';
import {
  Box,
  TextField,
  Button,
  Paper,
  Typography,
  List,
  ListItem,
  ListItemText,
  Divider,
  Chip,
  CircularProgress,
  Alert
} from '@mui/material';
import { useDispatch, useSelector } from 'react-redux';
import {
  addMessage,
  setConnectionStatus,
  selectChatMessages,
  selectChatConnectionStatus,
  type ChatMessage
} from '../stores/chatSlice';
import { fetchNotes, updateAIContextHistory, type AIActionData } from '../stores/notesSlice';
import type { AppDispatch } from '../stores/store';
import SendIcon from '@mui/icons-material/Send';
import ReactMarkdown from 'react-markdown';
import { FrontendLogger } from '../services/frontendLogger';

const AI_WEBSOCKET_URL = 'ws://localhost:8000/api/ai/ws';

const ChatInterface: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>();
  const messages = useSelector(selectChatMessages);
  const connectionStatus = useSelector(selectChatConnectionStatus);
  
  const [inputText, setInputText] = useState('');
  const ws = useRef<WebSocket | null>(null);
  const messageListRef = useRef<HTMLUListElement>(null); // For scrolling to bottom

  // Store the last user query to associate with AI action data
  const lastUserQueryRef = useRef<string>('');

  useEffect(() => {
    // Scroll to bottom when new messages are added
    if (messageListRef.current) {
      messageListRef.current.scrollTop = messageListRef.current.scrollHeight;
    }
  }, [messages]);

  const connectWebSocket = () => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) return;

    dispatch(setConnectionStatus('connecting'));
    ws.current = new WebSocket(AI_WEBSOCKET_URL);
    FrontendLogger.info('Attempting WebSocket connection...');

    ws.current.onopen = () => {
      dispatch(setConnectionStatus('connected'));
      FrontendLogger.info('WebSocket connected.');
    };

    ws.current.onmessage = (event) => {
      try {
        const receivedData = JSON.parse(event.data as string);
        FrontendLogger.debug('WebSocket message received:', receivedData);

        if (receivedData.error) {
          console.error('AI Error:', receivedData.error);
          FrontendLogger.error('AI Error from backend:', receivedData.error);
          dispatch(addMessage({
            id: Date.now().toString(),
            text: `Error: ${receivedData.error}`,
            sender: 'system',
            timestamp: new Date().toISOString(),
          }));
          return;
        }

        // Correctly access the response_text field from the backend
        const aiResponseText = receivedData.response_text || 'No response text could be extracted.';
        let combinedAiMessageText = aiResponseText;

        // If action_feedback is present, append it to the main AI response for history
        // and for display as a single AI turn.
        if (receivedData.action_feedback && receivedData.action_feedback.trim() !== '') {
          combinedAiMessageText += `\n\n${receivedData.action_feedback}`; // Combine them, separated by newlines
        }

        dispatch(addMessage({
          id: Date.now().toString(),
          text: combinedAiMessageText, // Use the combined text
          sender: 'ai',
          timestamp: new Date().toISOString(),
        }));

        // Action feedback is now part of the main AI message, so no need to dispatch it separately.
        // However, we still need the logic to refetch notes if a CUD operation occurred.
        if (receivedData.action_feedback) {
          const feedbackLowerCase = receivedData.action_feedback.toLowerCase();
                      if (feedbackLowerCase.includes('created note') ||               feedbackLowerCase.includes('updated note') ||               feedbackLowerCase.includes('deleted note')) {             dispatch(fetchNotes());
          }
        }

        // Handle AI Action Data for contextual view
        if (receivedData.action_data) {
          const actionData = receivedData.action_data as Omit<AIActionData, 'query_text'>;
          // Add the last user query to the action data
          const completeActionData: AIActionData = {
            ...actionData,
            query_text: lastUserQueryRef.current || "User query not captured"
          };
          dispatch(updateAIContextHistory(completeActionData)); 
          lastUserQueryRef.current = ''; // Clear after use or decide on a better strategy
        }

      } catch (error) {
        console.error('Failed to parse AI response:', error);
        FrontendLogger.error('Failed to parse AI WebSocket response:', { error, rawData: event.data });
        dispatch(addMessage({
          id: Date.now().toString(),
          text: 'Received an unparseable message from AI.',
          sender: 'system',
          timestamp: new Date().toISOString(),
        }));
      }
    };

    ws.current.onerror = (error) => {
      console.error('AI WebSocket error:', error);
      FrontendLogger.error('AI WebSocket error event:', error);
      dispatch(setConnectionStatus('error'));
    };

    ws.current.onclose = () => {
      FrontendLogger.info('WebSocket onclose event triggered.');
      if (ws.current && ws.current.readyState !== WebSocket.OPEN && connectionStatus !== 'error') {
         dispatch(setConnectionStatus('disconnected'));
      }
      
      FrontendLogger.info('Attempting WebSocket reconnection due to close...');
      setTimeout(() => {
        connectWebSocket();
      }, 3000); // Simple reconnect
    };
  };

  useEffect(() => {
    connectWebSocket();
    return () => {
      ws.current?.close();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dispatch]); // Only run on mount and unmount

  const handleSend = (e: FormEvent) => {
    e.preventDefault(); // Prevent default form submission which reloads the page
    if (inputText.trim() !== '' && ws.current && ws.current.readyState === WebSocket.OPEN) {
      const userMessage: ChatMessage = {
        id: Date.now().toString(),
        text: inputText,
        sender: 'user',
        timestamp: new Date().toISOString(),
      };
      dispatch(addMessage(userMessage));
      
      lastUserQueryRef.current = inputText; // Store the query
      FrontendLogger.info(`User sending message: ${inputText}`, { historyLength: messages.length });

      // Prepare conversation history for the backend
      const backendHistory = messages
        .filter(msg => msg.sender === 'user' || msg.sender === 'ai')
        .map(msg => ({
          role: msg.sender === 'user' ? 'user' : 'model',
          text: msg.text,
        }));

      // Add the current user's input to the history being sent,
      // as `messages` selector might not have updated yet with the latest userMessage
      // Or, ensure `messages` includes the latest userMessage before this step.
      // For simplicity, let's rely on the existing `messages` which should update quickly.
      // If issues arise, we can explicitly add userMessage to backendHistory here.

      ws.current.send(JSON.stringify({
        query: inputText,
        conversation_history: backendHistory 
        // user_name: can be added here if available
      }));
      
      setInputText('');
    } else if (!ws.current || ws.current.readyState !== WebSocket.OPEN) {
        dispatch(addMessage({
            id: Date.now().toString(),
            text: 'Not connected to AI. Attempting to reconnect...',
            sender: 'system',
            timestamp: new Date().toISOString(),
          }));
        FrontendLogger.warn('Attempted to send message while not connected. Triggering reconnect.');
    }
  };
  
  const getConnectionChip = () => {
    let chipColor: "default" | "primary" | "secondary" | "error" | "info" | "success" | "warning" = "default";
    let progressColor: "inherit" | "primary" | "secondary" | "error" | "info" | "success" | "warning" = "info"; // Default for connecting
    const chipLabel = connectionStatus;

    switch (connectionStatus) {
      case 'connected': 
        chipColor = 'success'; 
        break;
      case 'connecting': 
        chipColor = 'info'; 
        progressColor = 'info';
        break;
      case 'disconnected': 
        chipColor = 'default'; 
        break;
      case 'error': 
        chipColor = 'error'; 
        progressColor = 'error';
        break;
    }
    return (
        <Box sx={{display: 'flex', alignItems: 'center', gap: 0.5}}>
            {connectionStatus === 'connecting' && <CircularProgress size={14} color={progressColor}/>}
            <Chip label={chipLabel} color={chipColor} size="small" />
        </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', flexGrow: 1 }}>
      <Box sx={{display: 'flex', justifyContent:'space-between', alignItems:'center', p: '4px 8px', borderBottom: '1px solid divider' , flexShrink:0}}>
        <Typography variant="subtitle1" sx={{ mb:0, fontWeight: 'medium'}}>
          Agent Chat
        </Typography>
        {getConnectionChip()}
      </Box>
      <Paper 
        elevation={0} 
        sx={{ 
          flexGrow: 1, 
          overflowY: 'auto', 
          p: 1, 
          mb: 0,
          backgroundColor: 'grey.100',
          borderRadius:0
        }}
      >
        <List ref={messageListRef}>
          {messages.map((msg) => (
            <React.Fragment key={msg.id}>
              <ListItem sx={{ 
                display: 'flex', 
                flexDirection: 'column',
                alignItems: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                mb: 0.5
              }}>
                <Paper elevation={1} sx={{ 
                    p: '4px 10px',
                    borderRadius: msg.sender === 'user' ? '12px 12px 2px 12px' : '2px 12px 12px 12px',
                    bgcolor: msg.sender === 'user' ? 'primary.main' : (msg.sender === 'ai' ? 'secondary.main' : 'background.paper'), 
                    color: msg.sender === 'user' || msg.sender === 'ai' ? 'common.white' : 'text.primary',
                    maxWidth: '80%',
                    wordBreak: 'break-word',
                    boxShadow: 'sm'
                  }}>
                  <ListItemText 
                    primaryTypographyProps={{
                      variant:'body2',
                      component: 'div',
                      sx: {
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        '& p': { margin: 0 },
                        '& ul': { paddingLeft: '20px', marginTop: '0.25em', marginBottom: '0.25em'},
                        '& li': { marginBottom: '0.1em', marginTop: '0.1em'},
                        '& li > p': { margin: 0 },
                        '& li > ul': { marginTop: '0.1em', marginBottom: '0.1em' },
                        '& strong': { fontWeight: 'bold' },
                      }
                    }}
                  >
                    <ReactMarkdown>{msg.text}</ReactMarkdown>
                  </ListItemText>
                </Paper>
                 <Typography variant="caption" sx={{color: 'text.secondary', mt:0.25, px:0.5}}>
                    {msg.sender !== 'system' ? `${msg.sender} - ${new Date(msg.timestamp).toLocaleTimeString()}` : new Date(msg.timestamp).toLocaleTimeString()}
                </Typography>
              </ListItem>
            </React.Fragment>
          ))}
        </List>
      </Paper>
      <Box component="form" onSubmit={handleSend} sx={{ display: 'flex', alignItems: 'center', flexShrink: 0, p: 1, borderTop: '1px solid divider', bgcolor:'background.paper' }}>
        <TextField
          fullWidth
          variant="outlined"
          size="small"
          placeholder="Type your message..."
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyPress={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSend(e as any); // Cast to any to satisfy FormEvent, though not strictly needed here
            }
          }}
          sx={{ mr: 1 }}
        />
        <Button type="submit" variant="contained" color="primary" onClick={(e) => handleSend(e as any)} disabled={connectionStatus !== 'connected' && connectionStatus !== 'error'} endIcon={<SendIcon />}>
          Send
        </Button>
      </Box>
    </Box>
  );
};

export default ChatInterface; 