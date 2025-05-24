/// <reference types="vitest/globals" />

import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import configureStore from 'redux-mock-store';
import NoteList from './NoteList';
import { type RootState } from '../stores/store';
import { type NotesState, type Note, type AIContextEntry } from '../stores/notesSlice'; // Import necessary types
import { type ChatState, type ChatMessage } from '../stores/chatSlice'; // Import necessary types

// Define a complete initial state for the notes slice
const initialNotesState: NotesState = {
  notes: [],
  aiContextHistory: [],
  noteListViewMode: 'all',
  loading: false,
  error: null,
};

// Define a complete initial state for the chat slice
const initialChatState: ChatState = {
  messages: [],
  connectionStatus: 'disconnected',
};

// Mock the necessary parts of the Redux store
const mockStore = configureStore<RootState>([]);

describe('NoteList Component', () => {
  let store: ReturnType<typeof mockStore>;

  beforeEach(() => {
    const rootStateFull: RootState = {
      notes: { ...initialNotesState, noteListViewMode: 'all' },
      chat: { ...initialChatState },
    };
    store = mockStore(rootStateFull);
    store.dispatch = vi.fn(); // Mock dispatch
  });

  test('renders "My Notes" heading by default', () => {
    render(
      <Provider store={store}>
        <NoteList />
      </Provider>
    );
    expect(screen.getByText((content) => content.startsWith('My Notes ('))).toBeInTheDocument();
  });

  test('renders "AI Context History" heading when view mode is contextual', () => {
    const contextualNotesState: NotesState = {
      ...initialNotesState,
      noteListViewMode: 'contextual',
      aiContextHistory: [], 
    };
    const contextualRootState: RootState = {
        notes: contextualNotesState,
        chat: { ...initialChatState },
    };
    
    store = mockStore(contextualRootState);
    store.dispatch = vi.fn(); // Mock dispatch

    render(
      <Provider store={store}>
        <NoteList />
      </Provider>
    );
    expect(screen.getByText((content) => content.startsWith('AI Context History ('))).toBeInTheDocument();
  });
});