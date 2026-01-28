// frontend/src/App.jsx
import React, { useState } from 'react';
import Interview from './Interview';
import StartScreen from './StartScreen';
import './App.css';

function App() {
  const [interviewStarted, setInterviewStarted] = useState(false);
  const [sessionData, setSessionData] = useState(null);

  const handleInterviewStart = (data) => {
    setSessionData(data);
    setInterviewStarted(true);
  };

  const handleInterviewEnd = () => {
    setInterviewStarted(false);
    setSessionData(null);
  };

  return (
    <div className="App">
      {!interviewStarted ? (
        <StartScreen onStartInterview={handleInterviewStart} />
      ) : (
        <Interview 
          sessionData={sessionData} 
          onEndInterview={handleInterviewEnd}
        />
      )}
    </div>
  );
}

export default App;