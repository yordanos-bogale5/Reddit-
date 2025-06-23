import React, { useState } from "react";
import Dashboard from "./components/Dashboard";
import KarmaReports from "./components/KarmaReports";
import EngagementLogs from "./components/EngagementLogs";
import ActivitySchedule from "./components/ActivitySchedule";
import SubredditAnalytics from "./components/SubredditAnalytics";
import AccountHealth from "./components/AccountHealth";
import Settings from "./components/Settings";
import AdminPanel from "./components/AdminPanel";

const tabs = [
  { id: "dashboard", name: "Dashboard", component: Dashboard },
  { id: "karma", name: "Karma Reports", component: KarmaReports },
  { id: "engagement", name: "Engagement Logs", component: EngagementLogs },
  { id: "schedule", name: "Activity Schedule", component: ActivitySchedule },
  { id: "subreddits", name: "Subreddit Analytics", component: SubredditAnalytics },
  { id: "health", name: "Account Health", component: AccountHealth },
  { id: "settings", name: "Settings", component: Settings },
  { id: "admin", name: "Admin Panel", component: AdminPanel },
];

function App() {
  const [activeTab, setActiveTab] = useState(tabs[0].id);

  const getCurrentComponent = () => {
    const tab = tabs.find(t => t.id === activeTab);
    const Component = tab?.component;

    if (Component) {
      return <Component />;
    }

    return (
      <div className="bg-white rounded-lg shadow p-6 min-h-[300px]">
        <p className="text-gray-600">Component for {tab?.name} is under development.</p>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation */}
      <nav className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-8 overflow-x-auto">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                className={`py-4 px-1 border-b-2 font-medium text-sm whitespace-nowrap ${
                  activeTab === tab.id
                    ? "border-blue-500 text-blue-600"
                    : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                }`}
                onClick={() => setActiveTab(tab.id)}
              >
                {tab.name}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        {getCurrentComponent()}
      </main>
    </div>
  );
}

export default App; 