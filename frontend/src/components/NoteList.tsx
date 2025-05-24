import React, { useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import {
  List, ListItem, ListItemText, Typography, CircularProgress, Alert, Paper, Box, Chip, Tooltip, IconButton, FormGroup, FormControlLabel, Switch, Button, Divider
} from '@mui/material';
import {
  type Note, type AIContextEntry, fetchNotes, selectNotesError, selectNotesLoading, 
  selectAllNotes, setNoteListViewMode, selectAIContextHistory, selectNoteListViewMode,
  clearAIContextHistory
} from '../stores/notesSlice';
import { type AppDispatch } from '../stores/store';
import { format } from 'date-fns';
import { formatDistanceToNow } from 'date-fns/formatDistanceToNow';
import { parseISO } from 'date-fns/parseISO';
import LabelIcon from '@mui/icons-material/Label';
import NotesIcon from '@mui/icons-material/Notes';
import UpdateIcon from '@mui/icons-material/Update';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import HistoryIcon from '@mui/icons-material/History';
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep';

const NoteListItem: React.FC<{ note: Note }> = ({ note }) => (
  <ListItem 
    divider 
    sx={{ 
      flexDirection: 'column', 
      alignItems: 'flex-start', 
      mb: 1.5, py: 1.5, px:1, 
      border: '1px solid #e0e0e0', 
      borderRadius: '4px', 
      backgroundColor: 'white',
      '&:hover': {
        borderColor: 'primary.main',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
      }
    }}
  >
    <Box sx={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5}}>
      <Tooltip title={`Original ID: ${note.original_note_id} (Version ID: ${note.note_id})`}>
        <Typography variant="caption" color="textSecondary" sx={{ display: 'flex', alignItems: 'center' }}>
          <HelpOutlineIcon fontSize="inherit" sx={{ mr: 0.5 }} />
          ID: {note.original_note_id}
        </Typography>
      </Tooltip>
      <Typography variant="caption" color="textSecondary" sx={{ display: 'flex', alignItems: 'center' }}>
        <UpdateIcon fontSize="inherit" sx={{ mr: 0.5 }} />
        {formatDistanceToNow(parseISO(note.created_at + 'Z'), { addSuffix: true })}
      </Typography>
    </Box>
    <ListItemText
      primary={<Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{note.content}</Typography>}
      sx={{width: '100%'}}
    />
    {note.tags && note.tags.length > 0 && (
      <Box sx={{ mt: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
        {note.tags.map(tag => (
          <Chip 
            key={tag} 
            icon={<LabelIcon fontSize="small" />} 
            label={tag} 
            size="small" 
            variant="outlined" 
          />
        ))}
      </Box>
    )}
  </ListItem>
);

const NoteList: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>();
  const allNotes = useSelector(selectAllNotes);
  const aiContextHistory = useSelector(selectAIContextHistory);
  const noteListViewMode = useSelector(selectNoteListViewMode);
  const loading = useSelector(selectNotesLoading);
  const error = useSelector(selectNotesError);

  useEffect(() => {
    if (noteListViewMode === 'all' && (allNotes.length === 0 || error)) {
      dispatch(fetchNotes());
    }
  }, [dispatch, noteListViewMode, allNotes.length, error]);

  const handleViewModeChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    dispatch(setNoteListViewMode(event.target.checked ? 'contextual' : 'all'));
  };

  const handleClearHistory = () => {
    dispatch(clearAIContextHistory());
  };

  const renderAllNotes = () => (
    <List>
      {allNotes.map((note) => <NoteListItem key={`${note.original_note_id}-${note.note_id}`} note={note} />)}
    </List>
  );

  const renderAIContextHistory = () => (
    <Box>
      {aiContextHistory.map((entry) => (
        <Paper key={entry.id} elevation={2} sx={{ mb: 2, p: 1.5, backgroundColor:'grey.50' }}>
          <Box sx={{display:'flex', justifyContent:'space-between', alignItems:'center', mb:1}}>
            <Typography variant="subtitle2" sx={{fontWeight:'bold', display:'flex', alignItems:'center', gap:0.5}}>
                <HistoryIcon fontSize='small'/> Context for: "<Box component="span" sx={{fontStyle:'italic', color:'primary.main'}}>{entry.queryText.length > 50 ? entry.queryText.substring(0,50) + '...' : entry.queryText}</Box>"
            </Typography>
            <Typography variant="caption" color="textSecondary">
              {format(parseISO(entry.timestamp + 'Z'), 'Pp')}
            </Typography>
          </Box>
          <Divider sx={{my:1}}/>
          {entry.notes.length > 0 ? (
            <List disablePadding>
              {entry.notes.map((note) => <NoteListItem key={`${note.original_note_id}-${note.note_id}`} note={note} />)}
            </List>
          ) : (
            <Typography variant="body2" color="textSecondary" sx={{textAlign:'center', py:1}}>
              No notes associated with this context entry.
            </Typography>
          )}
        </Paper>
      ))}
    </Box>
  );

  let contentToDisplay;
  let displayTitle = "My Notes";
  let notesCount = 0;

  if (noteListViewMode === 'contextual') {
    contentToDisplay = renderAIContextHistory();
    displayTitle = "AI Context History";
    notesCount = aiContextHistory.reduce((acc, entry) => acc + entry.notes.length, 0);
  } else {
    contentToDisplay = renderAllNotes();
    notesCount = allNotes.length;
  }

  if (loading && ((noteListViewMode === 'all' && allNotes.length === 0) || (noteListViewMode === 'contextual' && aiContextHistory.length === 0))) {
    return <CircularProgress sx={{ display: 'block', margin: '20px auto' }} />;
  }

  if (error && noteListViewMode === 'all') { // Only show general fetch error for 'all' notes view
    return <Alert severity="error" sx={{ margin: 2 }}>Error fetching notes: {error}</Alert>;
  }

  return (
    <Box sx={{ p: '2px 0px 2px 8px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Paper elevation={1} sx={{ p: '8px 12px', mb: 1, flexShrink: 0 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6" gutterBottom component="div" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb:0, fontSize: '1.1rem'}}>
            <NotesIcon /> {displayTitle} ({noteListViewMode === 'contextual' ? `${aiContextHistory.length} entries, ${notesCount} notes` : notesCount})
          </Typography>
          <Box sx={{display:'flex', alignItems:'center', gap:1}}>
            {noteListViewMode === 'contextual' && aiContextHistory.length > 0 && (
                <Button 
                    size="small" 
                    variant="outlined"
                    startIcon={<DeleteSweepIcon />}
                    onClick={handleClearHistory}
                >
                    Clear History
                </Button>
            )}
            <FormGroup>
              <FormControlLabel
                control={<Switch checked={noteListViewMode === 'contextual'} onChange={handleViewModeChange} size="small"/>}
                label={<Typography variant="caption">AI Context</Typography>}
                sx={{mr:0}}
              />
            </FormGroup>
          </Box>
        </Box>
      </Paper>

      <Box sx={{flexGrow:1, overflowY: 'auto', pr:1}}>
        {noteListViewMode === 'all' && allNotes.length === 0 && !loading && (
          <Typography variant="subtitle1" align="center" sx={{ mt: 3 }}>
            No notes yet. Create your first note!
          </Typography>
        )}
        {noteListViewMode === 'contextual' && aiContextHistory.length === 0 && !loading && (
          <Typography variant="subtitle1" align="center" sx={{ mt: 3 }}>
            AI context history is empty. Interact with the AI to build it up!
          </Typography>
        )}
        {contentToDisplay}
      </Box>
    </Box>
  );
};

export default NoteList; 