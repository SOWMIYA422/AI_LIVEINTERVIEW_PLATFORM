// frontend/src/StartScreen.jsx
import React, { useState } from 'react';
import './Interview.css';

const StartScreen = ({ onStartInterview }) => {
  const [jobRole, setJobRole] = useState('data_scientist');
  const [candidateName, setCandidateName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [consentGiven, setConsentGiven] = useState(false);

  const jobRoles = [
    { value: 'data_scientist', label: 'Data Scientist' },
    { value: 'software_engineer', label: 'Software Engineer' },
    { value: 'product_manager', label: 'Product Manager' },
    { value: 'ml_engineer', label: 'ML Engineer' },
    { value: 'devops_engineer', label: 'DevOps Engineer' }
  ];

  const handleStart = async () => {
    if (!candidateName.trim()) {
      setError('Please enter your name');
      return;
    }

    if (!consentGiven) {
      setError('You must consent to audio and video recording');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await fetch('http://localhost:8000/api/interview/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          job_role: jobRole,
          candidate_name: candidateName
        })
      });

      if (!response.ok) {
        throw new Error('Failed to start interview');
      }

      const data = await response.json();
      onStartInterview(data);

    } catch (err) {
      setError(err.message || 'Failed to start interview');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="start-screen">
      <div className="start-container">
        <h1 className="main-title">🎙️ AI Interview Platform</h1>
        <p className="subtitle">Professional AI-powered interviews with real-time proctoring</p>

        <div className="start-card">
          <h2>Start New Interview</h2>

          {/* Consent Disclaimer - NEW SECTION */}
          <div className="consent-disclaimer">
            <div className="disclaimer-header">
              <span className="warning-icon">⚠️</span>
              <h3>Recording Consent</h3>
            </div>
            <div className="disclaimer-content">
              <p>
                <strong>Audio and video will be recorded during this interview.</strong>
                <br />
                By proceeding, you consent to the recording of:
              </p>
              <ul>
                <li>✅ Your voice and responses</li>
                <li>✅ Your webcam video feed</li>
                <li>✅ Screen activity monitoring</li>
                <li>✅ Proctoring data collection</li>
              </ul>
              <p className="consent-note">
                This recording is used for interview evaluation and proctoring purposes only.
              </p>
            </div>
            
            <div className="consent-checkbox">
              <input
                type="checkbox"
                id="recording-consent"
                checked={consentGiven}
                onChange={(e) => setConsentGiven(e.target.checked)}
              />
              <label htmlFor="recording-consent">
                I understand that <strong>audio and video will be recorded</strong> and I consent to this recording.
              </label>
            </div>
          </div>

          <div className="form-group">
            <label>Select Job Role</label>
            <select 
              value={jobRole} 
              onChange={(e) => setJobRole(e.target.value)}
              className="form-select"
            >
              {jobRoles.map(role => (
                <option key={role.value} value={role.value}>
                  {role.label}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Your Name</label>
            <input
              type="text"
              value={candidateName}
              onChange={(e) => setCandidateName(e.target.value)}
              placeholder="Enter your full name"
              className="form-input"
            />
          </div>

          {error && <div className="error-message">{error}</div>}

          <div className="requirements">
            <h4>📋 Requirements:</h4>
            <ul>
              <li>✅ Stable internet connection</li>
              <li>✅ Webcam and microphone</li>
              <li>✅ Chrome/Firefox browser</li>
              <li>✅ Quiet environment</li>
              <li>✅ 60+ minutes available</li>
            </ul>
          </div>

          <div className="proctoring-info">
            <h4>🔒 Proctoring Features:</h4>
            <ul>
              <li>🎥 Real-time face detection</li>
              <li>🔍 Tab switch monitoring</li>
              <li>🎤 Audio recording & analysis</li>
              <li>📊 Adaptive difficulty levels</li>
              <li>📈 Performance analytics</li>
            </ul>
          </div>

          <button 
            onClick={handleStart}
            disabled={loading || !consentGiven}
            className="start-button"
          >
            {loading ? 'Starting...' : '🚀 Start Interview'}
          </button>
          {!consentGiven && (
            <div className="consent-warning">
              ⚠️ You must consent to audio/video recording before starting
            </div>
          )}

          <div className="instructions">
            <p><strong>💡 Tip:</strong> Speak clearly and look at the camera during the interview.</p>
            <p><strong>⚠️ Warning:</strong> Tab switching will be recorded and may affect your score.</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StartScreen;