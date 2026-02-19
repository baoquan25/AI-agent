const path = require('path');

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Frontend is in a subfolder; use this dir as root so Next doesn't use parent yarn.lock
  outputFileTracingRoot: path.join(__dirname),
};

module.exports = nextConfig;
