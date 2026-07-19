import { useState } from "react";
import SessionScreen from "./components/SessionScreen";
import CorrectionScreen from "./components/CorrectionScreen";
import ReviewScreen from "./components/ReviewScreen";
import "./App.css";

type Screen = "session" | "correction" | "review";

const USERS = [
  { id: "margaret", display: "Margaret" },
  { id: "james", display: "James" },
];

export default function App() {
  const [screen, setScreen] = useState<Screen>("session");
  const [userId, setUserId] = useState<string>(
    () => localStorage.getItem("revoice_user") ?? "margaret"
  );

  function switchUser(id: string) {
    setUserId(id);
    localStorage.setItem("revoice_user", id);
    setScreen("session");
  }

  const userName = USERS.find((u) => u.id === userId)?.display ?? userId;

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="header-brand">
          <span className="header-logo">ReVoice</span>
          <span className="header-tagline">Memory Agent</span>
        </div>

        {/* User selector */}
        <div className="user-selector">
          {USERS.map((u) => (
            <button
              key={u.id}
              className={userId === u.id ? "user-btn active" : "user-btn"}
              onClick={() => switchUser(u.id)}
              title={`Switch to ${u.display}`}
            >
              {u.display}
            </button>
          ))}
        </div>

        <nav className="header-nav">
          <button
            className={screen === "session" ? "nav-btn active" : "nav-btn"}
            onClick={() => setScreen("session")}
          >
            Session
          </button>
          <button
            className={screen === "review" ? "nav-btn active" : "nav-btn"}
            onClick={() => setScreen("review")}
          >
            Progress
          </button>
          <button
            className={screen === "correction" ? "nav-btn active" : "nav-btn"}
            onClick={() => setScreen("correction")}
          >
            Correct
          </button>
        </nav>
      </header>

      <main className="app-main">
        {screen === "session" && (
          <SessionScreen ownerId={userId} userName={userName} />
        )}
        {screen === "review" && (
          <ReviewScreen ownerId={userId} />
        )}
        {screen === "correction" && (
          <CorrectionScreen ownerId={userId} onDone={() => setScreen("session")} />
        )}
      </main>
    </div>
  );
}
