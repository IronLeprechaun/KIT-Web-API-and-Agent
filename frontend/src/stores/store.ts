import { configureStore } from '@reduxjs/toolkit';
import notesReducer from './notesSlice'; // Import the notes reducer
import chatReducer from './chatSlice'; // Import the chat reducer
// Import your reducers here
// Example: import notesReducer from './notesSlice';

export const store = configureStore({
  reducer: {
    notes: notesReducer, // Add the notes reducer to the store
    chat: chatReducer, // Add the chat reducer to the store
    // Add reducers here
    // notes: notesReducer,
    // You can add other reducers here as your application grows
    // e.g., user: userReducer,
  },
});

// Infer the `RootState` and `AppDispatch` types from the store itself
export type RootState = ReturnType<typeof store.getState>;
// Inferred type: {notes: NotesState, users: UsersState, ...}
export type AppDispatch = typeof store.dispatch;

export default store; 