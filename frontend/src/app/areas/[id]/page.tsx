import { AreaDetailClient } from '@/components/AreaDetailClient';

export const dynamic = 'force-dynamic';

interface Params {
  params: Promise<{ id: string }>;
}

export default async function AreaDetailPage({ params }: Params) {
  const { id } = await params;
  return <AreaDetailClient areaId={id} />;
}
