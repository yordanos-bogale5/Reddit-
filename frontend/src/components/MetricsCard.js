import React from 'react';

const MetricsCard = ({ 
  title, 
  value, 
  icon, 
  color = 'blue', 
  format = 'default',
  suffix = '',
  trend = null,
  loading = false 
}) => {
  const formatValue = (val) => {
    if (loading) return '...';
    
    switch (format) {
      case 'number':
        return new Intl.NumberFormat().format(val);
      case 'percentage':
        return `${(val * 100).toFixed(1)}%`;
      case 'currency':
        return new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: 'USD'
        }).format(val);
      default:
        return val;
    }
  };

  const getColorClasses = (color) => {
    const colors = {
      blue: 'bg-blue-50 text-blue-600 border-blue-200',
      green: 'bg-green-50 text-green-600 border-green-200',
      yellow: 'bg-yellow-50 text-yellow-600 border-yellow-200',
      purple: 'bg-purple-50 text-purple-600 border-purple-200',
      red: 'bg-red-50 text-red-600 border-red-200',
      indigo: 'bg-indigo-50 text-indigo-600 border-indigo-200',
      cyan: 'bg-cyan-50 text-cyan-600 border-cyan-200',
      emerald: 'bg-emerald-50 text-emerald-600 border-emerald-200',
      orange: 'bg-orange-50 text-orange-600 border-orange-200',
    };
    return colors[color] || colors.blue;
  };

  const getTrendIcon = (trend) => {
    if (!trend) return null;
    if (trend > 0) return <span className="text-green-500">↗️</span>;
    if (trend < 0) return <span className="text-red-500">↘️</span>;
    return <span className="text-gray-500">➡️</span>;
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-600 mb-1">{title}</p>
          <div className="flex items-baseline space-x-2">
            <p className="text-2xl font-bold text-gray-900">
              {formatValue(value)}{suffix}
            </p>
            {trend !== null && getTrendIcon(trend)}
          </div>
          {trend !== null && (
            <p className="text-xs text-gray-500 mt-1">
              {trend > 0 ? '+' : ''}{trend.toFixed(1)}% from last period
            </p>
          )}
        </div>
        <div className={`p-3 rounded-full ${getColorClasses(color)}`}>
          <span className="text-xl">{icon}</span>
        </div>
      </div>
    </div>
  );
};

export default MetricsCard;
