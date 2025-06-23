import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import KarmaChart from './charts/KarmaChart';
import EngagementChart from './charts/EngagementChart';
import ActivityHeatmap from './charts/ActivityHeatmap';
import MetricsCard from './MetricsCard';
import AccountSelector from './AccountSelector';

const Dashboard = () => {
  const [selectedAccount, setSelectedAccount] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState(30);

  const fetchAccounts = async () => {
    try {
      const response = await axios.get('/api/analytics/accounts');
      setAccounts(response.data);
      if (response.data.length > 0) {
        setSelectedAccount(response.data[0].id);
      }
    } catch (error) {
      console.error('Error fetching accounts:', error);
    }
  };

  const fetchDashboardSummary = async () => {
    try {
      const response = await axios.get('/api/analytics/dashboard-summary');
      setDashboardData(response.data);
    } catch (error) {
      console.error('Error fetching dashboard summary:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchAccountData = useCallback(async () => {
    if (!selectedAccount) return;

    setLoading(true);
    try {
      const [karmaResponse, engagementResponse, performanceResponse] = await Promise.all([
        axios.get(`/api/analytics/karma-growth/${selectedAccount}?days=${timeRange}`),
        axios.get(`/api/analytics/engagement/${selectedAccount}?days=${timeRange}`),
        axios.get(`/api/analytics/performance/${selectedAccount}?days=${timeRange}`)
      ]);

      // Update dashboard data with account-specific data
      setDashboardData(prev => ({
        ...prev,
        selectedAccountData: {
          karma: karmaResponse.data,
          engagement: engagementResponse.data,
          performance: performanceResponse.data
        }
      }));
    } catch (error) {
      console.error('Error fetching account data:', error);
    } finally {
      setLoading(false);
    }
  }, [selectedAccount, timeRange]);

  useEffect(() => {
    fetchAccounts();
    fetchDashboardSummary();
  }, []);

  useEffect(() => {
    if (selectedAccount) {
      fetchAccountData();
    }
  }, [selectedAccount, timeRange, fetchAccountData]);

  if (loading && !dashboardData) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center space-y-4 sm:space-y-0">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Reddit Automation Dashboard</h1>
          <p className="text-gray-600 mt-1">Monitor your Reddit automation performance</p>
        </div>
        
        <div className="flex space-x-4">
          <AccountSelector
            accounts={accounts}
            selectedAccount={selectedAccount}
            onAccountChange={setSelectedAccount}
          />
          
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(parseInt(e.target.value))}
            className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricsCard
          title="Total Accounts"
          value={dashboardData?.total_accounts || 0}
          icon="👥"
          color="blue"
        />
        <MetricsCard
          title="Total Karma"
          value={dashboardData?.total_karma || 0}
          icon="⭐"
          color="yellow"
          format="number"
        />
        <MetricsCard
          title="Actions Today"
          value={dashboardData?.total_actions_today || 0}
          icon="🎯"
          color="green"
        />
        <MetricsCard
          title="Success Rate"
          value={dashboardData?.success_rate_today || 0}
          icon="📈"
          color="purple"
          format="percentage"
        />
      </div>

      {/* Account-specific metrics */}
      {selectedAccount && dashboardData?.selectedAccountData && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <MetricsCard
            title="Karma Growth"
            value={dashboardData.selectedAccountData.karma.growth_rate_daily}
            icon="📊"
            color="indigo"
            format="number"
            suffix="/day"
          />
          <MetricsCard
            title="Total Actions"
            value={dashboardData.selectedAccountData.engagement.total_actions}
            icon="⚡"
            color="cyan"
          />
          <MetricsCard
            title="Success Rate"
            value={dashboardData.selectedAccountData.engagement.success_rate}
            icon="✅"
            color="emerald"
            format="percentage"
          />
          <MetricsCard
            title="Automation Efficiency"
            value={dashboardData.selectedAccountData.performance.automation_efficiency}
            icon="🤖"
            color="orange"
            format="percentage"
          />
        </div>
      )}

      {/* Charts Section */}
      {selectedAccount ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">Karma Growth</h3>
            <KarmaChart accountId={selectedAccount} days={timeRange} />
          </div>
          
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">Engagement Distribution</h3>
            <EngagementChart accountId={selectedAccount} days={timeRange} />
          </div>
          
          <div className="bg-white rounded-lg shadow p-6 lg:col-span-2">
            <h3 className="text-lg font-semibold mb-4">Activity Heatmap</h3>
            <ActivityHeatmap accountId={selectedAccount} days={timeRange} />
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-center py-12">
            <div className="text-gray-400 text-6xl mb-4">📊</div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">No Account Selected</h3>
            <p className="text-gray-600">Select an account to view detailed analytics</p>
          </div>
        </div>
      )}

      {/* Recent Activity */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold">Recent Activity</h3>
        </div>
        <div className="p-6">
          {dashboardData?.recent_activity?.length > 0 ? (
            <div className="space-y-3">
              {dashboardData.recent_activity.slice(0, 5).map((activity, index) => (
                <div key={index} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-b-0">
                  <div className="flex items-center space-x-3">
                    <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                    <span className="text-sm text-gray-900">{activity.action}</span>
                    <span className="text-xs text-gray-500">Account {activity.account_id}</span>
                  </div>
                  <span className="text-xs text-gray-400">
                    {new Date(activity.timestamp).toLocaleTimeString()}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              No recent activity
            </div>
          )}
        </div>
      </div>

      {/* Active Automations Status */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Automation Status</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="text-center p-4 bg-green-50 rounded-lg">
            <div className="text-2xl font-bold text-green-600">
              {dashboardData?.active_automations || 0}
            </div>
            <div className="text-sm text-green-700">Active Automations</div>
          </div>
          <div className="text-center p-4 bg-yellow-50 rounded-lg">
            <div className="text-2xl font-bold text-yellow-600">
              {dashboardData?.alerts_count || 0}
            </div>
            <div className="text-sm text-yellow-700">Pending Alerts</div>
          </div>
          <div className="text-center p-4 bg-blue-50 rounded-lg">
            <div className="text-2xl font-bold text-blue-600">
              {((dashboardData?.success_rate_today || 0) * 100).toFixed(1)}%
            </div>
            <div className="text-sm text-blue-700">Overall Success Rate</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
