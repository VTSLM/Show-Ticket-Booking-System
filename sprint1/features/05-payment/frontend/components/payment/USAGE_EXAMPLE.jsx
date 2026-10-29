// Example for a Next.js/React page after Feature 01 exposes the Firebase user
// and Feature 04 routes here with the canonical pending booking UUID.
'use client';

import PaymentCheckout from './PaymentCheckout';
import { useAuth } from '@/shared/auth/AuthProvider'; // replace with the team's actual auth hook
import { useSearchParams, useRouter } from 'next/navigation';
import { useCallback } from 'react';

export default function PaymentPage() {
  const { user } = useAuth();
  const search = useSearchParams();
  const router = useRouter();
  const bookingId = search.get('booking_id');
  const getAccessToken = useCallback(() => user?.getIdToken(), [user]);

  return (
    <PaymentCheckout
      bookingId={bookingId}
      apiBaseUrl={process.env.NEXT_PUBLIC_BACKEND_URL || ''}
      getAccessToken={getAccessToken}
      onBookingConfirmed={(result) => {
        // Feature 06 can use this callback or reload booking status from the API.
        // Do not generate a ticket based on the browser callback alone.
        if (result.booking_confirmation_status === 'confirmed') {
          router.replace(`/booking/confirmation?booking_id=${encodeURIComponent(result.booking_id)}`);
        }
      }}
    />
  );
}
