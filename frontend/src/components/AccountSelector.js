import React, { useState } from 'react';

const AccountSelector = ({ accounts, selectedAccount, onAccountChange, allowMultiple = false }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedAccounts, setSelectedAccounts] = useState(
    allowMultiple ? [] : selectedAccount ? [selectedAccount] : []
  );

  const handleAccountToggle = (accountId) => {
    if (allowMultiple) {
      const newSelection = selectedAccounts.includes(accountId)
        ? selectedAccounts.filter(id => id !== accountId)
        : [...selectedAccounts, accountId];
      
      setSelectedAccounts(newSelection);
      onAccountChange(newSelection);
    } else {
      setSelectedAccounts([accountId]);
      onAccountChange(accountId);
      setIsOpen(false);
    }
  };

  const getSelectedAccountName = () => {
    if (allowMultiple) {
      if (selectedAccounts.length === 0) return 'Select accounts';
      if (selectedAccounts.length === 1) {
        const account = accounts.find(acc => acc.id === selectedAccounts[0]);
        return account?.username || 'Unknown';
      }
      return `${selectedAccounts.length} accounts selected`;
    } else {
      const account = accounts.find(acc => acc.id === selectedAccount);
      return account?.username || 'Select account';
    }
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between w-48 px-3 py-2 text-left bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
      >
        <span className="truncate">{getSelectedAccountName()}</span>
        <svg
          className={`w-5 h-5 ml-2 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto">
          {accounts.length === 0 ? (
            <div className="px-3 py-2 text-gray-500">No accounts available</div>
          ) : (
            accounts.map((account) => (
              <div
                key={account.id}
                onClick={() => handleAccountToggle(account.id)}
                className={`px-3 py-2 cursor-pointer hover:bg-gray-100 flex items-center justify-between ${
                  (allowMultiple ? selectedAccounts.includes(account.id) : selectedAccount === account.id)
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-900'
                }`}
              >
                <div className="flex items-center space-x-3">
                  <div className="w-8 h-8 bg-gradient-to-r from-blue-400 to-purple-500 rounded-full flex items-center justify-center text-white text-sm font-medium">
                    {account.username.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <div className="font-medium">{account.username}</div>
                    {account.created_at && (
                      <div className="text-xs text-gray-500">
                        Created {new Date(account.created_at).toLocaleDateString()}
                      </div>
                    )}
                  </div>
                </div>
                
                {allowMultiple && (
                  <input
                    type="checkbox"
                    checked={selectedAccounts.includes(account.id)}
                    onChange={() => {}} // Handled by parent onClick
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                )}
                
                {!allowMultiple && selectedAccount === account.id && (
                  <svg className="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Overlay to close dropdown when clicking outside */}
      {isOpen && (
        <div
          className="fixed inset-0 z-0"
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  );
};

export default AccountSelector;
