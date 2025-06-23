import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import AccountSelector from './AccountSelector';
import KarmaChart from './charts/KarmaChart';
import MetricsCard from './MetricsCard';

const KarmaReports = () => {
  const [selectedAccount, setSelectedAccount] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [karmaData, setKarmaData] = useState(null);
  const [timeRange, setTimeRange] = useState(30);
  const [loading, setLoading] = useState(false);

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

  const fetchKarmaData = useCallback(async () => {
    if (!selectedAccount) return;

    setLoading(true);
    try {
      const response = await axios.get(`/api/analytics/karma-growth/${selectedAccount}?days=${timeRange}`);
      setKarmaData(response.data);
    } catch (error) {
      console.error('Error fetching karma data:', error);
    } finally {
      setLoading(false);
    }
  }, [selectedAccount, timeRange]);

  useEffect(() => {
    fetchAccounts();
  }, []);

  useEffect(() => {
    if (selectedAccount) {
      fetchKarmaData();
    }
  }, [selectedAccount, timeRange, fetchKarmaData]);

  const handleExport = () => {
    if (selectedAccount && karmaData) {
      // Create CSV content
      const csvContent = [
        ['Date', 'Total Karma', 'Post Karma', 'Comment Karma', 'Daily Growth'],
        ...karmaData.historical_data.map(item => [
          item.date,
          item.total_karma,
          item.post_karma,
          item.comment_karma,
          item.daily_growth
        ])
      ].map(row => row.join(',')).join('\n');

      // Download CSV
      const blob = new Blob([csvContent], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `karma-report-${selectedAccount}-${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center space-y-4 sm:space-y-0">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Karma Reports</h1>
          <p className="text-gray-600 mt-1">Track karma growth and analyze trends</p>
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
            <option value={365}>Last year</option>
          </select>
          
          <button
            onClick={handleExport}
            disabled={!selectedAccount || !karmaData}
            className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Export CSV
          </button>
        </div>
      </div>

      {/* Karma Metrics */}
      {karmaData && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <MetricsCard
            title="Total Karma"
            value={karmaData.total_karma}
            icon="⭐"
            color="yellow"
            format="number"
          />
          <MetricsCard
            title="Post Karma"
            value={karmaData.post_karma}
            icon="📝"
            color="blue"
            format="number"
          />
          <MetricsCard
            title="Comment Karma"
            value={karmaData.comment_karma}
            icon="💬"
            color="green"
            format="number"
          />
          <MetricsCard
            title="Daily Growth"
            value={karmaData.growth_rate_daily}
            icon="📈"
            color="purple"
            format="number"
            suffix="/day"
          />
        </div>
      )}

      {/* Growth Rates */}
      {karmaData && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">Growth Rates</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">
                {karmaData.growth_rate_daily.toFixed(1)}
              </div>
              <div className="text-sm text-gray-600">Per Day</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {karmaData.growth_rate_weekly.toFixed(1)}
              </div>
              <div className="text-sm text-gray-600">Per Week</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-purple-600">
                {karmaData.growth_rate_monthly.toFixed(1)}
              </div>
              <div className="text-sm text-gray-600">Per Month</div>
            </div>
          </div>
          
          {karmaData.peak_growth_day && (
            <div className="mt-4 p-3 bg-yellow-50 rounded-lg">
              <div className="text-sm text-yellow-800">
                <strong>Peak Growth Day:</strong> {karmaData.peak_growth_day}
              </div>
            </div>
          )}
          
          <div className="mt-4 p-3 bg-gray-50 rounded-lg">
            <div className="text-sm text-gray-700">
              <strong>Trend:</strong> 
              <span className={`ml-2 px-2 py-1 rounded text-xs font-medium ${
                karmaData.trend_direction === 'up' ? 'bg-green-100 text-green-800' :
                karmaData.trend_direction === 'down' ? 'bg-red-100 text-red-800' :
                'bg-gray-100 text-gray-800'
              }`}>
                {karmaData.trend_direction === 'up' ? '📈 Increasing' :
                 karmaData.trend_direction === 'down' ? '📉 Decreasing' :
                 '➡️ Stable'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Karma Chart */}
      {selectedAccount && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">Karma Growth Over Time</h3>
          <KarmaChart accountId={selectedAccount} days={timeRange} />
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
        </div>
      )}

      {/* No Account Selected */}
      {!selectedAccount && !loading && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-center py-12">
            <div className="text-gray-400 text-6xl mb-4">⭐</div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">No Account Selected</h3>
            <p className="text-gray-600">Select an account to view karma reports</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default KarmaReports;
