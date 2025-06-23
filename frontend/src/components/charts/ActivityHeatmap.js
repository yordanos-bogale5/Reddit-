import React, { useState, useEffect, useCallback } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts';
import axios from 'axios';

const ActivityHeatmap = ({ accountId, days = 30 }) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [viewMode, setViewMode] = useState('hourly'); // 'hourly' or 'daily'

  const fetchActivityData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      if (viewMode === 'hourly') {
        // Fetch engagement data for hourly distribution
        const response = await axios.get(`/api/analytics/engagement/${accountId}?days=${days}`);
        const hourlyDistribution = response.data.hourly_distribution;

        // Transform hourly data
        const transformedData = Array.from({ length: 24 }, (_, hour) => ({
          hour: `${hour.toString().padStart(2, '0')}:00`,
          activity: hourlyDistribution[hour] || 0,
          hourNumber: hour
        }));

        setData(transformedData);
      } else {
        // Fetch daily activity data
        const response = await axios.get(`/api/analytics/time-series/${accountId}?metric=engagement&days=${days}`);

        const transformedData = response.data.data.map(item => ({
          date: new Date(item.date).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric'
          }),
          activity: item.total_actions,
          fullDate: item.date
        }));

        setData(transformedData);
      }
    } catch (err) {
      console.error('Error fetching activity data:', err);
      setError('Failed to load activity data');
    } finally {
      setLoading(false);
    }
  }, [accountId, days, viewMode]);

  useEffect(() => {
    if (accountId) {
      fetchActivityData();
    }
  }, [accountId, days, viewMode, fetchActivityData]);

  const getBarColor = (value, maxValue) => {
    const intensity = value / maxValue;
    if (intensity === 0) return '#f3f4f6';
    if (intensity < 0.25) return '#dbeafe';
    if (intensity < 0.5) return '#93c5fd';
    if (intensity < 0.75) return '#3b82f6';
    return '#1d4ed8';
  };

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const data = payload[0];
      return (
        <div className="bg-white p-3 border border-gray-200 rounded-lg shadow-lg">
          <p className="font-medium text-gray-900 mb-1">
            {viewMode === 'hourly' ? `Hour: ${label}` : `Date: ${label}`}
          </p>
          <p className="text-sm text-blue-600">
            Activity: {data.value.toLocaleString()}
          </p>
        </div>
      );
    }
    return null;
  };

  const maxActivity = Math.max(...data.map(d => d.activity));

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
            onClick={fetchActivityData}
            className="mt-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full">
      {/* View Mode Toggle */}
      <div className="flex justify-between items-center mb-4">
        <div className="flex space-x-2">
          <button
            onClick={() => setViewMode('hourly')}
            className={`px-3 py-1 rounded text-sm font-medium ${
              viewMode === 'hourly'
                ? 'bg-blue-500 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            Hourly
          </button>
          <button
            onClick={() => setViewMode('daily')}
            className={`px-3 py-1 rounded text-sm font-medium ${
              viewMode === 'daily'
                ? 'bg-blue-500 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            Daily
          </button>
        </div>
        
        {/* Activity Legend */}
        <div className="flex items-center space-x-2 text-xs">
          <span className="text-gray-600">Activity:</span>
          <div className="flex space-x-1">
            <div className="w-3 h-3 bg-gray-200 rounded"></div>
            <span>Low</span>
            <div className="w-3 h-3 bg-blue-300 rounded"></div>
            <div className="w-3 h-3 bg-blue-500 rounded"></div>
            <div className="w-3 h-3 bg-blue-700 rounded"></div>
            <span>High</span>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart 
            data={data} 
            margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis 
              dataKey={viewMode === 'hourly' ? 'hour' : 'date'}
              stroke="#6b7280"
              fontSize={12}
              tick={{ fill: '#6b7280' }}
              angle={viewMode === 'daily' ? -45 : 0}
              textAnchor={viewMode === 'daily' ? 'end' : 'middle'}
              height={viewMode === 'daily' ? 60 : 30}
            />
            <YAxis 
              stroke="#6b7280"
              fontSize={12}
              tick={{ fill: '#6b7280' }}
              tickFormatter={(value) => value.toLocaleString()}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar 
              dataKey="activity" 
              fill={(entry) => getBarColor(entry?.activity || 0, maxActivity)}
              radius={[2, 2, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-4 mt-4">
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-lg font-bold text-gray-900">
            {Math.max(...data.map(d => d.activity)).toLocaleString()}
          </div>
          <div className="text-sm text-gray-600">Peak Activity</div>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-lg font-bold text-gray-900">
            {(data.reduce((sum, d) => sum + d.activity, 0) / data.length).toFixed(1)}
          </div>
          <div className="text-sm text-gray-600">Average</div>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-lg font-bold text-gray-900">
            {data.reduce((sum, d) => sum + d.activity, 0).toLocaleString()}
          </div>
          <div className="text-sm text-gray-600">Total</div>
        </div>
      </div>

      {/* Peak Activity Time */}
      {viewMode === 'hourly' && (
        <div className="mt-4 p-3 bg-blue-50 rounded-lg">
          <div className="text-sm text-blue-800">
            <strong>Peak Activity:</strong> {
              data.find(d => d.activity === Math.max(...data.map(d => d.activity)))?.hour || 'N/A'
            } with {Math.max(...data.map(d => d.activity)).toLocaleString()} actions
          </div>
        </div>
      )}
    </div>
  );
};

export default ActivityHeatmap;
