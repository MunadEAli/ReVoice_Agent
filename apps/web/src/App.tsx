import { useState } from "react";
import SessionScreen from "./components/SessionScreen";
import CorrectionScreen from "./components/CorrectionScreen";
import "./App.css";

type Screen = "session" | "correction";

export default function App() {
  const [screen, setScreen] = useState<Screen>("session");

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="header-brand">
          <span className="header-logo">ReVoice</span>
          <span className="header-tagline">Memory Agent — Margaret</span>
        </div>
        <nav className="header-nav">
          <button
            className={screen === "session" ? "nav-btn active" : "nav-btn"}
            onClick={() => setScreen("session")}
          >
            Session
          </button>
          <button
            className={screen === "correction" ? "nav-btn active" : "nav-btn"}
            onClick={() => setScreen("correction")}
          >
            Correct a Concept
          </button>
        </nav>
      </header>

      <main className="app-main">
        {screen === "session" && <SessionScreen ownerId="margaret" />}
        {screen === "correction" && (
          <CorrectionScreen ownerId="margaret" onDone={() => setScreen("session")} />
        )}
      </main>
    </div>
  );
}
