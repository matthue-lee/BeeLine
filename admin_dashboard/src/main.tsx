import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./index.css";
import { TokenProvider } from "./state/token";

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <TokenProvider>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </TokenProvider>
  </React.StrictMode>
);
