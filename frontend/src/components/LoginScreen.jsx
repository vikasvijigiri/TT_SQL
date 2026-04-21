import React from 'react';
import axios from 'axios';
import { GoogleLogin } from '@react-oauth/google';
import { ArrowRight, Database } from 'lucide-react';

/* eslint-disable react/prop-types */
import './LoginScreen.css';

const API_BASE_URL = 'http://localhost:8001';

const LoginScreen = ({ onLogin }) => {
  const handleGoogleSuccess = async (response) => {
    try {
      const res = await axios.post(`${API_BASE_URL}/api/auth/google`, {
        credential: response.credential
      });
      if (res.data.success) {
        onLogin(res.data.user);
      }
    } catch (err) {
      console.error("Google Auth failed", err);
      alert("Authentication failed. Please try again.");
    }
  };

  const [showGuestNameInput, setShowGuestNameInput] = React.useState(false);
  const [guestName, setGuestName] = React.useState('');
  const [googleLoadError, setGoogleLoadError] = React.useState(false);

  // Fallback for Google Load Issues
  const handleGoogleLoadError = () => {
    console.error("Google SSO failed to initialize");
    setGoogleLoadError(true);
  };

  const handleGuestLogin = () => {
    if (!showGuestNameInput) {
      setShowGuestNameInput(true);
      return;
    }

    if (!guestName.trim()) {
      alert("Please enter a name to continue.");
      return;
    }

    onLogin({ 
      name: guestName.trim(), 
      email: `${guestName.trim().toLowerCase().replace(/\s+/g, '_')}@ttsql.internal`, 
      picture: null 
    });
  };

  return (
    <div className="login-wrapper">
      
      {/* LEFT PANEL - Branded Graphic */}
      <div className="login-graphic">
        <div className="mesh-gradient"></div>
        <div className="login-graphic-content">
          <div className="login-logo">
            <Database size={24} color="#60a5fa" />
            <span>NextGen SQL</span>
          </div>
          
          <div className="login-tagline">
            <h1>Autonomous Intelligence. <br/> At Scale.</h1>
            <p>
              Connect, analyze, and orchestrate advanced database queries through natural language. 
            </p>
          </div>
          
          <div style={{ opacity: 0.6, fontSize: '12px' }}>
            © 2026 NextGen Accelerators
          </div>
        </div>
      </div>
      
      {/* RIGHT PANEL - Authentication */}
      <div className="login-panel">
        <div className="login-container compact">
          
          <div className="login-header">
            <h2>Welcome back</h2>
            <p>Select your access method below</p>
          </div>

          <div className="auth-methods-primary">
            <div className="google-login-button-container">
              {!googleLoadError ? (
                <GoogleLogin 
                  onSuccess={handleGoogleSuccess}
                  onError={() => {
                    console.log('Login Failed');
                    handleGoogleLoadError();
                  }}
                  theme="filled_blue"
                  size="large"
                  shape="pill"
                  width="320px"
                />
              ) : (
                <div className="auth-error-banner">
                  Google Sign-In is unavailable. Use Guest Access instead.
                </div>
              )}
            </div>

            <div className="divider">
              <span>or</span>
            </div>

            {showGuestNameInput ? (
              <div className="guest-name-input-container">
                <input 
                  type="text" 
                  placeholder="Enter your name..." 
                  value={guestName}
                  onChange={(e) => setGuestName(e.target.value)}
                  autoFocus
                  onKeyDown={(e) => e.key === 'Enter' && handleGuestLogin()}
                  className="guest-name-input"
                />
                <div className="guest-name-actions">
                  <button className="btn-guest-login primary" onClick={handleGuestLogin}>
                    <span>Continue</span>
                    <ArrowRight size={16} />
                  </button>
                  <button className="btn-guest-cancel" onClick={() => setShowGuestNameInput(false)}>
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button className="btn-guest-login" onClick={handleGuestLogin}>
                <div className="guest-icon-circle">
                  <ArrowRight size={18} />
                </div>
                <span>Continue as Guest</span>
              </button>
            )}
          </div>

          <div className="signup-prompt">
            Need an enterprise account? <span>Contact Sales</span>
          </div>

        </div>
      </div>
    </div>
  );
};

export default LoginScreen;
