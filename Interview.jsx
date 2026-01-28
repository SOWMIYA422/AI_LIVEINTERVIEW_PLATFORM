// frontend/src/Interview.jsx - WITH FACE PROCTORING
import React, { useState, useEffect, useRef } from 'react';
import './Interview.css';

const Interview = ({ sessionData, onEndInterview }) => {
  // State
  const [currentQuestion, setCurrentQuestion] = useState(sessionData?.question || '');
  const [conversation, setConversation] = useState([]);
  const [loading, setLoading] = useState(false);
  const [faceDetected, setFaceDetected] = useState(true);
  const [tabSwitchCount, setTabSwitchCount] = useState(0);
  const [warning, setWarning] = useState('');
  const [currentLevel, setCurrentLevel] = useState('easy');
  const [questionNumber, setQuestionNumber] = useState(1);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [lastTranscription, setLastTranscription] = useState('');
  const [lastAnalysis, setLastAnalysis] = useState('');
  const [interviewCompleted, setInterviewCompleted] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [cameraReady, setCameraReady] = useState(false);
  
  // Proctoring state
  const [faceAlerts, setFaceAlerts] = useState([]);
  const [proctoringStats, setProctoringStats] = useState({
    multiple_faces: 0,
    face_coverings: 0,
    eye_coverings: 0,
    no_face_count: 0,
    total_alerts: 0,
    calibrating: true,
  });
  const [faceCalibration, setFaceCalibration] = useState({
    complete: false,
    frames: 0,
    face_cover_counter: 0,
    eye_cover_counter: 0,
  });
  
  // Refs
  const videoWsRef = useRef(null);
  const monitorWsRef = useRef(null);
  const videoRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const recordedChunksRef = useRef([]);
  const recordingTimerRef = useRef(null);
  const isProcessingRef = useRef(false);
  const faceIntervalRef = useRef(null);
  const mediaStreamRef = useRef(null);

  // ==================== INITIALIZE CAMERA ====================
  
  useEffect(() => {
    if (!sessionData?.session_id || interviewCompleted) return;
    
    console.log("🚀 Initializing camera with face proctoring...");
    
    // Initialize camera with getUserMedia directly
    const initCamera = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            width: 640,
            height: 480,
            facingMode: "user"
          },
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            sampleRate: 16000,
            channelCount: 1
          }
        });
        
        mediaStreamRef.current = stream;
        
        // Connect stream to video element
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play();
          setCameraReady(true);
          console.log("✅ Camera with audio ready");
        }
        
      } catch (error) {
        console.error("❌ Camera initialization failed:", error);
        alert(`Camera/microphone error: ${error.message}. Please allow permissions.`);
      }
    };
    
    initCamera();
    
    // Initialize Face Proctoring WebSocket
    const videoWs = new WebSocket(`ws://localhost:8000/ws/video/${sessionData.session_id}`);
    videoWs.onopen = () => {
      console.log('✅ Face proctoring connected');
      videoWsRef.current = videoWs;
      
      // Send face detection frames every 1 second
      faceIntervalRef.current = setInterval(() => {
        if (videoRef.current && videoWs.readyState === WebSocket.OPEN) {
          captureFrameForFaceProctoring();
        }
      }, 1000);
    };
    
    videoWs.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'proctoring_result') {
          setFaceDetected(data.detected);
          setFaceAlerts(data.alerts || []);
          
          if (data.proctoring_data) {
            setFaceCalibration({
              complete: data.proctoring_data.calibration_complete || false,
              frames: data.proctoring_data.calibration_frames || 0,
              face_cover_counter: data.proctoring_data.face_cover_counter || 0,
              eye_cover_counter: data.proctoring_data.eye_cover_counter || 0,
            });
          }
          
          if (data.session_stats) {
            setProctoringStats(prev => ({
              ...prev,
              ...data.session_stats,
              calibrating: !data.proctoring_data?.calibration_complete || false,
            }));
          }
          
          // Show alerts as warnings
          if (data.alerts && data.alerts.length > 0) {
            const alertMessages = data.alerts.join(', ');
            setWarning(`⚠️ Proctoring Alert: ${alertMessages}`);
            setTimeout(() => setWarning(''), 3000);
          }
        }
      } catch (error) {
        console.error('Face proctoring error:', error);
      }
    };
    
    // Monitor WebSocket for tab switching
    const monitorWs = new WebSocket(`ws://localhost:8000/ws/monitor/${sessionData.session_id}`);
    monitorWs.onopen = () => {
      console.log('✅ Tab monitoring connected');
      monitorWsRef.current = monitorWs;
    };
    
    monitorWs.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'tab_warning') {
          setTabSwitchCount(data.count);
          setWarning(data.message);
          setTimeout(() => setWarning(''), 3000);
        }
      } catch (error) {
        console.error('Monitor error:', error);
      }
    };
    
    // Tab switch detection
    const handleTabSwitch = () => {
      if (document.hidden && monitorWsRef.current?.readyState === WebSocket.OPEN) {
        monitorWsRef.current.send(JSON.stringify({
          type: 'tab_switch',
          timestamp: Date.now()
        }));
      }
    };
    
    document.addEventListener('visibilitychange', handleTabSwitch);
    
    // Speak first question
    speakQuestion(currentQuestion);
    
    // Cleanup
    return () => {
      clearInterval(faceIntervalRef.current);
      clearInterval(recordingTimerRef.current);
      stopRecording();
      if (videoWsRef.current) videoWsRef.current.close();
      if (monitorWsRef.current) monitorWsRef.current.close();
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach(track => track.stop());
      }
      document.removeEventListener('visibilitychange', handleTabSwitch);
    };
    
  }, [sessionData, interviewCompleted]);

  // Capture frame from video element for face proctoring
  const captureFrameForFaceProctoring = () => {
    if (!videoRef.current) return;
    
    const canvas = document.createElement('canvas');
    canvas.width = 320;
    canvas.height = 240;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
    
    const imageData = canvas.toDataURL('image/jpeg', 0.8);
    const base64Data = imageData.split(',')[1];
    
    if (videoWsRef.current?.readyState === WebSocket.OPEN) {
      videoWsRef.current.send(JSON.stringify({
        type: "video_frame",
        data: base64Data,
        timestamp: Date.now(),
        width: canvas.width,
        height: canvas.height
      }));
    }
  };

  // ==================== RECORDING FUNCTIONS ====================
  
  const startRecording = async () => {
    if (!mediaStreamRef.current) {
      console.error("No media stream available");
      return;
    }
    
    try {
      console.log("🎥 Starting recording...");
      
      // Reset chunks
      recordedChunksRef.current = [];
      
      // Create MediaRecorder
      const options = {
        mimeType: 'video/webm;codecs=vp9',
        videoBitsPerSecond: 2500000,
        audioBitsPerSecond: 128000
      };
      
      // Try different mimeTypes
      const mimeTypes = [
        'video/webm;codecs=vp9',
        'video/webm;codecs=vp8',
        'video/webm'
      ];
      
      let mediaRecorder;
      for (const mimeType of mimeTypes) {
        if (MediaRecorder.isTypeSupported(mimeType)) {
          try {
            mediaRecorder = new MediaRecorder(mediaStreamRef.current, { mimeType });
            console.log(`Using mimeType: ${mimeType}`);
            break;
          } catch (e) {
            console.log(`Failed with ${mimeType}:`, e);
          }
        }
      }
      
      if (!mediaRecorder) {
        mediaRecorder = new MediaRecorder(mediaStreamRef.current);
        console.log('Using default MediaRecorder');
      }
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          recordedChunksRef.current.push(event.data);
          console.log(`📹 Chunk recorded: ${event.data.size} bytes`);
        }
      };
      
      mediaRecorder.onstop = () => {
        console.log("⏹️ Recording stopped");
        setIsRecording(false);
      };
      
      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start(1000);
      setIsRecording(true);
      setRecordingTime(0);
      
      // Start timer
      recordingTimerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
      
      console.log("✅ Recording started");
      
    } catch (error) {
      console.error("❌ Failed to start recording:", error);
    }
  };
  
  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
    }
    
    if (recordingTimerRef.current) {
      clearInterval(recordingTimerRef.current);
      recordingTimerRef.current = null;
    }
    
    console.log("⏹️ Recording stopped");
  };
  
  const getRecordedVideo = () => {
    if (recordedChunksRef.current.length > 0) {
      const blob = new Blob(recordedChunksRef.current, { type: 'video/webm' });
      console.log(`📹 Total video recorded: ${blob.size} bytes from ${recordedChunksRef.current.length} chunks`);
      return blob;
    }
    return null;
  };

  // ==================== INTERVIEW FUNCTIONS ====================
  
  const speakQuestion = (text) => {
    if ('speechSynthesis' in window) {
      setIsSpeaking(true);
      window.speechSynthesis.cancel();
      
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      utterance.volume = 1.0;
      
      utterance.onend = () => {
        setIsSpeaking(false);
        console.log('✅ AI finished speaking. Starting recording...');
        startRecording();
      };
      
      utterance.onerror = () => {
        setIsSpeaking(false);
        console.log('❌ Speech error. Starting recording...');
        startRecording();
      };
      
      window.speechSynthesis.speak(utterance);
    } else {
      setTimeout(() => {
        startRecording();
      }, 1000);
    }
  };
  
  const handleNextQuestion = async () => {
    if (loading || isProcessingRef.current) return;
    
    setLoading(true);
    isProcessingRef.current = true;
    
    try {
      console.log(`🔄 Processing answer for question ${questionNumber}...`);
      
      // Stop recording
      stopRecording();
      
      // Wait longer for recording to fully stop (1.5 seconds)
      console.log("⏳ Waiting for recording to finalize...");
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      // Get recorded video
      const videoBlob = getRecordedVideo();
      
      if (!videoBlob || videoBlob.size === 0) {
        console.log("⚠️ No video recorded or video is empty");
      }
      
      // Prepare request
      const requestBody = {
        timestamp: Date.now(),
        question: currentQuestion,
        proctoring_stats: proctoringStats,
      };
      
      if (videoBlob && videoBlob.size > 1000) {
        console.log(`📹 Converting video: ${videoBlob.size} bytes to base64...`);
        
        const videoBase64 = await new Promise((resolve) => {
          const reader = new FileReader();
          reader.onloadend = () => {
            const base64 = reader.result.split(',')[1];
            console.log(`✅ Video converted: ${base64.length} chars`);
            resolve(base64);
          };
          reader.onerror = (error) => {
            console.error('❌ FileReader error:', error);
            resolve('');
          };
          reader.readAsDataURL(videoBlob);
        });
        
        if (videoBase64) {
          requestBody.video = videoBase64;
        }
      } else {
        console.log("⚠️ Video too small or not available");
      }
      
      // Send to backend
      console.log('📤 Sending request to backend...');
      const response = await fetch(
        `http://localhost:8000/api/interview/${sessionData.session_id}/next-question`,
        {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          },
          body: JSON.stringify(requestBody)
        }
      );
      
      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`);
      }
      
      const data = await response.json();
      console.log('📥 Backend response:', data);
      
      if (data.interview_completed) {
        handleInterviewCompletion(data);
      } else if (data.success) {
        handleInterviewResponse(data);
      } else {
        throw new Error(data.error || 'Unknown error');
      }
      
    } catch (error) {
      console.error('❌ Next question error:', error);
      setWarning('Error: ' + error.message);
      
      // Even on error, try to get next question
      try {
        const response = await fetch(
          `http://localhost:8000/api/interview/${sessionData.session_id}/next-question`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ timestamp: Date.now() })
          }
        );
        
        const data = await response.json();
        if (data.success) {
          handleInterviewResponse(data);
        }
      } catch (fallbackError) {
        console.error('Fallback also failed:', fallbackError);
      }
      
    } finally {
      setLoading(false);
      isProcessingRef.current = false;
      setRecordingTime(0);
      recordedChunksRef.current = [];
    }
  };
  
  const handleInterviewResponse = (data) => {
    // Update conversation
    const newConversation = [
      ...conversation,
      { 
        type: 'candidate', 
        text: data.transcription || 'Video answer submitted' 
      }
    ];
    
    if (data.analysis) {
      newConversation.push({ type: 'analysis', text: data.analysis });
      setLastAnalysis(data.analysis);
    }
    
    newConversation.push({ type: 'ai', text: data.next_question });
    
    setConversation(newConversation);
    
    // Update state
    setCurrentQuestion(data.next_question);
    setQuestionNumber(data.question_number || questionNumber + 1);
    setCurrentLevel(data.current_level || currentLevel);
    setLastTranscription(data.transcription || '');
    
    if (data.proctoring_stats) {
      setProctoringStats(prev => ({
        ...prev,
        ...data.proctoring_stats
      }));
    }
    
    console.log(`✅ Question ${questionNumber + 1} ready`);
    
    // Speak next question after delay
    setTimeout(() => {
      speakQuestion(data.next_question);
    }, 1000);
  };

  const handleInterviewCompletion = (data) => {
    setInterviewCompleted(true);
    setConversation(prev => [
      ...prev,
      { type: 'ai', text: `Interview completed! ${data.final_feedback}` }
    ]);
    
    speakQuestion(`Interview completed! ${data.final_feedback}`);
    
    // Call callback after delay
    setTimeout(() => {
      onEndInterview();
    }, 5000);
  };

  const handleEndInterview = async () => {
    if (window.confirm('Are you sure you want to end the interview?')) {
      try {
        stopRecording();
        
        const response = await fetch(
          `http://localhost:8000/api/interview/${sessionData.session_id}/end`,
          { method: 'POST' }
        );
        
        const data = await response.json();
        
        if (data.success) {
          handleInterviewCompletion(data);
        }
        
      } catch (error) {
        console.error('End error:', error);
        alert('Error ending interview');
      }
    }
  };

  const testProctoring = () => {
    console.log("🔍 Testing proctoring...");
    console.log("Face detected:", faceDetected);
    console.log("Face alerts:", faceAlerts);
    console.log("Proctoring stats:", proctoringStats);
    console.log("Face calibration:", faceCalibration);
    
    // Trigger a manual frame capture
    captureFrameForFaceProctoring();
  };

  // ==================== RENDER ====================
  
  return (
    <div className="interview-container">
      {/* Header */}
      <header className="interview-header">
        <div className="header-left">
          <h1>🎥 AI Interview with Face Proctoring</h1>
          <div className="session-info">
            <span><strong>Role:</strong> {sessionData?.job_role}</span>
            <span><strong>Candidate:</strong> {sessionData?.candidate_name}</span>
            <span><strong>Q:</strong> {questionNumber}/9</span>
            <span><strong>Level:</strong> <span className={`level-${currentLevel}`}>{currentLevel.toUpperCase()}</span></span>
          </div>
        </div>
        
        <div className="header-right">
          <div className="status-indicators">
            <div className={`status-indicator ${faceDetected ? 'active' : 'warning'}`}>
              {faceDetected ? '✅ Face Detected' : '❌ No Face'}
              {!faceCalibration.complete && (
                <span className="calibration-indicator">
                  Calibrating: {faceCalibration.frames}/30
                </span>
              )}
            </div>
            <div className="status-indicator">
              🔍 Tabs: {tabSwitchCount}
            </div>
            <div className={`status-indicator ${isRecording ? 'recording' : isSpeaking ? 'speaking' : 'ready'}`}>
              {isRecording ? `🎥 Recording (${recordingTime}s)` : 
               isSpeaking ? '🗣️ AI Speaking' : '✅ Ready'}
            </div>
            <button 
              onClick={testProctoring}
              className="test-button"
              style={{padding: '5px 10px', fontSize: '12px'}}
            >
              Test Proctoring
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="main-content">
        {/* Left Panel - Interview */}
        <div className="interview-panel">
          <div className="question-section">
            <div className="question-header">
              <h2>Question {questionNumber}</h2>
              <div className="level-badge">
                <span className={`level-${currentLevel}`}>
                  {currentLevel.toUpperCase()} LEVEL
                </span>
              </div>
            </div>
            
            <div className="question-display">
              <p>{currentQuestion}</p>
              <div className="question-status">
                {isSpeaking ? (
                  <span className="speaking-indicator">🗣️ AI is speaking... Recording will auto-start</span>
                ) : isRecording ? (
                  <span className="recording-indicator">
                    🎥 Recording your answer... Speak naturally ({recordingTime}s)
                  </span>
                ) : loading ? (
                  <span className="loading-indicator">🔄 Processing your answer...</span>
                ) : (
                  <span className="ready-indicator">
                    ✅ Speak your answer. Click "Next Question" when done.
                  </span>
                )}
              </div>
            </div>

            {/* ONE BUTTON - NEXT QUESTION */}
            <div className="next-button-section">
              <button
                onClick={handleNextQuestion}
                disabled={loading || isSpeaking}
                className="next-question-button"
              >
                {loading ? '🔄 Processing...' : '⏭️ Next Question'}
              </button>
              
              <div className="button-instruction">
                {isSpeaking ? 'Wait for AI to finish speaking' :
                 isRecording ? 'Speak your answer, then click above' :
                 'Answer recorded. Click to proceed'}
              </div>
              
              <div className="recording-info">
                <small>
                  {cameraReady ? '✅ Camera ready' : '❌ Camera not ready'}
                  {isRecording && ` | Recording: ${recordingTime}s`}
                </small>
              </div>
            </div>
            
            {warning && (
              <div className="warning-message">
                ⚠️ {warning}
              </div>
            )}
            
            {lastTranscription && (
              <div className="last-answer">
                <h4>Your Last Answer:</h4>
                <div className="transcription-box">{lastTranscription}</div>
              </div>
            )}
            
            {lastAnalysis && (
              <div className="last-analysis">
                <h4>Analysis:</h4>
                <div className="analysis-box">{lastAnalysis}</div>
              </div>
            )}
          </div>

          <div className="conversation-section">
            <h3>Conversation History</h3>
            <div className="conversation-list">
              {conversation.length === 0 ? (
                <div className="empty-conversation">
                  Your conversation will appear here...
                </div>
              ) : (
                conversation.map((item, index) => (
                  <div key={index} className={`conversation-item ${item.type}`}>
                    <div className="item-header">
                      <strong>
                        {item.type === 'ai' ? '🤖 AI Interviewer' : 
                         item.type === 'analysis' ? '📊 Analysis' : 
                         '👤 Candidate'}
                      </strong>
                    </div>
                    <div className="item-content">{item.text}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Panel - Proctoring */}
        <div className="proctoring-panel">
          <div className="video-monitoring">
            <h3>Live Camera with Face Proctoring</h3>
            <div className="video-container">
              <video
                ref={videoRef}
                autoPlay
                muted
                playsInline
                width="320"
                height="240"
                className="direct-video"
              />
              <div className="recording-status">
                <span className={`recording-dot ${isRecording ? 'active' : ''}`}></span>
                <span>
                  {isRecording ? 'Auto-recording video+audio...' : 
                   cameraReady ? '✅ Camera ready' : '❌ Camera loading...'}
                </span>
              </div>
            </div>
            
            {/* Proctoring Stats */}
            <div className="proctoring-stats">
              <div className="stat-item">
                <span className="stat-label">Face Status:</span>
                <span className={`stat-value ${faceDetected ? 'good' : 'bad'}`}>
                  {faceDetected ? '✅ Detected' : '❌ Not Detected'}
                </span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Calibration:</span>
                <span className={`stat-value ${faceCalibration.complete ? 'good' : 'warning'}`}>
                  {faceCalibration.complete ? '✅ Complete' : `${faceCalibration.frames}/30`}
                </span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Multiple People:</span>
                <span className={`stat-value ${proctoringStats.multiple_faces > 0 ? 'bad' : 'good'}`}>
                  {proctoringStats.multiple_faces} detected
                </span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Face Coverings:</span>
                <span className={`stat-value ${proctoringStats.face_coverings > 0 ? 'bad' : 'good'}`}>
                  {proctoringStats.face_coverings} incidents
                </span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Eye Coverings:</span>
                <span className={`stat-value ${proctoringStats.eye_coverings > 0 ? 'bad' : 'good'}`}>
                  {proctoringStats.eye_coverings} incidents
                </span>
              </div>
              <div className="stat-item">
                <span className="stat-label">No Face Count:</span>
                <span className={`stat-value ${proctoringStats.no_face_count > 0 ? 'bad' : 'good'}`}>
                  {proctoringStats.no_face_count} times
                </span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Total Alerts:</span>
                <span className={`stat-value ${proctoringStats.total_alerts > 0 ? 'bad' : 'good'}`}>
                  {proctoringStats.total_alerts}
                </span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Tab Switches:</span>
                <span className="stat-value warning">
                  🔍 {tabSwitchCount}
                </span>
              </div>
            </div>
            
            {/* Proctoring Alerts */}
            <div className="proctoring-alerts">
              <h4>Active Proctoring Alerts:</h4>
              {faceAlerts.length === 0 ? (
                <div className="no-alerts">✅ No violations detected</div>
              ) : (
                <div className="alerts-list">
                  {faceAlerts.map((alert, index) => (
                    <div key={index} className="alert-item">
                      ⚠️ {alert}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="interview-controls">
            <button
              onClick={handleEndInterview}
              className="end-interview-button"
              disabled={loading || isSpeaking || isRecording}
            >
              🏁 End Interview
            </button>
            
            <div className="instructions">
              <h4>Face Proctoring Features:</h4>
              <ul>
                <li><strong>Multiple Face Detection:</strong> Alerts when multiple people detected</li>
                <li><strong>Face Covering Detection:</strong> Detects when face is covered</li>
                <li><strong>Eye Covering Detection:</strong> Detects when eyes are covered</li>
                <li><strong>No Face Detection:</strong> Alerts when face disappears</li>
                <li><strong>30-frame Calibration:</strong> Adapts to your lighting</li>
                <li><strong>Real-time Alerts:</strong> Shows violations immediately</li>
                <li><strong>Tab Switching:</strong> Tracks when you switch tabs</li>
              </ul>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Interview;