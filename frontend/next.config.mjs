/** @type {import('next').NextConfig} */
const nextConfig = {
  // The app does not use next/image, so the image optimizer is switched off and
  // no remote hosts are allowed. Several Next.js 14 advisories are in that optimizer.
  images: {
    unoptimized: true,
  },
  // Basic hardening headers for every page. A full Content-Security-Policy needs an
  // allow-list for Razorpay, Firebase, Google sign-in and map tiles, so only
  // frame-ancestors is set for now.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(self), microphone=(), geolocation=(self), payment=(self)" },
        ],
      },
    ];
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
    NEXT_PUBLIC_RAZORPAY_KEY_ID: process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID || "",
  },
};

export default nextConfig;
