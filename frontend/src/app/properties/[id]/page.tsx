import { PropertyDetailClient } from '@/components/PropertyDetailClient';

export const dynamic = 'force-dynamic';

interface Params {
  params: Promise<{ id: string }>;
}

export default async function PropertyDetailPage({ params }: Params) {
  const { id } = await params;
  return <PropertyDetailClient propertyId={id} />;
}
