import React, { useState } from 'react';
import axios from 'axios';

const ExportModal = ({ isOpen, onClose, accountId, accountIds = null, type = 'single' }) => {
  const [format, setFormat] = useState('json');
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleExport = async () => {
    setLoading(true);
    setError(null);

    try {
      let url;
      let params = { format, days };

      if (type === 'comparative' && accountIds) {
        url = '/api/analytics/export/comparative';
        params.account_ids = accountIds;
      } else {
        url = `/api/analytics/export/${accountId}`;
      }

      const response = await axios.get(url, { params });

      if (response.data.success) {
        // Trigger download
        const downloadUrl = response.data.download_url;
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = response.data.export_info.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        // Close modal after successful export
        setTimeout(() => {
          onClose();
        }, 1000);
      }
    } catch (err) {
      console.error('Export error:', err);
      setError(err.response?.data?.detail || 'Export failed');
    } finally {
      setLoading(false);
    }
  };

  const getFormatDescription = (fmt) => {
    switch (fmt) {
      case 'json':
        return 'Structured data format, ideal for further processing';
      case 'csv':
        return 'Spreadsheet format, compatible with Excel and Google Sheets';
      case 'pdf':
        return 'Formatted report (currently text format for demo)';
      default:
        return '';
    }
  };

  const getEstimatedSize = () => {
    const baseSize = type === 'comparative' ? (accountIds?.length || 1) * 50 : 50;
    const multiplier = days / 30;
    return Math.round(baseSize * multiplier);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">
            Export Analytics Data
          </h3>
          <p className="text-sm text-gray-600 mt-1">
            {type === 'comparative' 
              ? `Export data for ${accountIds?.length || 0} accounts`
              : 'Export data for selected account'
            }
          </p>
        </div>

        <div className="px-6 py-4 space-y-4">
          {/* Format Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Export Format
            </label>
            <div className="space-y-2">
              {['json', 'csv', 'pdf'].map((fmt) => (
                <label key={fmt} className="flex items-start space-x-3">
                  <input
                    type="radio"
                    name="format"
                    value={fmt}
                    checked={format === fmt}
                    onChange={(e) => setFormat(e.target.value)}
                    className="mt-1 w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                  />
                  <div className="flex-1">
                    <div className="text-sm font-medium text-gray-900">
                      {fmt.toUpperCase()}
                    </div>
                    <div className="text-xs text-gray-500">
                      {getFormatDescription(fmt)}
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Time Range */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Time Range
            </label>
            <select
              value={days}
              onChange={(e) => setDays(parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
              <option value={180}>Last 6 months</option>
              <option value={365}>Last year</option>
            </select>
          </div>

          {/* Export Info */}
          <div className="bg-gray-50 rounded-lg p-3">
            <div className="text-xs text-gray-600 space-y-1">
              <div>Estimated size: ~{getEstimatedSize()} KB</div>
              <div>Format: {format.toUpperCase()}</div>
              <div>Period: {days} days</div>
              {type === 'comparative' && (
                <div>Accounts: {accountIds?.length || 0}</div>
              )}
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3">
              <div className="text-sm text-red-600">{error}</div>
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
          <button
            onClick={onClose}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleExport}
            disabled={loading || (!accountId && !accountIds)}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
          >
            {loading && (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
            )}
            <span>{loading ? 'Exporting...' : 'Export'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default ExportModal;
