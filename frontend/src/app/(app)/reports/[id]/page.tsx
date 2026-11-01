"use client";

import { useParams } from "next/navigation";
import { Reports } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { PageHeader, Skeleton } from "@/components/ui";
import { ReportView } from "@/components/report-view";

export default function ReportPage() {
  const params = useParams<{ id: string }>();
  const report = useApi(() => Reports.get(Number(params.id)));

  if (report.loading) {
    return (
      <>
        <Skeleton className="h-9 w-72" />
        <div className="mt-6 grid gap-4 lg:grid-cols-3">
          <Skeleton className="h-64 rounded-xl" />
          <Skeleton className="h-64 rounded-xl lg:col-span-2" />
        </div>
      </>
    );
  }
  if (report.error || !report.data) return <p className="text-sm text-red-400">{report.error}</p>;

  return (
    <>
      <PageHeader
        title={`Benchmark report · run #${report.data.test_run_id}`}
        subtitle={`Generated ${new Date(report.data.created_at).toLocaleString()}`}
      />
      <ReportView summary={report.data.summary} runId={report.data.test_run_id} />
    </>
  );
}
