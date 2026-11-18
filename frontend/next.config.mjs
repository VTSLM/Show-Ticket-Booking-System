/** @type {import('next').NextConfig} */
const nextConfig = {
  // The app does not use next/image, so the image optimizer is switched off and
  // no remote hosts are allowed. Several Next.js 14 advisories are in that optimizer.
  images: {
    unoptimized: true,
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
    NEXT_PUBLIC_RAZORPAY_KEY_ID: process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID || "",
  },
};

export default nextConfig;
