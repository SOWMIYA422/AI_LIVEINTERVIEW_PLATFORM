import React, { useState, useEffect, useRef } from 'react';

const SimpleAudioRecorder = ({ onAudioData, onStatus }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [permission, setPermission] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const streamRef = useRef(null);

  // Request microphone permission
  const requestMicrophone = async () => {
    try {
      console.log("🎤 Requesting microphone...");
      
      // SIMPLEST POSSIBLE - Let browser handle everything
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: true 
      });
      
      console.log("✅ Microphone granted:", stream.getAudioTracks());
      
      streamRef.current = stream;
      setPermission(true);
      onStatus("Microphone ready");
      
      // Test if audio is actually being captured
      testAudioCapture(stream);
      
      return stream;
      
    } catch (error) {
      console.error("❌ Microphone error:", error);
      onStatus(`Microphone error: ${error.message}`);
      return null;
    }
  };

  // Test if audio is actually being captured
  const testAudioCapture = (stream) => {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioContext.createMediaStreamSource(stream);
    const analyser = audioContext.createAnalyser();
    
    source.connect(analyser);
    analyser.fftSize = 256;
    
    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    
    const checkLevel = () => {
      analyser.getByteFrequencyData(dataArray);
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i];
      }
      const average = sum / dataArray.length;
      setAudioLevel(average);
      
      if (average > 0) {
        console.log(`🔊 Audio level: ${average}`);
      }
      
      if (stream.active) {
        requestAnimationFrame(checkLevel);
      }
    };
    
    checkLevel();
  };

  // Start recording
  const startRecording = async () => {
    if (!streamRef.current) {
      const stream = await requestMicrophone();
      if (!stream) return;
    }
    
    console.log("🎤 Starting recording...");
    
    // Reset chunks
    audioChunksRef.current = [];
    
    // Create MediaRecorder - NO parameters, let browser decide
    mediaRecorderRef.current = new MediaRecorder(streamRef.current);
    
    mediaRecorderRef.current.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunksRef.current.push(event.data);
        console.log(`📦 Audio chunk: ${event.data.size} bytes, type: ${event.data.type}`);
      }
    };
    
    mediaRecorderRef.current.onstop = () => {
      console.log("⏹️ Recording stopped");
      processRecording();
    };
    
    mediaRecorderRef.current.start(1000); // Collect every second
    setIsRecording(true);
    onStatus("Recording... Speak now!");
    
    console.log("✅ Recording started");
  };

  // Stop recording
  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  // Process recorded audio
  const processRecording = () => {
    if (audioChunksRef.current.length === 0) {
      console.log("❌ No audio chunks recorded");
      onStatus("No audio was recorded");
      return;
    }
    
    const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
    console.log(`🎵 Total audio: ${audioBlob.size} bytes, type: ${audioBlob.type}`);
    
    // Convert to base64
    const reader = new FileReader();
    reader.onloadend = () => {
      const base64Audio = reader.result.split(',')[1];
      console.log(`🔢 Base64 length: ${base64Audio ? base64Audio.length : 0}`);
      
      if (onAudioData) {
        onAudioData(base64Audio, audioBlob);
      }
    };
    reader.readAsDataURL(audioBlob);
  };

  // Cleanup
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
    };
  }, []);

  return {
    startRecording,
    stopRecording,
    isRecording,
    permission,
    audioLevel,
    requestMicrophone
  };
};

export default SimpleAudioRecorder;