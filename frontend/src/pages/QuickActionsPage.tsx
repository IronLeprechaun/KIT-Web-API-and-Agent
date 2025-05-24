import React from 'react';
import { Box, Typography, Paper } from '@mui/material';

const QuickActionsPage: React.FC = () => {
  return (
    <Paper elevation={3} sx={{ p: 3, m: 2, height: '100%' }}>
      <Typography variant="h4" gutterBottom>
        Quick Actions
      </Typography>
      <Typography variant="body1">
        This page will provide quick access to common actions and information.
      </Typography>
      {/* Placeholder for future quick action buttons or content */}
      <Box mt={3}>
        <Typography variant="h6">Coming Soon:</Typography>
        <ul>
          <li>Create New Note Button</li>
          <li>Global Search Bar</li>
          <li>Settings Shortcuts</li>
        </ul>
      </Box>
    </Paper>
  );
};

export default QuickActionsPage; 