/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    domains: ["res.cloudinary.com", "images.unsplash.com", "m.media-amazon.com"],
  },
};

module.exports = nextConfig;
