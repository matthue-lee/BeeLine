import { FormEvent, useState, type CSSProperties } from "react";
import { useToken } from "../state/token";

const cardStyle: CSSProperties = {
  maxWidth: 520,
  margin: "4rem auto",
  padding: "2rem",
  borderRadius: 16,
  border: "1px solid #cbd5f5",
  background: "#fff"
};

function TokenGate({ errorMessage }: { errorMessage?: string }) {
  const { setToken } = useToken();
  const [value, setValue] = useState("");

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!value.trim()) return;
    setToken(value.trim());
    setValue("");
  };

  return (
    <div className="app-shell" style={{ background: "#0f172a", minHeight: "100vh" }}>
      <main style={cardStyle}>
        <h1 style={{ marginTop: 0 }}>BeeLine Admin Dashboard</h1>
        <p style={{ color: "#475569" }}>
          Paste an active admin session token to access the operations dashboard. Generate a new token via the OTP flow
          (`/api/admin/auth/request-code` + `/verify`). Tokens are stored in your browser only.
        </p>
        <form onSubmit={handleSubmit} className="stack">
          <label htmlFor="admin-token" className="section-title">
            Session Token
          </label>
          {errorMessage && (
            <div style={{ color: "#b91c1c", fontSize: "0.9rem" }}>{errorMessage}</div>
          )}
          <input
            id="admin-token"
            type="password"
            placeholder="Paste token here"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            required
            style={{ padding: "0.75rem", borderRadius: 10, border: "1px solid #cbd5f5" }}
          />
          <button type="submit" style={buttonStyle}>
            Continue
          </button>
        </form>
        <p style={{ color: "#475569", fontSize: "0.9rem", marginTop: "1.5rem" }}>
          Need OTP emails? Configure `SMTP_HOST` and related env vars in the ingestion API container so codes are delivered securely.
        </p>
      </main>
    </div>
  );
}

const buttonStyle: CSSProperties = {
  background: "#2563eb",
  color: "#fff",
  border: "none",
  borderRadius: 8,
  padding: "0.75rem 1.2rem",
  fontWeight: 600,
  cursor: "pointer"
};

export default TokenGate;
