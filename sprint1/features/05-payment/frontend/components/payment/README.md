# React/Next.js checkout component

`PaymentCheckout.jsx` is the frontend component intended for the team's React/Next.js application. It does not require a separate checkout page or a second frontend build owned by Feature 05.

## Mount it

Import the component into the team's Payment page and provide:

- `bookingId`: canonical pending booking UUID created after seat selection.
- `getAccessToken`: async function returning the signed-in Firebase user's ID token.
- `apiBaseUrl`: FastAPI origin, normally `NEXT_PUBLIC_BACKEND_URL`.
- Optional `onBookingConfirmed` and `onPaymentResult` callbacks.

See `USAGE_EXAMPLE.jsx`. Replace its example `useAuth` import with the actual Feature 01 auth provider. The component sends the token as `Authorization: Bearer ...`; it does not trust a client-provided user ID or amount. It gets the payable amount from the authenticated booking API and leaves payment-method selection to Razorpay Checkout.

The stylesheet is intentionally namespaced with `cp-` classes to avoid collisions with the shared application CSS. It includes reduced-motion handling and responsive layouts. Google Fonts and Razorpay Checkout load from their official CDNs, so browser internet access is required.

The existing `frontend/standalone-preview/index.html`, `app.js`, and `styles.css` remain the standalone demo/preview UI. Shared PostgreSQL mode is API-only and should be mounted from the team's main frontend via this React component.
