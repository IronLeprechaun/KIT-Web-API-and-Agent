import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  TextField,
  Button,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  Chip,
  InputAdornment
} from '@mui/material';
import {
  Security as SecurityIcon,
  Visibility,
  VisibilityOff,
  Delete as DeleteIcon,
  Key as KeyIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon
} from '@mui/icons-material';
import { FrontendLogger } from '../services/frontendLogger';

interface ApiKey {
  key: string;
  name: string;
  masked: string;
}

interface SecretsStatus {
  secrets_available: boolean;
  config_exists: boolean;
  secrets_count: number;
  secrets_keys: string[];
}

const SettingsPage: React.FC = () => {
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [secretsStatus, setSecretsStatus] = useState<SecretsStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Add new API key dialog state
  const [addKeyDialog, setAddKeyDialog] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyValue, setNewKeyValue] = useState('');
  const [showNewKeyValue, setShowNewKeyValue] = useState(false);

  // Frontend Logs State
  const [showLogsDialog, setShowLogsDialog] = useState(false);
  const [frontendLogs, setFrontendLogs] = useState<any[]>([]);

  // Load secrets status on component mount
  useEffect(() => {
    loadSecretsStatus();
    loadApiKeys();
  }, []);

  const loadSecretsStatus = async () => {
    try {
      const response = await fetch('/api/secrets/status');
      const data = await response.json();
      setSecretsStatus(data);
    } catch (err) {
      setError('Failed to load secrets status');
    }
  };

  const loadApiKeys = async () => {
    try {
      const response = await fetch('/api/secrets/list', {
        method: 'GET',
      });

      const data = await response.json();

      if (data.success && data.data) {
        const keys = data.data.keys.map((key: string) => ({
          key,
          name: key,
          masked: `${'*'.repeat(Math.max(0, key.length - 4))}${key.slice(-4)}`
        }));
        setApiKeys(keys);
      }
    } catch (err) {
      setError('Failed to load API keys');
    }
  };

  const handleAddApiKey = async () => {
    if (!newKeyName || !newKeyValue) {
      setError('Please enter both key name and value');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/secrets/set', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          key: newKeyName,
          value: newKeyValue,
        }),
      });

      const data = await response.json();

      if (data.success) {
        setSuccess(`API key '${newKeyName}' added successfully`);
        setAddKeyDialog(false);
        setNewKeyName('');
        setNewKeyValue('');
        await loadApiKeys();
        await loadSecretsStatus();
      } else {
        setError(data.message || 'Failed to add API key');
      }
    } catch (err) {
      setError('Failed to add API key');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteApiKey = async (keyName: string) => {
    if (!window.confirm(`Are you sure you want to delete the API key '${keyName}'?`)) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/secrets/delete/${encodeURIComponent(keyName)}`, {
        method: 'DELETE',
        // headers and body are not needed for this DELETE request
      });

      const data = await response.json();

      if (data.success) {
        setSuccess(`API key '${keyName}' deleted successfully`);
        await loadApiKeys();
        await loadSecretsStatus();
      } else {
        setError(data.message || 'Failed to delete API key');
      }
    } catch (err) {
      setError('Failed to delete API key');
    } finally {
      setLoading(false);
    }
  };

  const openFrontendLogsDialog = () => {
    setFrontendLogs(FrontendLogger.getLogs());
    setShowLogsDialog(true);
  };

  const handleClearFrontendLogs = () => {
    FrontendLogger.clearLogs();
    setFrontendLogs([]); // Clear logs in dialog immediately
    setSuccess("Frontend logs cleared.");
  };

  const handleDownloadFrontendLogs = () => {
    FrontendLogger.downloadLogs();
  };

  const renderSecretsStatus = () => (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center' }}>
          <SecurityIcon sx={{ mr: 1 }} />
          Secrets Management Status
        </Typography>
        <Box sx={{ display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, gap: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
            {secretsStatus?.secrets_available ? (
              <CheckCircleIcon color="success" sx={{ mr: 1 }} />
            ) : (
              <WarningIcon color="warning" sx={{ mr: 1 }} />
            )}
            <Typography variant="body2">
              Secrets Manager: {secretsStatus?.secrets_available ? 'Available' : 'Not Available'}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
            {secretsStatus?.config_exists ? (
              <CheckCircleIcon color="success" sx={{ mr: 1 }} />
            ) : (
              <WarningIcon color="warning" sx={{ mr: 1 }} />
            )}
            <Typography variant="body2">
              Configuration: {secretsStatus?.config_exists ? 'Ready' : 'Not Set Up'}
            </Typography>
          </Box>
        </Box>
        <Chip 
          label={`${secretsStatus?.secrets_count || 0} secrets stored`}
          color="primary"
          size="small"
          sx={{ mt: 1 }}
        />
      </CardContent>
    </Card>
  );

  const renderApiKeysManagement = () => {
    const commonApiKeys = [
      { key: 'GEMINI_API_KEY', label: 'Google Gemini API Key', description: 'For Google\'s Gemini AI model' },
      { key: 'OPENAI_API_KEY', label: 'OpenAI API Key', description: 'For GPT-4, ChatGPT, and other OpenAI models' },
      { key: 'ANTHROPIC_API_KEY', label: 'Anthropic API Key', description: 'For Claude AI models' },
    ];

    const hasApiKey = (keyName: string) => {
      return apiKeys.some(k => k.key === keyName);
    };

    return (
      <Card>
        <CardContent>
          <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center' }}>
            <KeyIcon sx={{ mr: 1 }} />
            AI Service API Keys
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Click the "Add Key" button to securely store your API keys. Keys are stored locally without encryption.
          </Typography>
          
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {commonApiKeys.map((service) => (
              <Box key={service.key} sx={{
                p: 2,
                borderRadius: 2,
                border: hasApiKey(service.key) ? '1px solid' : '2px dashed',
                borderColor: hasApiKey(service.key) ? 'success.light' : 'primary.light',
                backgroundColor: hasApiKey(service.key) ? 'success.50' : 'primary.50'
              }}>
                <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 'medium' }}>
                  {service.label}
                  {!hasApiKey(service.key) && (
                    <Chip
                      label="Action Required"
                      color="warning"
                      size="small"
                      sx={{ ml: 1 }}
                    />
                  )}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  {service.description}
                </Typography>
                <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
                  <TextField
                    fullWidth
                    type="password"
                    placeholder={hasApiKey(service.key) 
                      ? 'API key securely stored' 
                      : 'Click "Add" button to set your API key →'
                    }
                    value={hasApiKey(service.key) ? '••••••••••••••••' : ''}
                    variant="outlined"
                    size="small"
                    disabled={true} // Always disabled - not directly editable
                    sx={{
                      '& .MuiInputBase-input': {
                        cursor: 'default',
                      },
                      '& .MuiOutlinedInput-root': {
                        backgroundColor: hasApiKey(service.key) ? 'success.50' : 'grey.50',
                      }
                    }}
                    InputProps={{
                      endAdornment: hasApiKey(service.key) ? (
                        <InputAdornment position="end">
                          <Chip 
                            label="Saved" 
                            color="success" 
                            size="small"
                            sx={{ mr: 1 }}
                          />
                        </InputAdornment>
                      ) : (
                        <InputAdornment position="end">
                          <Typography variant="caption" color="text.secondary" sx={{ mr: 1 }}>
                            Not set
                          </Typography>
                        </InputAdornment>
                      ),
                    }}
                  />

                  {hasApiKey(service.key) ? (
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      <Button
                        variant="outlined"
                        size="small"
                        onClick={() => {
                          setNewKeyName(service.key);
                          setNewKeyValue('');
                          setAddKeyDialog(true);
                        }}
                        sx={{ minWidth: 'auto' }}
                      >
                        Edit
                      </Button>
                      <IconButton
                        color="error"
                        size="small"
                        onClick={() => handleDeleteApiKey(service.key)}
                      >
                        <DeleteIcon />
                      </IconButton>
                    </Box>
                  ) : (
                    <Button
                      variant="contained"
                      color="primary"
                      size="medium"
                      onClick={() => {
                        setNewKeyName(service.key);
                        setNewKeyValue('');
                        setAddKeyDialog(true);
                      }}
                      sx={{
                        minWidth: 100,
                        fontWeight: 'bold',
                        boxShadow: 2,
                        '&:hover': {
                          boxShadow: 4,
                        }
                      }}
                    >
                      + Add Key
                    </Button>
                  )}
                </Box>
              </Box>
            ))}
          </Box>
        </CardContent>
      </Card>
    );
  };

  const renderFrontendLogsManagement = () => (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Frontend Log Management
        </Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button variant="outlined" onClick={openFrontendLogsDialog}>
            View Frontend Logs
          </Button>
          <Button variant="outlined" color="warning" onClick={handleClearFrontendLogs}>
            Clear Frontend Logs
          </Button>
          <Button variant="contained" onClick={handleDownloadFrontendLogs}>
            Download Frontend Logs
          </Button>
        </Box>
      </CardContent>
    </Card>
  );

  const renderFrontendLogsDialog = () => (
    <Dialog open={showLogsDialog} onClose={() => setShowLogsDialog(false)} maxWidth="lg" fullWidth>
      <DialogTitle>Frontend Application Logs</DialogTitle>
      <DialogContent>
        {frontendLogs.length === 0 ? (
          <Typography>No logs available.</Typography>
        ) : (
          <Box 
            component="pre" 
            sx={{ 
              maxHeight: '60vh', 
              overflow: 'auto', 
              p: 1, 
              bgcolor: 'grey.100', 
              borderRadius: 1,
              fontSize: '0.8rem',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all'
            }}
          >
            {frontendLogs.map((log, index) => (
              <div key={index}>
                {`${log.timestamp} [${log.level}] ${log.message}`}
                {log.details && <div style={{ marginLeft: '10px', whiteSpace: 'pre-wrap' }}>{typeof log.details === 'string' ? log.details : JSON.stringify(log.details, null, 2)}</div>}
              </div>
            )).join('\n')}
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setShowLogsDialog(false)}>Close</Button>
        <Button onClick={handleDownloadFrontendLogs} variant="contained">Download Logs</Button>
        <Button onClick={handleClearFrontendLogs} color="warning">Clear Logs in View</Button>
      </DialogActions>
    </Dialog>
  );

  const renderAddKeyDialog = () => {
    // Fix: Only disable the key name field when editing an existing predefined key
    const isEditingPredefinedKey = Boolean(newKeyName && ['GEMINI_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY'].includes(newKeyName));
    
    return (
      <Dialog open={addKeyDialog} onClose={() => setAddKeyDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{isEditingPredefinedKey ? `Edit ${newKeyName}` : 'Add New API Key'}</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Key Name (e.g., GEMINI_API_KEY)"
            fullWidth
            variant="outlined"
            value={newKeyName}
            onChange={(e) => setNewKeyName(e.target.value)}
            disabled={isEditingPredefinedKey}
            sx={{ mb: 2 }}
          />
          <TextField
            margin="dense"
            label="API Key Value"
            type={showNewKeyValue ? 'text' : 'password'}
            fullWidth
            variant="outlined"
            value={newKeyValue}
            onChange={(e) => setNewKeyValue(e.target.value)}
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    onClick={() => setShowNewKeyValue(!showNewKeyValue)}
                    edge="end"
                  >
                    {showNewKeyValue ? <VisibilityOff /> : <Visibility />}
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddKeyDialog(false)}>Cancel</Button>
          <Button
            onClick={handleAddApiKey}
            variant="contained"
            disabled={loading || !newKeyName || !newKeyValue}
          >
            {loading ? 'Adding...' : 'Add Key'}
          </Button>
        </DialogActions>
      </Dialog>
    );
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" sx={{ mb: 3, display: 'flex', alignItems: 'center' }}>
        <SecurityIcon sx={{ mr: 2, fontSize: '2rem' }} />
        Secure Settings
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ mb: 3 }} onClose={() => setSuccess(null)}>
          {success}
        </Alert>
      )}

      {renderSecretsStatus()}
      {renderApiKeysManagement()}
      {renderFrontendLogsManagement()}
      {renderAddKeyDialog()}
      {renderFrontendLogsDialog()}
    </Box>
  );
};

export default SettingsPage; 