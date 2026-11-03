import { defineConfig } from 'vite'; // Imports Vite configuration helper.
import react from '@vitejs/plugin-react'; // Enables React JSX support.

export default defineConfig({ // Configure React support and local API forwarding.
  plugins: [react()], // Enable React JSX and Fast Refresh.
  server: { // Configure only the local Vite development server.
    proxy: { // Forward API calls without changing the browser-visible host.
      '/api/v1': { target: 'http://127.0.0.1:8000', changeOrigin: true }, // Keep browser cookies on the same local site as the frontend.
    }, // Finish the local API proxy rules.
  }, // Finish the development server settings.
}); // Export the Vite configuration.
