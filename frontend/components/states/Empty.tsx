interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex items-center justify-center py-48">
      <div className="max-w-md text-center">
        {icon && <div className="mb-16">{icon}</div>}
        
        <h3 className="text-lg font-semibold mb-8">{title}</h3>
        
        {description && (
          <p className="text-sm text-text-secondary mb-16">{description}</p>
        )}
        
        {action && <div>{action}</div>}
      </div>
    </div>
  );
}
