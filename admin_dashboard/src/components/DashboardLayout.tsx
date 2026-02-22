import { useState } from "react";

import { useToken } from "../state/token";
import type { AdminUserProfile } from "../types";
import SystemOverviewSection from "../sections/SystemOverviewSection";
import IngestionRunsSection from "../sections/IngestionRunsSection";
import EntitiesSection from "../sections/EntitiesSection";
import FlagsSection from "../sections/FlagsSection";
import JobsSection from "../sections/JobsSection";
import CostSection from "../sections/CostSection";
import LLMActivitySection from "../sections/LLMActivitySection";
import ReleaseDebugSection from "../sections/ReleaseDebugSection";
import ToolsSection from "../sections/ToolsSection";
import ArticlesSection from "../sections/ArticlesSection";

const SECTIONS = [
  { id: "overview", label: "Overview", component: SystemOverviewSection },
  { id: "ingestion", label: "Ingestion Runs", component: IngestionRunsSection },
  { id: "entities", label: "Entities", component: EntitiesSection },
  { id: "flags", label: "Content Flags", component: FlagsSection },
  { id: "jobs", label: "Jobs & Queues", component: JobsSection },
  { id: "costs", label: "Cost Dashboard", component: CostSection },
  { id: "llm", label: "Summaries & LLM Calls", component: LLMActivitySection },
  { id: "articles", label: "News Articles", component: ArticlesSection },
  { id: "debug", label: "Release Debugger", component: ReleaseDebugSection },
  { id: "tools", label: "Tools & Docs", component: ToolsSection }
];

function DashboardLayout({ profile }: { profile: AdminUserProfile }) {
  const { clearToken } = useToken();
  const [activeSection, setActiveSection] = useState(SECTIONS[0].id);

  const section = SECTIONS.find((item) => item.id === activeSection) ?? SECTIONS[0];
  const SectionComponent = section.component;

  return (
    <div className="dashboard-shell">
      <aside className="sidebar">
        <div className="sidebar-header">
          <strong>BeeLine Admin</strong>
          <span>Operations desk</span>
        </div>
        <nav className="sidebar-nav">
          {SECTIONS.map((item) => (
            <button
              key={item.id}
              className={item.id === activeSection ? "nav-item active" : "nav-item"}
              onClick={() => setActiveSection(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </aside>
      <div className="dashboard-main">
        <header className="dashboard-header">
          <div>
            <h1>{section.label}</h1>
            <p>Monitoring & control surface</p>
          </div>
          <div className="user-info">
            <div>
              <strong>{profile.display_name || profile.email}</strong>
              <small>{profile.role}</small>
            </div>
            <button className="ghost" onClick={clearToken}>
              Log out
            </button>
          </div>
        </header>
        <section className="section-container">
          <SectionComponent />
        </section>
      </div>
    </div>
  );
}

export default DashboardLayout;
