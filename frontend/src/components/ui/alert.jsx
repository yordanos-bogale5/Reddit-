import React from 'react';

export const Alert = ({ 
  children, 
  variant = 'default', 
  className = '', 
  ...props 
}) => {
  const baseClasses = 'relative w-full rounded-lg border p-4';
  
  const variants = {
    default: 'bg-white border-gray-200',
    destructive: 'border-red-200 bg-red-50 text-red-900',
    warning: 'border-yellow-200 bg-yellow-50 text-yellow-900'
  };
  
  return (
    <div
      className={`${baseClasses} ${variants[variant]} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};

export const AlertDescription = ({ 
  children, 
  className = '', 
  ...props 
}) => (
  <div 
    className={`text-sm [&_p]:leading-relaxed ${className}`}
    {...props}
  >
    {children}
  </div>
);
