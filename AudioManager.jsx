// frontend/src/AudioManager.jsx
import React, { useState, useEffect, useRef } from 'react';

const AudioManager = ({ sessionId, onTranscriptionUpdate }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [liveTranscription, setLiveTranscription] = useState('');
  const [audioPermission, setAudioPermission] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  
  const mediaRecorderRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const audioChunksRef = useRef([]);
  const wsRef = useRef(null);

  // Initialize audio
  const initializeAudio = async () => {
    try {
      // Request microphone permission
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000
        }
      });
      
      setAudioPermission(true);
      
      // Setup WebAudio for visualization
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
      analyserRef.current = audioContextRef.current.createAnalyser();
      const source = audioContextRef.current.createMediaStreamSource(stream);
      source.connect(analyserRef.current);
      
      // Setup MediaRecorder
      mediaRecorderRef.current = new MediaRecorder(stream, {
        mimeType: 'audio/webm; codecs=opus'
      });
      
      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
          sendAudioChunk(event.data);
        }
      };
      
      // Start recording
      mediaRecorderRef.current.start(1000); // Collect every second
      setIsRecording(true);
      
      // Start audio level monitoring
      monitorAudioLevel();
      
      // Connect to WebSocket
      connectAudioWebSocket();
      
    } catch (error) {
      console.error('Audio initialization error:', error);
      alert('Please allow microphone access for voice interview');
    }
  };

  // Monitor audio level for visualization
  const monitorAudioLevel = () => {
    const checkLevel = () => {
      if (analyserRef.current) {
        const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
        analyserRef.current.getByteFrequencyData(dataArray);
        
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i];
        }
        const average = sum / dataArray.length;
        setAudioLevel(average);
      }
      
      if (isRecording) {
        requestAnimationFrame(checkLevel);
      }
    };
    
    checkLevel();
  };

  // Connect to audio WebSocket
  const connectAudioWebSocket = () => {
    const ws = new WebSocket(`ws://localhost:8000/ws/${sessionId}/audio`);
    
    ws.onopen = () => {
      console.log('Audio WebSocket connected');
      wsRef.current = ws;
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'transcription_update') {
        setLiveTranscription(data.text);
        if (onTranscriptionUpdate) {
          onTranscriptionUpdate(data.text);
        }
      }
    };
    
    ws.onclose = () => {
      console.log('Audio WebSocket disconnected');
    };
  };

  // Send audio chunk to backend
  const sendAudioChunk = async (audioBlob) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const arrayBuffer = await audioBlob.arrayBuffer();
      wsRef.current.send(arrayBuffer);
    }
  };

  // Play AI voice
  const playTextToSpeech = async (text) => {
    try {
      const response = await fetch('http://localhost:8000/api/text-to-speech', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text: text })
      });
      
      if (!response.ok) throw new Error('TTS failed');
      
      const audioBlob = await response.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      
      // Play with user interaction
      audio.play().catch(e => {
        console.log('Auto-play blocked, adding play button');
        // Create play button if autoplay blocked
        const playBtn = document.createElement('button');
        playBtn.innerHTML = '🔊 Play Question';
        playBtn.style.cssText = `
          position: fixed;
          top: 20px;
          right: 20px;
          padding: 10px 20px;
          background: #4CAF50;
          color: white;
          border: none;
          border-radius: 5px;
          cursor: pointer;
          z-index: 1000;
        `;
        playBtn.onclick = () => {
          audio.play();
          playBtn.remove();
        };
        document.body.appendChild(playBtn);
      });
      
    } catch (error) {
      console.error('TTS playback error:', error);
    }
  };

  // Stop recording
  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
      setIsRecording(false);
    }
  };

  // Cleanup
  useEffect(() => {
    return () => {
      stopRecording();
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  return {
    initializeAudio,
    stopRecording,
    playTextToSpeech,
    liveTranscription,
    audioPermission,
    audioLevel,
    isRecording
  };
};

export default AudioManager;