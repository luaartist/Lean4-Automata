'use client';

import { useModuleMetrics } from '@/lib/api/queries';
import { ModuleMetricsTable } from '@/components/ModuleMetricsTable';
import { Loading } from '@/components/states/Loading';
import { ErrorState } from '@/components/states/Error';
import { Breadcrumbs } from '@/components/Breadcrumbs';

export default function ProjectPage({ params }: { params: { name: string } }) {
  const projectId = parseInt(params.name, 10);
  const { data, isLoading, error, refetch } = useModuleMetrics(projectId);

  return (
    <div>
      <Breadcrumbs
        segments={[
          { label: 'Home', href: '/' },
          { label: `Project ${projectId}`, href: `/projects/${projectId}` },
        ]}
      />

      <h1 className="text-2xl font-bold mt-24 mb-16">
        Current Lean Project
      </h1>

      {isLoading && <Loading />}
      {error && (
        <ErrorState
          message="Failed to load module metrics"
          error={error}
          onRetry={() => refetch()}
        />
      )}
      {data && <ModuleMetricsTable metrics={data} projectId={projectId} />}
    </div>
  );
}
