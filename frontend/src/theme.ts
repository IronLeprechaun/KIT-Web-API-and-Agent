import { createTheme } from '@mui/material/styles';
import { red } from '@mui/material/colors';

// Create a theme instance.
const theme = createTheme({
  palette: {
    primary: {
      main: '#556cd6', // A shade of blue
    },
    secondary: {
      main: '#19857b', // A shade of green
    },
    error: {
      main: red.A400,
    },
    background: {
      default: '#f4f6f8', // A light grey background
      paper: '#ffffff',
    },
  },
  typography: {
    fontFamily: 'Roboto, Arial, sans-serif',
    h1: {
      fontSize: '2.5rem',
      fontWeight: 500,
    },
    h2: {
      fontSize: '2rem',
      fontWeight: 500,
    },
    // Define other typography variants as needed
  },
  components: {
    // Example: Default props for MuiButton
    MuiButton: {
      defaultProps: {
        disableElevation: true,
      },
      styleOverrides: {
        root: {
          textTransform: 'none', // Keep button text case as is
        },
      },
    },
    MuiAppBar: {
      defaultProps: {
        elevation: 1,
      }
    }
    // Add other component overrides or default props here
  },
});

export default theme; 