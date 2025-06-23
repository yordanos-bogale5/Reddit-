import React, { useState, useEffect, useCallback } from 'react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Legend
} from 'recharts';
import axios from 'axios';

const EngagementChart = ({ accountId, days = 30 }) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [engagementStats, setEngagementStats] = useState(null);

  const fetchEngagementData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.get(`/api/analytics/engagement/${accountId}?days=${days}`);
      const engagementData = response.data;

      setEngagementStats(engagementData);

      // Define colors inside the callback to avoid dependency issues
      const COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6'];

      // Transform actions_by_type data for PieChart
      const transformedData = Object.entries(engagementData.actions_by_type).map(([action, count], index) => ({
        name: action.charAt(0).toUpperCase() + action.slice(1),
        value: count,
        color: COLORS[index % COLORS.length]
      }));

      setData(transformedData);
    } catch (err) {
      console.error('Error fetching engagement data:', err);
      setError('Failed to load engagement data');
    } finally {
      setLoading(false);
    }
  }, [accountId, days]);

  useEffect(() => {
    if (accountId) {
      fetchEngagementData();
    }
  }, [accountId, days, fetchEngagementData]);

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0];
      return (
        <div className="bg-white p-3 border border-gray-200 rounded-lg shadow-lg">
          <p className="font-medium text-gray-900">{data.name}</p>
          <p className="text-sm text-gray-600">
            Count: {data.value.toLocaleString()}
          </p>
          <p className="text-sm text-gray-600">
            Percentage: {((data.value / engagementStats?.total_actions) * 100).toFixed(1)}%
          </p>
        </div>
      );
    }
    return null;
  };

  const renderCustomLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
    if (percent < 0.05) return null; // Don't show labels for slices smaller than 5%
    
    const RADIAN = Math.PI / 180;
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + radius * Math.cos(-midAngle * RADIAN);
    const y = cy + radius * Math.sin(-midAngle * RADIAN);

    return (
      <text 
        x={x} 
        y={y} 
        fill="white" 
        textAnchor={x > cx ? 'start' : 'end'} 
        dominantBaseline="central"
        fontSize={12}
        fontWeight="bold"
      >
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="text-red-500 text-4xl mb-2">⚠️</div>
          <p className="text-gray-600">{error}</p>
          <button
            onClick={fetchEngagementData}
            className="mt-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="text-gray-400 text-4xl mb-2">📊</div>
          <p className="text-gray-600">No engagement data available</p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full">
      {/* Summary Stats */}
      {engagementStats && (
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div className="text-center p-3 bg-gray-50 rounded-lg">
            <div className="text-lg font-bold text-gray-900">
              {engagementStats.total_actions.toLocaleString()}
            </div>
            <div className="text-sm text-gray-600">Total Actions</div>
          </div>
          <div className="text-center p-3 bg-gray-50 rounded-lg">
            <div className="text-lg font-bold text-green-600">
              {(engagementStats.success_rate * 100).toFixed(1)}%
            </div>
            <div className="text-sm text-gray-600">Success Rate</div>
          </div>
        </div>
      )}

      {/* Pie Chart */}
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              labelLine={false}
              label={renderCustomLabel}
              outerRadius={80}
              fill="#8884d8"
              dataKey="value"
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
            <Legend 
              verticalAlign="bottom" 
              height={36}
              formatter={(value, entry) => (
                <span style={{ color: entry.color }}>{value}</span>
              )}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Detailed Stats */}
      {engagementStats && (
        <div className="mt-4 space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Successful Actions:</span>
            <span className="font-medium text-green-600">
              {engagementStats.successful_actions.toLocaleString()}
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Failed Actions:</span>
            <span className="font-medium text-red-600">
              {engagementStats.failed_actions.toLocaleString()}
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Daily Average:</span>
            <span className="font-medium text-gray-900">
              {engagementStats.daily_average.toFixed(1)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default EngagementChart;
