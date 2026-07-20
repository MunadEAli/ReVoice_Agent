import { useState } from "react";
import SessionScreen from "./components/SessionScreen";
import CorrectionScreen from "./components/CorrectionScreen";
import ReviewScreen from "./components/ReviewScreen";
import "./App.css";

type Screen = "session" | "correction" | "review";

const USERS = [
  {
    id: "margaret",
    display: "Margaret",
    role: "Practice profile",
    initials: "MG",
    summary: "Family, appointments, documents, cafe orders, and one caregiver-only medication memory.",
    stats: "7 concepts",
  },
  {
    id: "james",
    display: "James",
    role: "Practice profile",
    initials: "JM",
    summary: "Spouse, community center, and morning coffee memories with early progress history.",
    stats: "3 concepts",
  },
];

export default function App() {
  const storedUser = localStorage.getItem("revoice_user");
  const [screen, setScreen] = useState<Screen>("session");
  const [userId, setUserId] = useState<string>(() => storedUser ?? "margaret");
  const [isLoggedIn, setIsLoggedIn] = useState(() => Boolean(storedUser));

  function selectUser(id: string) {
    setUserId(id);
    localStorage.setItem("revoice_user", id);
    setIsLoggedIn(true);
    setScreen("session");
  }

  function logout() {
    localStorage.removeItem("revoice_user");
    setIsLoggedIn(false);
    setScreen("session");
  }

  const activeUser = USERS.find((u) => u.id === userId) ?? USERS[0];
  const userName = activeUser.display;

  if (!isLoggedIn) {
    return (
      <div className="login-page">
        <main className="login-panel" aria-labelledby="login-title">
          <section className="login-copy">
            <div className="brand-mark">ReVoice</div>
            <p className="login-kicker">Memory Agent demo</p>
            <h1 id="login-title">Choose a reference person to begin.</h1>
            <p className="login-lede">
              The seeded demo users are Margaret and James. Pick either profile to keep
              practicing with its existing memories, cue ladder, and review history.
            </p>
            <div className="login-metrics" aria-label="Demo data summary">
              <div>
                <strong>2</strong>
                <span>reference people</span>
              </div>
              <div>
                <strong>10</strong>
                <span>seeded concepts</span>
              </div>
              <div>
                <strong>live</strong>
                <span>memory scoring</span>
              </div>
            </div>
          </section>

          <section className="login-card" aria-label="Reference people">
            <div className="login-card-header">
              <span>Sign in as</span>
              <strong>Demo identity</strong>
            </div>
            <div className="profile-choice-list">
              {USERS.map((u) => (
                <button
                  key={u.id}
                  className="profile-choice"
                  onClick={() => selectUser(u.id)}
                >
                  <span className="profile-avatar">{u.initials}</span>
                  <span className="profile-copy">
                    <span className="profile-name-row">
                      <strong>{u.display}</strong>
                      <em>{u.stats}</em>
                    </span>
                    <span>{u.summary}</span>
                  </span>
                </button>
              ))}
            </div>
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="header-brand">
          <span className="header-logo" aria-hidden="true">R</span>
          <span>
            <span className="header-title">ReVoice</span>
            <span className="header-tagline">Memory Agent</span>
          </span>
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

        <div className="header-profile">
          <span className="header-profile-avatar">{activeUser.initials}</span>
          <span className="header-profile-copy">
            <strong>{activeUser.display}</strong>
            <span>{activeUser.id}</span>
          </span>
          <button className="signout-btn" onClick={logout}>
            Switch
          </button>
        </div>
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
