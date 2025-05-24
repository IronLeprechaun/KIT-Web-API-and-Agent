import React, { useState } from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Box,
  Paper,
  BottomNavigation,
  BottomNavigationAction
} from '@mui/material';
import ChatIcon from '@mui/icons-material/Chat';
import DashboardCustomizeIcon from '@mui/icons-material/DashboardCustomize';
import SettingsIcon from '@mui/icons-material/Settings';
import NoteList from './components/NoteList';
import ChatInterface from './components/ChatInterface';
import QuickActionsPage from './pages/QuickActionsPage';
import SettingsPage from './pages/SettingsPage';

const App: React.FC = () => {
  const [activeView, setActiveView] = useState<'chat' | 'quickActions' | 'settings'>('chat');

  return (
    <Box sx={{ 
      display: 'flex', 
      flexDirection: 'column', 
      height: '100vh', 
      width: '100%', 
      boxSizing: 'border-box',
      margin: 0,
      padding: 0 
    }}>
      <AppBar position="static" sx={{ flexShrink: 0 }}>
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            KIT Agent - Web Interface
          </Typography>
        </Toolbar>
      </AppBar>

      <Box 
        sx={{
          flexGrow: 1, 
          mt: 2, 
          ml: 0, 
          mr: 0, 
          display: 'flex', 
          flexDirection: 'column',
          overflow: 'hidden',
          minHeight: 0,
          width: 'auto',
          paddingBottom: '64px'
        }}
      >
        {activeView === 'settings' ? (
          // Full width layout for settings
          <Box sx={{ flexGrow: 1, paddingLeft: 2, paddingRight: 2 }}>
            <Box sx={{ display: 'flex', flexDirection: 'column', border: '1px solid #e0e0e0', borderRadius: 1, overflow: 'hidden', height: '100%' }}>
              <Box sx={{ flexGrow: 1, overflowY: 'auto', minHeight: 0 }}>
                <SettingsPage />
              </Box>
            </Box>
          </Box>
        ) : (
          // Two-column layout for chat and quick actions
          <Box sx={{ display: 'flex', flexGrow: 1, gap: 2, minHeight: 0, paddingLeft: 2, paddingRight: 2 }}>
            <Box sx={{ flexGrow: 7, display: 'flex', flexDirection: 'column', border: '1px solid #e0e0e0', borderRadius: 1, overflow: 'hidden' }}>
              <Box sx={{flexGrow:1, overflowY: 'auto', p:1, minHeight: 0 }}>
                {activeView === 'chat' && <ChatInterface />}
                {activeView === 'quickActions' && <QuickActionsPage />}
              </Box>
            </Box>

            <Box sx={{ flexGrow: 5, display: 'flex', flexDirection: 'column', border: '1px solid #e0e0e0', borderRadius: 1, overflow: 'hidden' }}>
              <Box sx={{flexGrow:1, overflowY: 'auto', p:1, minHeight: 0 }}>
                <NoteList />
              </Box>
            </Box>
          </Box>
        )}
      </Box>

      <Paper sx={{ position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 1100 }} elevation={3}>
        <BottomNavigation
          showLabels
          value={activeView}
          onChange={(event, newValue) => {
            setActiveView(newValue);
          }}
        >
          <BottomNavigationAction label="Chat" value="chat" icon={<ChatIcon />} />
          <BottomNavigationAction label="Quick Actions" value="quickActions" icon={<DashboardCustomizeIcon />} />
          <BottomNavigationAction label="Settings" value="settings" icon={<SettingsIcon />} />
        </BottomNavigation>
      </Paper>
    </Box>
  );
};

export default App;
