import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from './store';

export interface ChatMessage {
  id: string; // Unique ID for each message (e.g., timestamp or UUID)
  text: string;
  sender: 'user' | 'ai' | 'system'; // 'system' for connection messages, errors, etc.
  timestamp: string; // ISO string
  // Optional: Add other relevant fields like in_reply_to_id, metadata, etc.
}

export interface ChatState {
  messages: ChatMessage[];
  connectionStatus: 'disconnected' | 'connecting' | 'connected' | 'error';
  // Optional: Add other state like isTyping, aiModelInUse, etc.
}

const initialState: ChatState = {
  messages: [],
  connectionStatus: 'disconnected',
};

const chatSlice = createSlice({
  name: 'chat',
  initialState,
  reducers: {
    addMessage: (state, action: PayloadAction<ChatMessage>) => {
      state.messages.push(action.payload);
    },
    setConnectionStatus: (state, action: PayloadAction<ChatState['connectionStatus']>) => {
      state.connectionStatus = action.payload;
    },
    clearChatMessages: (state) => {
      state.messages = [];
    },
    // You might add more reducers later, e.g., for editing/deleting messages if needed
  },
});

export const { addMessage, setConnectionStatus, clearChatMessages } = chatSlice.actions;

// Selectors
export const selectChatMessages = (state: RootState) => state.chat.messages;
export const selectChatConnectionStatus = (state: RootState) => state.chat.connectionStatus;

export default chatSlice.reducer; 