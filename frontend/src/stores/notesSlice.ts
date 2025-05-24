import { type PayloadAction, createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import axios from 'axios';
import { v4 as uuidv4 } from 'uuid'; // For generating unique IDs for context entries

// Define the base URL for the API
const API_URL = 'http://localhost:8000/api';

// Define the structure of a Note (mirroring the Pydantic model in the backend)
export interface Note {
  note_id: number; // This is the version-specific ID
  original_note_id: number; // This is the ID for the note lineage
  id: number; // Frontend will use 'id', mapped from original_note_id
  title: string;
  content: string;
  created_at: string; // ISO date string
  tags: string[];
  properties?: Record<string, any>;
  is_latest_version?: boolean;
  is_deleted?: boolean;
  deleted_at?: string | null;
}

// New interface for AI Context History entries
export interface AIContextEntry {
  id: string; // Unique ID for the entry
  queryText: string; // The user query that triggered this context, or a system message
  actionType: string; // e.g., "CREATE_NOTE", "FIND_NOTES"
  notes: Note[]; // Notes relevant to this action
  timestamp: string; // ISO string timestamp
}

// Define the state structure for notes
export interface NotesState {
  notes: Note[];
  aiContextHistory: AIContextEntry[]; // Stores a history of AI interactions and their notes
  noteListViewMode: 'all' | 'contextual'; // 'contextual' will now refer to this history view
  loading: boolean;
  error: string | null;
}

const MAX_CONTEXT_HISTORY_LENGTH = 10; // Max number of AI context entries to keep

const initialState: NotesState = {
  notes: [],
  aiContextHistory: [],
  noteListViewMode: 'all',
  loading: false,
  error: null,
};

// Async thunk to fetch notes from the backend
export const fetchNotes = createAsyncThunk('notes/fetchNotes', async (_, { rejectWithValue }) => {  try {
    const response = await axios.get<Omit<Note, 'id'>[]>(`${API_URL}/notes/`); // Expect backend notes without 'id'
    // Map original_note_id to id for simpler use in some UI components if needed,
    // and ensure all fields of Note are present.
        const notes = response.data.map(note => ({ ...note, id: note.original_note_id } as Note));    return notes;
  } catch (err: any) {
    let errorPayload: any = 'An unknown error occurred';
    if (err.response) {
      console.error('[Thunk: notes/fetchNotes] API error response:', err.response.data, 'Status:', err.response.status);
      errorPayload = err.response.data;
    } else if (err.request) {
      console.error('[Thunk: notes/fetchNotes] API no response received:', err.request);
      errorPayload = 'No response received from server.';
    } else {
      console.error('[Thunk: notes/fetchNotes] Error setting up API request:', err.message);
      errorPayload = err.message;
    }
    return rejectWithValue(errorPayload);
  }
});

// Define the structure for action_data if received from WebSocket
export interface AIActionData {
  action_type: string; // e.g., "CREATE_NOTE", "FIND_NOTES", "DELETE_NOTE", "UPDATE_NOTE_TAGS"
  // Notes from backend won't have 'id' field directly, it's derived from original_note_id
  notes?: Omit<Note, 'id'>[]; // Full note objects related to the action, without frontend 'id' - Optional
  deleted_note_id?: number; // Kept for potential single delete scenarios if any, but prefer deleted_note_ids
  deleted_note_ids?: number[]; // For multiple deletions
  failed_to_delete_ids?: (number | string)[]; // IDs that failed deletion
  query_text?: string; // Add the user query text to action_data from backend if possible
}

const notesSlice = createSlice({
  name: 'notes',
  initialState,
  reducers: {
    updateAIContextHistory: (state, action: PayloadAction<AIActionData>) => {
      const { action_type, notes, deleted_note_id, deleted_note_ids, query_text } = action.payload;
      state.error = null;

      let newContextEntry: AIContextEntry | null = null;
      let idsToDelete: number[] = [];

      if (deleted_note_ids && deleted_note_ids.length > 0) {
        idsToDelete.push(...deleted_note_ids);
      } else if (deleted_note_id) { // Fallback for single ID if still used
        idsToDelete.push(deleted_note_id);
      }

      if (action_type === 'DELETE_NOTE' && idsToDelete.length > 0) {
        state.notes = state.notes.filter(note => !idsToDelete.includes(note.original_note_id));
        // Also remove from any existing entries in aiContextHistory
        state.aiContextHistory = state.aiContextHistory.map(entry => ({
          ...entry,
          notes: entry.notes.filter(note => !idsToDelete.includes(note.original_note_id))
        })).filter(entry => entry.notes.length > 0 || action_type !== 'DELETE_NOTE'); // Keep non-delete entries
      } else if (notes && notes.length > 0) { // For CREATE, FIND, UPDATE - actions that yield notes
        const processedNotes = notes.map(note => ({ ...note, id: note.original_note_id } as Note));
        
        // If the action involves updating existing notes (e.g., adding tags), update these notes across the entire history.
        // We can identify an update if the action_type suggests it, or if processedNotes contains notes
        // that already exist in the history (matched by original_note_id).
        // For simplicity, we'll assume any action that provides notes (other than pure FIND_NOTES that might just be a view)
        // could be an update (CREATE_NOTE also provides the initial state, ADD_TAGS_TO_NOTE provides the updated state).
        if (action_type === 'ADD_TAGS_TO_NOTE' || action_type === 'UPDATE_NOTE') { // Add other update-like action_types if necessary
          processedNotes.forEach(updatedNote => {
            state.aiContextHistory = state.aiContextHistory.map(entry => ({
              ...entry,
              notes: entry.notes.map(noteInHistory => 
                noteInHistory.original_note_id === updatedNote.original_note_id 
                  ? updatedNote // Replace with the updated version
                  : noteInHistory
              )
            }));
            // Also update the main notes list if the note exists there
            const mainNoteIndex = state.notes.findIndex(n => n.original_note_id === updatedNote.original_note_id);
            if (mainNoteIndex !== -1) {
              state.notes[mainNoteIndex] = updatedNote;
            }
          });
        }

        newContextEntry = {
          id: uuidv4(),
          queryText: query_text || `Action: ${action_type.replace("_", " ").toLowerCase()}`,
          actionType: action_type,
          notes: processedNotes,
          timestamp: new Date().toISOString(),
        };
      }

      if (newContextEntry) {
        state.aiContextHistory.unshift(newContextEntry); // Add to the beginning of the history
        if (state.aiContextHistory.length > MAX_CONTEXT_HISTORY_LENGTH) {
          state.aiContextHistory.pop(); // Remove the oldest entry if history is too long
        }
      }
      
      // Handle main notes list for CREATE
      if (action_type === 'CREATE_NOTE' && notes && notes.length > 0) {
        const newNoteData = notes[0];
        const newNote = { ...newNoteData, id: newNoteData.original_note_id } as Note;
        if (!state.notes.find(n => n.original_note_id === newNote.original_note_id)) {
          state.notes.unshift(newNote);
        }
      }
      
      // Switch to contextual view if a new entry was added, or if it's not a delete action that cleared context
      if (newContextEntry || (action_type !== 'DELETE_NOTE' && state.aiContextHistory.length > 0)) {
        state.noteListViewMode = 'contextual';
      } else if (action_type === 'DELETE_NOTE' && state.aiContextHistory.length === 0 && idsToDelete.length > 0) {
         state.noteListViewMode = 'all';
      }
    },
    setNoteListViewMode: (state, action: PayloadAction<'all' | 'contextual'>) => {
      state.noteListViewMode = action.payload;
    },
    clearAIContextHistory: (state) => {
      state.aiContextHistory = [];
      state.noteListViewMode = 'all'; // Switch to all notes view when history is cleared
    }
  },
  extraReducers: (builder) => {
    builder
            .addCase(fetchNotes.pending, (state) => {        state.loading = true;
        state.error = null;
      })
            .addCase(fetchNotes.fulfilled, (state, action: PayloadAction<Note[]>) => {        state.notes = action.payload;
        state.loading = false;
      })
      .addCase(fetchNotes.rejected, (state, action) => {
        console.error('[Reducer: notes/fetchNotes/rejected] Failed to load notes:', action.payload);
        state.loading = false;
        state.error = action.payload as string;
      });
  },
});

// Corrected export of actions
export const { updateAIContextHistory, setNoteListViewMode, clearAIContextHistory } = notesSlice.actions;

// Selectors
export const selectAllNotes = (state: { notes: NotesState }) => state.notes.notes;
export const selectAIContextHistory = (state: { notes: NotesState }) => state.notes.aiContextHistory;
export const selectNoteListViewMode = (state: { notes: NotesState }) => state.notes.noteListViewMode;
export const selectNotesLoading = (state: { notes: NotesState }) => state.notes.loading;
export const selectNotesError = (state: { notes: NotesState }) => state.notes.error;

export default notesSlice.reducer;

// Optional: Export actions if you have synchronous reducers
// export const { addNoteOptimistic } = notesSlice.actions; 