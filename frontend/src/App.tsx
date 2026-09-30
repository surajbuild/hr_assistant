import { useState } from "react";
import { LoginView } from "./LoginView";
import { ChatView } from "./ChatView";
import "./index.css";

export function App() {
  // Initialise from localStorage so a page refresh keeps the user logged in
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem("hr_token")
  );

  function handleLoginSuccess(newToken: string) {
    localStorage.setItem("hr_token", newToken);
    setToken(newToken);
  }

  function handleLogout() {
    localStorage.removeItem("hr_token");
    setToken(null);
  }

  if (!token) {
    return <LoginView onLoginSuccess={handleLoginSuccess} />;
  }

  return <ChatView token={token} onLogout={handleLogout} />;
}

export default App;
