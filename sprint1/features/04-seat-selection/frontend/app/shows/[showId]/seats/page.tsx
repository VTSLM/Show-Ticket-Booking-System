import React from 'react';
import { SeatSelectionProvider } from '@/features/seat-selection/context/SeatSelectionContext';
import { SeatSelectionView } from '@/features/seat-selection/components/SeatSelectionView';

interface PageProps {
  params: {
    showId: string;
  };
}

export default function SeatSelectionPage({ params }: PageProps) {
  const { showId } = params;

  return (
    <SeatSelectionProvider showId={showId}>
      <SeatSelectionView />
    </SeatSelectionProvider>
  );
}
